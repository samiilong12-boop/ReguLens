"""Storage abstraction service providing provider-independent object storage.

In accordance with Package C:
- Private objects only (zero public URLs or public buckets).
- Random, opaque, tenant-scoped object keys.
- Never relies on client-supplied filenames for object paths.
- Provider-specific implementations (Memory, Local, S3/GCS) isolated behind an interface.
- Thread-safe MemoryStorageService and LocalStorageService for CI and test isolation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import os
from pathlib import Path
import threading
from typing import Dict, Optional, Tuple
from uuid import UUID, uuid4

from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StorageObjectMetadata:
    """Metadata describing a stored object."""
    key: str
    size_bytes: int
    content_type: str
    etag: str
    last_modified: datetime


@dataclass(frozen=True)
class PresignedUrlInfo:
    """Details for a generated presigned operation."""
    url: str
    expires_in_seconds: int
    method: str
    headers: Dict[str, str] = field(default_factory=dict)


def generate_tenant_object_key(tenant_id: UUID, is_quarantine: bool = False) -> str:
    """Generates an opaque, randomized, tenant-scoped object key.
    
    Security: User-supplied filenames are NEVER used in the object key.
    Format:
      Quarantine: tenants/{tenant_id}/quarantine/{opaque_hex}
      Permanent:  tenants/{tenant_id}/documents/{opaque_hex}
    """
    opaque_id = uuid4().hex
    folder = "quarantine" if is_quarantine else "documents"
    return f"tenants/{tenant_id}/{folder}/{opaque_id}"


class StorageService(ABC):
    """Abstract provider-independent storage interface."""

    @abstractmethod
    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        content_type: Optional[str] = None,
        max_size_bytes: int = 25 * 1024 * 1024,
    ) -> PresignedUrlInfo:
        """Generates a short-lived URL for uploading directly to quarantine."""
        pass

    @abstractmethod
    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        response_content_disposition: Optional[str] = None,
    ) -> PresignedUrlInfo:
        """Generates a short-lived URL for authorized document download."""
        pass

    @abstractmethod
    def get_object(self, object_key: str) -> bytes:
        """Retrieves raw object bytes from storage."""
        pass

    @abstractmethod
    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        """Stores raw object bytes in storage."""
        pass

    @abstractmethod
    def delete_object(self, object_key: str) -> bool:
        """Deletes an object from storage if it exists."""
        pass

    @abstractmethod
    def move_object(self, source_key: str, destination_key: str) -> None:
        """Moves an object from source to destination (e.g. quarantine to permanent)."""
        pass

    @abstractmethod
    def copy_object(self, source_key: str, destination_key: str) -> None:
        """Copies an object from source to destination."""
        pass

    @abstractmethod
    def object_exists(self, object_key: str) -> bool:
        """Checks if an object exists in storage."""
        pass

    @abstractmethod
    def get_object_metadata(self, object_key: str) -> StorageObjectMetadata:
        """Retrieves object metadata (size, content_type, etag, last_modified)."""
        pass


class MemoryStorageService(StorageService):
    """In-memory, thread-safe object storage for unit testing and CI."""

    def __init__(self, signing_secret: str = "memory_storage_signing_key_for_testing"):
        self._objects: Dict[str, Tuple[bytes, str, datetime]] = {}
        self._lock = threading.Lock()
        self._signing_secret = signing_secret.encode("utf-8")

    def _sign(self, key: str, expires_at: int) -> str:
        msg = f"{key}:{expires_at}".encode("utf-8")
        return hmac.new(self._signing_secret, msg, hashlib.sha256).hexdigest()

    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        content_type: Optional[str] = None,
        max_size_bytes: int = 25 * 1024 * 1024,
    ) -> PresignedUrlInfo:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in_seconds
        sig = self._sign(object_key, expires_at)
        url = f"https://storage.regulens.internal/quarantine/upload/{object_key}?expires={expires_at}&sig={sig}"
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        return PresignedUrlInfo(
            url=url,
            expires_in_seconds=expires_in_seconds,
            method="PUT",
            headers=headers,
        )

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        response_content_disposition: Optional[str] = None,
    ) -> PresignedUrlInfo:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in_seconds
        sig = self._sign(object_key, expires_at)
        url = f"https://storage.regulens.internal/documents/download/{object_key}?expires={expires_at}&sig={sig}"
        headers = {}
        if response_content_disposition:
            headers["Response-Content-Disposition"] = response_content_disposition
        return PresignedUrlInfo(
            url=url,
            expires_in_seconds=expires_in_seconds,
            method="GET",
            headers=headers,
        )

    def get_object(self, object_key: str) -> bytes:
        with self._lock:
            if object_key not in self._objects:
                raise FileNotFoundError(f"Object '{object_key}' does not exist in storage.")
            return self._objects[object_key][0]

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        with self._lock:
            ct = content_type or "application/octet-stream"
            self._objects[object_key] = (data, ct, datetime.now(timezone.utc))

    def delete_object(self, object_key: str) -> bool:
        with self._lock:
            if object_key in self._objects:
                del self._objects[object_key]
                return True
            return False

    def copy_object(self, source_key: str, destination_key: str) -> None:
        with self._lock:
            if source_key not in self._objects:
                raise FileNotFoundError(f"Source object '{source_key}' does not exist in storage.")
            data, ct, _ = self._objects[source_key]
            self._objects[destination_key] = (data, ct, datetime.now(timezone.utc))

    def move_object(self, source_key: str, destination_key: str) -> None:
        with self._lock:
            if source_key not in self._objects:
                raise FileNotFoundError(f"Source object '{source_key}' does not exist in storage.")
            item = self._objects.pop(source_key)
            self._objects[destination_key] = (item[0], item[1], datetime.now(timezone.utc))

    def object_exists(self, object_key: str) -> bool:
        with self._lock:
            return object_key in self._objects

    def get_object_metadata(self, object_key: str) -> StorageObjectMetadata:
        with self._lock:
            if object_key not in self._objects:
                raise FileNotFoundError(f"Object '{object_key}' does not exist in storage.")
            data, ct, ts = self._objects[object_key]
            etag = hashlib.md5(data).hexdigest()
            return StorageObjectMetadata(
                key=object_key,
                size_bytes=len(data),
                content_type=ct,
                etag=etag,
                last_modified=ts,
            )

    def clear(self) -> None:
        """Test helper to reset storage between test cases."""
        with self._lock:
            self._objects.clear()


class LocalStorageService(StorageService):
    """Local filesystem storage with path traversal defenses."""

    def __init__(self, base_path: str = "./data/storage", signing_secret: str = "local_storage_secret"):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._signing_secret = signing_secret.encode("utf-8")

    def _resolve_key(self, object_key: str) -> Path:
        normalized = Path(object_key)
        resolved = (self.base_path / normalized).resolve()
        # Path traversal guard
        if not resolved.is_relative_to(self.base_path):
            raise ValueError(f"Path traversal detected in object key: {object_key}")
        return resolved

    def _sign(self, key: str, expires_at: int) -> str:
        msg = f"{key}:{expires_at}".encode("utf-8")
        return hmac.new(self._signing_secret, msg, hashlib.sha256).hexdigest()

    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        content_type: Optional[str] = None,
        max_size_bytes: int = 25 * 1024 * 1024,
    ) -> PresignedUrlInfo:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in_seconds
        sig = self._sign(object_key, expires_at)
        url = f"https://storage.local.regulens.internal/quarantine/upload/{object_key}?expires={expires_at}&sig={sig}"
        return PresignedUrlInfo(url=url, expires_in_seconds=expires_in_seconds, method="PUT")

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        response_content_disposition: Optional[str] = None,
    ) -> PresignedUrlInfo:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in_seconds
        sig = self._sign(object_key, expires_at)
        url = f"https://storage.local.regulens.internal/documents/download/{object_key}?expires={expires_at}&sig={sig}"
        return PresignedUrlInfo(url=url, expires_in_seconds=expires_in_seconds, method="GET")

    def get_object(self, object_key: str) -> bytes:
        file_path = self._resolve_key(object_key)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Object '{object_key}' does not exist on disk.")
        return file_path.read_bytes()

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        file_path = self._resolve_key(object_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)

    def delete_object(self, object_key: str) -> bool:
        file_path = self._resolve_key(object_key)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
        return False

    def copy_object(self, source_key: str, destination_key: str) -> None:
        data = self.get_object(source_key)
        self.put_object(destination_key, data)

    def move_object(self, source_key: str, destination_key: str) -> None:
        data = self.get_object(source_key)
        self.put_object(destination_key, data)
        self.delete_object(source_key)

    def object_exists(self, object_key: str) -> bool:
        file_path = self._resolve_key(object_key)
        return file_path.exists() and file_path.is_file()

    def get_object_metadata(self, object_key: str) -> StorageObjectMetadata:
        file_path = self._resolve_key(object_key)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Object '{object_key}' does not exist on disk.")
        stat = file_path.stat()
        data = file_path.read_bytes()
        etag = hashlib.md5(data).hexdigest()
        ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return StorageObjectMetadata(
            key=object_key,
            size_bytes=stat.st_size,
            content_type="application/octet-stream",
            etag=etag,
            last_modified=ts,
        )


class S3StorageService(StorageService):
    """S3-compatible object storage provider (AWS S3, MinIO, Cloudflare R2, Google Cloud Storage S3 API)."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        use_ssl: bool = False,
    ):
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.access_key = access_key or settings.S3_ACCESS_KEY
        self.secret_key = secret_key or settings.S3_SECRET_KEY
        self.region = region or settings.S3_REGION
        self.use_ssl = use_ssl
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError:
                raise RuntimeError("boto3 is required for S3StorageService. Install boto3 or use MemoryStorageService.")

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        content_type: Optional[str] = None,
        max_size_bytes: int = 25 * 1024 * 1024,
    ) -> PresignedUrlInfo:
        client = self._get_client()
        params = {"Bucket": self.bucket_name, "Key": object_key}
        if content_type:
            params["ContentType"] = content_type
        url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=expires_in_seconds,
            HttpMethod="PUT",
        )
        return PresignedUrlInfo(
            url=url,
            expires_in_seconds=expires_in_seconds,
            method="PUT",
            headers={"Content-Type": content_type} if content_type else {},
        )

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        response_content_disposition: Optional[str] = None,
    ) -> PresignedUrlInfo:
        client = self._get_client()
        params = {"Bucket": self.bucket_name, "Key": object_key}
        if response_content_disposition:
            params["ResponseContentDisposition"] = response_content_disposition
        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in_seconds,
            HttpMethod="GET",
        )
        return PresignedUrlInfo(
            url=url,
            expires_in_seconds=expires_in_seconds,
            method="GET",
        )

    def get_object(self, object_key: str) -> bytes:
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=object_key)
        return response["Body"].read()

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        client = self._get_client()
        params = {"Bucket": self.bucket_name, "Key": object_key, "Body": data}
        if content_type:
            params["ContentType"] = content_type
        client.put_object(**params)

    def delete_object(self, object_key: str) -> bool:
        client = self._get_client()
        client.delete_object(Bucket=self.bucket_name, Key=object_key)
        return True

    def copy_object(self, source_key: str, destination_key: str) -> None:
        client = self._get_client()
        client.copy_object(
            Bucket=self.bucket_name,
            CopySource={"Bucket": self.bucket_name, "Key": source_key},
            Key=destination_key,
        )

    def move_object(self, source_key: str, destination_key: str) -> None:
        self.copy_object(source_key, destination_key)
        self.delete_object(source_key)

    def object_exists(self, object_key: str) -> bool:
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except Exception:
            return False

    def get_object_metadata(self, object_key: str) -> StorageObjectMetadata:
        client = self._get_client()
        resp = client.head_object(Bucket=self.bucket_name, Key=object_key)
        return StorageObjectMetadata(
            key=object_key,
            size_bytes=resp["ContentLength"],
            content_type=resp.get("ContentType", "application/octet-stream"),
            etag=resp.get("ETag", "").strip('"'),
            last_modified=resp["LastModified"],
        )


# Global storage service instance for dependency injection
_storage_instance: Optional[StorageService] = None
_storage_lock = threading.Lock()


def get_storage_service() -> StorageService:
    """Returns the configured storage service instance."""
    global _storage_instance
    with _storage_lock:
        if _storage_instance is None:
            backend = getattr(settings, "STORAGE_BACKEND", "memory").lower()
            if backend == "local":
                _storage_instance = LocalStorageService(
                    base_path=getattr(settings, "LOCAL_STORAGE_PATH", "./data/storage")
                )
            elif backend == "s3":
                _storage_instance = S3StorageService()
            else:
                _storage_instance = MemoryStorageService()
    return _storage_instance


def set_storage_service(service: StorageService) -> None:
    """Allows test fixtures to inject mock storage."""
    global _storage_instance
    with _storage_lock:
        _storage_instance = service
