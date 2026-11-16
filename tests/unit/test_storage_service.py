"""Unit tests for storage service abstractions, presigned URLs, and tenant isolation."""
from pathlib import Path
import tempfile
import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import Settings
from app.services.storage import (
    MemoryStorageService,
    LocalStorageService,
    S3StorageService,
    GCSStorageService,
    StorageSecurityError,
    StoragePayloadTooLargeError,
    generate_tenant_object_key,
    get_storage_service,
    set_storage_service,
)


def test_generate_tenant_object_key_is_opaque_and_tenant_scoped():
    tenant_id = uuid.uuid4()
    quarantine_key = generate_tenant_object_key(tenant_id, is_quarantine=True)
    permanent_key = generate_tenant_object_key(tenant_id, is_quarantine=False)

    assert quarantine_key.startswith(f"tenants/{tenant_id}/quarantine/")
    assert permanent_key.startswith(f"tenants/{tenant_id}/documents/")

    # Ensure random opaque hex suffix (32 chars)
    quarantine_id = quarantine_key.split("/")[-1]
    permanent_id = permanent_key.split("/")[-1]
    assert len(quarantine_id) == 32
    assert len(permanent_id) == 32
    assert quarantine_id != permanent_id


def test_memory_storage_crud_and_presigned_urls():
    storage = MemoryStorageService()
    key = "tenants/test-tenant/quarantine/abc123"
    data = b"Hello Secure Storage"

    # Put and exists
    assert not storage.object_exists(key)
    storage.put_object(key, data, content_type="application/pdf")
    assert storage.object_exists(key)

    # Get
    assert storage.get_object(key) == data

    # Metadata
    meta = storage.get_object_metadata(key)
    assert meta.key == key
    assert meta.size_bytes == len(data)
    assert meta.content_type == "application/pdf"

    # Presigned URLs
    upload_info = storage.generate_presigned_upload_url(key, expires_in_seconds=900)
    assert upload_info.expires_in_seconds == 900
    assert upload_info.method == "PUT"
    assert "expires=" in upload_info.url
    assert "sig=" in upload_info.url

    download_info = storage.generate_presigned_download_url(
        key, expires_in_seconds=900, response_content_disposition='attachment; filename="doc.pdf"'
    )
    assert download_info.expires_in_seconds == 900
    assert download_info.method == "GET"
    assert "attachment" in download_info.headers.get("Response-Content-Disposition", "")

    # Move object (quarantine -> permanent)
    dest_key = "tenants/test-tenant/documents/final456"
    storage.move_object(key, dest_key)
    assert not storage.object_exists(key)
    assert storage.object_exists(dest_key)
    assert storage.get_object(dest_key) == data

    # Delete
    assert storage.delete_object(dest_key)
    assert not storage.object_exists(dest_key)


def test_local_storage_path_traversal_prevention():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = LocalStorageService(base_path=temp_dir)
        safe_key = "tenants/t1/documents/safe.pdf"
        storage.put_object(safe_key, b"content")
        assert storage.object_exists(safe_key)

        # Path traversal attack keys
        malicious_keys = [
            "../../etc/passwd",
            "../secret.txt",
            "tenants/t1/../../../root/shadow",
        ]
        for bad_key in malicious_keys:
            with pytest.raises(ValueError, match="Path traversal detected"):
                storage.put_object(bad_key, b"evil")
            with pytest.raises(ValueError, match="Path traversal detected"):
                storage.get_object(bad_key)
            with pytest.raises(ValueError, match="Path traversal detected"):
                storage.object_exists(bad_key)


# ==============================================================================
# Package C: Size Enforcement, S3 Security & GCS Adapter Tests
# ==============================================================================

def test_storage_size_enforcement_in_memory_and_local():
    """Object size limits (25MB) must be enforced across put and bounded get operations."""
    storage = MemoryStorageService()
    oversized = b"A" * (25 * 1024 * 1024 + 1)
    with pytest.raises(StoragePayloadTooLargeError):
        storage.put_object("tenants/t1/quarantine/too_big", oversized)

    # Valid size put, but restricted get_object max_bytes
    storage.put_object("tenants/t1/quarantine/bounded", b"1234567890")
    with pytest.raises(StoragePayloadTooLargeError):
        storage.get_object("tenants/t1/quarantine/bounded", max_bytes=5)


def test_s3_storage_presigned_post_content_length_range():
    """S3 upload generation must enforce upload-time content-length-range policy conditions."""
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_presigned_post.return_value = {
        "url": "https://s3.amazonaws.com/test-bucket",
        "fields": {"key": "tenants/t1/quarantine/uuid1", "policy": "xyz=="},
    }
    mock_boto.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto, "botocore.config": MagicMock()}):
        s3 = S3StorageService(bucket_name="test-bucket", use_ssl=True)
        info = s3.generate_presigned_upload_url(
            object_key="tenants/t1/quarantine/uuid1",
            content_type="application/pdf",
            max_size_bytes=26214400,
        )

        assert info.method == "POST"
        assert info.url == "https://s3.amazonaws.com/test-bucket"
        assert info.fields["policy"] == "xyz=="

        # Assert content-length-range was passed in conditions
        calls = mock_client.generate_presigned_post.call_args
        conditions = calls[1]["Conditions"]
        assert ["content-length-range", 1, 26214400] in conditions


def test_s3_storage_verify_bucket_configuration():
    """S3 bucket verification must fail closed if public access block settings are missing or incomplete."""
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_boto.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto, "botocore.config": MagicMock()}):
        s3 = S3StorageService(bucket_name="secure-bucket")

        # 1. Successful verification when all 4 controls are enabled
        mock_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }
        res = s3.verify_bucket_configuration()
        assert res["status"] == "verified"
        assert res["public_access_blocked"] is True

        # 2. Failure when one control is False
        mock_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }
        with pytest.raises(StorageSecurityError, match="incomplete public access block"):
            s3.verify_bucket_configuration()


def test_gcs_storage_service_operations_and_ubla_verification():
    """GCS adapter must generate signed URLs, enforce bounded reads, and verify UBLA security controls."""
    mock_storage = MagicMock()
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_storage.Client.return_value = mock_client
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    mock_google = MagicMock()
    mock_google.storage = mock_storage

    with patch.dict("sys.modules", {"google": MagicMock(cloud=mock_google), "google.cloud": mock_google, "google.cloud.storage": mock_storage}):
        gcs = GCSStorageService(bucket_name="gcs-secure-bucket")

        # 1. Direct presigned uploads disabled for GCS to prevent unrestricted client upload bypass
        assert gcs.supports_direct_upload is False
        with pytest.raises(StorageSecurityError, match="Direct presigned uploads are disabled for Google Cloud Storage"):
            gcs.generate_presigned_upload_url("tenants/t1/quarantine/gcs-uuid")

        # 2. Presigned download remains functional
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        down = gcs.generate_presigned_download_url("tenants/t1/documents/gcs-uuid")
        assert down.url == "https://storage.googleapis.com/signed-url"
        assert down.method == "GET"

        # 2. Bounded get_object rejects oversized blob
        mock_blob.exists.return_value = True
        mock_blob.size = 30 * 1024 * 1024  # 30MB
        with pytest.raises(StoragePayloadTooLargeError):
            gcs.get_object("tenants/t1/quarantine/gcs-uuid", max_bytes=26214400)

        # 3. UBLA and public access prevention verification
        mock_client.get_bucket.return_value = mock_bucket
        iam_cfg = MagicMock()
        iam_cfg.uniform_bucket_level_access_enabled = True
        iam_cfg.public_access_prevention = "enforced"
        mock_bucket.iam_configuration = iam_cfg

        status = gcs.verify_bucket_configuration()
        assert status["status"] == "verified"
        assert status["uniform_bucket_level_access"] is True
        assert status["public_access_prevention"] == "enforced"

        # 4. Fails if UBLA disabled
        iam_cfg.uniform_bucket_level_access_enabled = False
        with pytest.raises(StorageSecurityError, match="Uniform Bucket-Level Access"):
            gcs.verify_bucket_configuration()


def test_get_storage_service_production_fail_closed():
    """Factory get_storage_service must raise RuntimeError in production if non-cloud storage is selected."""
    from app.services.storage import _storage_lock
    import app.services.storage as storage_mod

    # Reset singleton
    with _storage_lock:
        storage_mod._storage_instance = None

    with patch.object(storage_mod.settings, "ENVIRONMENT", "production"), \
         patch.object(storage_mod.settings, "STORAGE_BACKEND", "memory"):
        with pytest.raises(RuntimeError, match="Production security violation: In-memory or local filesystem storage"):
            get_storage_service()

    with _storage_lock:
        storage_mod._storage_instance = None

    with patch.object(storage_mod.settings, "ENVIRONMENT", "development"), \
         patch.object(storage_mod.settings, "STORAGE_BACKEND", "invalid_backend"):
        with pytest.raises(ValueError, match="Unknown storage backend: 'invalid_backend'"):
            get_storage_service()

    with _storage_lock:
        storage_mod._storage_instance = None
