"""Unit tests for storage service abstractions, presigned URLs, and tenant isolation."""
from pathlib import Path
import tempfile
import uuid
import pytest

from app.services.storage import (
    MemoryStorageService,
    LocalStorageService,
    generate_tenant_object_key,
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
