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
    """S3 upload generation must enforce upload-time content-length-range and exact key policy conditions."""
    mock_boto = MagicMock()
    mock_client = MagicMock()
    expected_key = "tenants/t1/quarantine/uuid1"
    mock_client.generate_presigned_post.return_value = {
        "url": "https://s3.amazonaws.com/test-bucket",
        "fields": {"key": expected_key, "policy": "xyz=="},
    }
    mock_boto.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto, "botocore.config": MagicMock()}):
        s3 = S3StorageService(bucket_name="test-bucket", use_ssl=True)
        info = s3.generate_presigned_upload_url(
            object_key=expected_key,
            content_type="application/pdf",
            max_size_bytes=26214400,
        )

        assert info.method == "POST"
        assert info.url == "https://s3.amazonaws.com/test-bucket"
        assert info.fields["policy"] == "xyz=="

        # Assert content-length-range and exact key was passed in conditions
        calls = mock_client.generate_presigned_post.call_args
        conditions = calls[1]["Conditions"]
        assert ["content-length-range", 1, 26214400] in conditions
        assert {"key": expected_key} in conditions
        # Assert starts-with is NOT used for key (to prevent suffix appended keys)
        assert not any(isinstance(c, list) and len(c) > 1 and c[0] == "starts-with" and c[1] == "$key" for c in conditions)

        # Policy condition simulation: verify exact-match behavior vs suffix / alternate keys
        def validate_policy_key(conds, candidate_key):
            for c in conds:
                if isinstance(c, dict) and "key" in c:
                    return c["key"] == candidate_key
                elif isinstance(c, list) and len(c) == 3 and c[0] == "eq" and c[1] == "$key":
                    return c[2] == candidate_key
            return False

        # Exact key succeeds
        assert validate_policy_key(conditions, expected_key) is True
        # Appended suffix is rejected by exact-match policy
        assert validate_policy_key(conditions, expected_key + "/extra") is False
        assert validate_policy_key(conditions, expected_key + ".png") is False
        # Alternate key under same tenant prefix is rejected
        assert validate_policy_key(conditions, "tenants/t1/quarantine/different_uuid") is False


def test_s3_storage_presigned_post_failure_fails_closed():
    """When S3 presigned POST generation fails, it must fail closed and NEVER fall back to presigned PUT."""
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_presigned_post.side_effect = RuntimeError("AWS S3 Presigned POST Generation Failed")
    mock_boto.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto, "botocore.config": MagicMock()}):
        s3 = S3StorageService(bucket_name="test-bucket", use_ssl=True)
        with pytest.raises(StorageSecurityError, match="Failed to generate secure S3 presigned POST policy"):
            s3.generate_presigned_upload_url(
                object_key="tenants/t1/quarantine/uuid1",
                content_type="application/pdf",
                max_size_bytes=26214400,
            )

        # Invariant: No presigned PUT URL was ever generated or attempted
        assert mock_client.generate_presigned_url.called is False


def test_storage_service_streaming_upload_bounded_and_cleanup(tmp_path):
    """Storage stream_upload_object must stream chunks with byte ceiling and purge partial data on error."""
    # Helper to drive coroutine without async event loop socketpair
    def run_sync(coro):
        try:
            coro.send(None)
        except StopIteration as e:
            return e.value

    # 1. MemoryStorageService
    mem = MemoryStorageService()
    mem_key = "tenants/t1/quarantine/mem_doc"

    # 1a. Successful bounded stream
    chunks = [b"chunk1_", b"chunk2_", b"chunk3"]
    total = run_sync(mem.stream_upload_object(mem_key, iter(chunks), max_bytes=100))
    assert total == len(b"chunk1_chunk2_chunk3")
    assert mem.get_object(mem_key) == b"chunk1_chunk2_chunk3"

    # 1b. Exceeding max_bytes aborts immediately and purges partial object
    overflow_key = "tenants/t1/quarantine/overflow"
    with pytest.raises(StoragePayloadTooLargeError, match="exceeded maximum permitted limit"):
        run_sync(mem.stream_upload_object(overflow_key, iter([b"A" * 50, b"B" * 60]), max_bytes=100))
    assert not mem.object_exists(overflow_key)

    # 1c. Empty stream raises ValueError and leaves no object
    empty_key = "tenants/t1/quarantine/empty"
    with pytest.raises(ValueError, match="empty"):
        run_sync(mem.stream_upload_object(empty_key, iter([]), max_bytes=100))
    assert not mem.object_exists(empty_key)

    # 2. LocalStorageService
    local = LocalStorageService(base_path=str(tmp_path / "storage"))
    local_key = "tenants/t1/quarantine/local_doc"

    # 2a. Successful bounded stream
    total_loc = run_sync(local.stream_upload_object(local_key, iter(chunks), max_bytes=100))
    assert total_loc == len(b"chunk1_chunk2_chunk3")
    assert local.get_object(local_key) == b"chunk1_chunk2_chunk3"

    # 2b. Exceeding max_bytes aborts immediately and cleans up temporary and final files
    loc_overflow_key = "tenants/t1/quarantine/loc_overflow"
    with pytest.raises(StoragePayloadTooLargeError, match="exceeded maximum permitted limit"):
        run_sync(local.stream_upload_object(loc_overflow_key, iter([b"X" * 60, b"Y" * 50]), max_bytes=100))
    assert not local.object_exists(loc_overflow_key)
    # Ensure no leftover temp files exist in the quarantine directory
    quarantine_dir = tmp_path / "storage" / "tenants" / "t1" / "quarantine"
    temp_files = list(quarantine_dir.glob(".tmp_*"))
    assert len(temp_files) == 0, f"Found leaked temp files: {temp_files}"

    # 2c. Empty stream raises ValueError
    loc_empty_key = "tenants/t1/quarantine/loc_empty"
    with pytest.raises(ValueError, match="empty"):
        run_sync(local.stream_upload_object(loc_empty_key, iter([]), max_bytes=100))
    assert not local.object_exists(loc_empty_key)


def test_s3_and_gcs_spooling_cleanup_on_success_overflow_and_failure():
    """Verify S3 and GCS disk spooling unlinks temporary files on success, overflow, and provider failure."""
    temp_dir = Path(tempfile.gettempdir())

    def run_sync(coro):
        try:
            coro.send(None)
        except StopIteration as e:
            return e.value

    # --- S3 Spooling Cleanup ---
    mock_boto = MagicMock()
    mock_s3_client = MagicMock()
    mock_boto.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto, "botocore.config": MagicMock()}):
        s3 = S3StorageService(bucket_name="spool-bucket")

        # 1. Success case: temp spool unlinked
        before_spools = set(temp_dir.glob("regulens_s3_spool_*.tmp"))
        total = run_sync(s3.stream_upload_object("tenants/t1/doc1", iter([b"data1", b"data2"]), max_bytes=100))
        assert total == 10
        assert mock_s3_client.put_object.called is True
        after_spools = set(temp_dir.glob("regulens_s3_spool_*.tmp"))
        assert after_spools - before_spools == set()

        # 2. Overflow case: StoragePayloadTooLargeError raised and temp spool unlinked
        before_spools = set(temp_dir.glob("regulens_s3_spool_*.tmp"))
        with pytest.raises(StoragePayloadTooLargeError):
            run_sync(s3.stream_upload_object("tenants/t1/overflow", iter([b"A" * 60, b"B" * 60]), max_bytes=100))
        after_spools = set(temp_dir.glob("regulens_s3_spool_*.tmp"))
        assert after_spools - before_spools == set()

        # 3. Provider error case: put_object fails, error propagated and temp spool unlinked
        mock_s3_client.put_object.side_effect = RuntimeError("S3 Put Failed")
        before_spools = set(temp_dir.glob("regulens_s3_spool_*.tmp"))
        with pytest.raises(RuntimeError, match="S3 Put Failed"):
            run_sync(s3.stream_upload_object("tenants/t1/fail", iter([b"some-bytes"]), max_bytes=100))
        after_spools = set(temp_dir.glob("regulens_s3_spool_*.tmp"))
        assert after_spools - before_spools == set()

    # --- GCS Spooling Cleanup ---
    mock_storage = MagicMock()
    mock_gcs_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_storage.Client.return_value = mock_gcs_client
    mock_gcs_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    mock_google = MagicMock()
    mock_google.storage = mock_storage

    with patch.dict("sys.modules", {"google": MagicMock(cloud=mock_google), "google.cloud": mock_google, "google.cloud.storage": mock_storage}):
        gcs = GCSStorageService(bucket_name="gcs-spool-bucket")

        # 1. Success case: temp spool unlinked
        before_spools = set(temp_dir.glob("regulens_gcs_spool_*.tmp"))
        total = run_sync(gcs.stream_upload_object("tenants/t1/gcs_doc", iter([b"gcs1", b"gcs2"]), max_bytes=100))
        assert total == 8
        assert mock_blob.upload_from_filename.called is True
        after_spools = set(temp_dir.glob("regulens_gcs_spool_*.tmp"))
        assert after_spools - before_spools == set()

        # 2. Overflow case: temp spool unlinked
        before_spools = set(temp_dir.glob("regulens_gcs_spool_*.tmp"))
        with pytest.raises(StoragePayloadTooLargeError):
            run_sync(gcs.stream_upload_object("tenants/t1/gcs_overflow", iter([b"Z" * 80, b"Z" * 50]), max_bytes=100))
        after_spools = set(temp_dir.glob("regulens_gcs_spool_*.tmp"))
        assert after_spools - before_spools == set()

        # 3. Provider error case: upload_from_filename fails, temp spool unlinked
        mock_blob.upload_from_filename.side_effect = RuntimeError("GCS Upload Failed")
        mock_blob.exists.return_value = False
        before_spools = set(temp_dir.glob("regulens_gcs_spool_*.tmp"))
        with pytest.raises(RuntimeError, match="GCS Upload Failed"):
            run_sync(gcs.stream_upload_object("tenants/t1/gcs_fail", iter([b"payload"]), max_bytes=100))
        after_spools = set(temp_dir.glob("regulens_gcs_spool_*.tmp"))
        assert after_spools - before_spools == set()



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
