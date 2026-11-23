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
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4

from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)


class StorageSecurityError(RuntimeError):
    """Raised when storage security controls (transport, bucket privacy, or access policies) are violated."""
    pass


class StoragePayloadTooLargeError(ValueError):
    """Raised when an object payload exceeds maximum permitted storage size."""
    pass


class StorageObjectNotFoundError(FileNotFoundError):
    """Raised when a requested storage object key is not found."""
    pass


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
    fields: Dict[str, str] = field(default_factory=dict)


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

    @property
    def supports_direct_upload(self) -> bool:
        """Indicates whether this storage backend supports genuine provider-level upload-time size enforcement."""
        return True

    @property
    def backend_name(self) -> str:
        """Identifier name of the storage backend."""
        return "unknown"

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
    def get_object(self, object_key: str, max_bytes: Optional[int] = None) -> bytes:
        """Retrieves raw object bytes from storage, bounded by max_bytes."""
        pass

    @abstractmethod
    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        """Stores raw object bytes in storage."""
        pass

    @abstractmethod
    async def stream_upload_object(
        self,
        object_key: str,
        stream: Any,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> int:
        """Streams upload payload directly to quarantine storage with bounded backpressure.

        Enforces hard byte limit on every received chunk and aborts immediately without
        buffering entire payload into memory. Automatically cleans up partial uploads on error.
        Returns total bytes written.
        """
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

    @abstractmethod
    def verify_bucket_configuration(self) -> Dict[str, Any]:
        """Verifies that the private storage bucket exists and enforces required private access controls."""
        pass


class MemoryStorageService(StorageService):
    """In-memory, thread-safe object storage for unit testing and CI."""

    @property
    def backend_name(self) -> str:
        return "memory"

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

    def get_object(self, object_key: str, max_bytes: Optional[int] = None) -> bytes:
        with self._lock:
            if object_key not in self._objects:
                raise StorageObjectNotFoundError(f"Object '{object_key}' does not exist in storage.")
            data = self._objects[object_key][0]
            limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
            if len(data) > limit:
                raise StoragePayloadTooLargeError(
                    f"Object '{object_key}' size ({len(data)} bytes) exceeds maximum permitted limit ({limit} bytes)."
                )
            return data

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        limit = getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
        if len(data) > limit:
            raise StoragePayloadTooLargeError(
                f"Object '{object_key}' size ({len(data)} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        with self._lock:
            ct = content_type or "application/octet-stream"
            self._objects[object_key] = (data, ct, datetime.now(timezone.utc))

    async def stream_upload_object(
        self,
        object_key: str,
        stream: Any,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> int:
        buf = bytearray()
        total_bytes = 0
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)

        try:
            if hasattr(stream, "__aiter__"):
                async for chunk in stream:
                    total_bytes += len(chunk)
                    if total_bytes > limit:
                        raise StoragePayloadTooLargeError(
                            f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                        )
                    buf.extend(chunk)
            else:
                for chunk in stream:
                    total_bytes += len(chunk)
                    if total_bytes > limit:
                        raise StoragePayloadTooLargeError(
                            f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                        )
                    buf.extend(chunk)

            if total_bytes == 0:
                raise ValueError("Uploaded stream payload is empty (0 bytes).")

            with self._lock:
                ct = content_type or "application/octet-stream"
                self._objects[object_key] = (bytes(buf), ct, datetime.now(timezone.utc))
            return total_bytes
        except Exception:
            with self._lock:
                self._objects.pop(object_key, None)
            raise

    def delete_object(self, object_key: str) -> bool:
        with self._lock:
            if object_key in self._objects:
                del self._objects[object_key]
                return True
            return False

    def copy_object(self, source_key: str, destination_key: str) -> None:
        with self._lock:
            if source_key not in self._objects:
                raise StorageObjectNotFoundError(f"Source object '{source_key}' does not exist in storage.")
            data, ct, _ = self._objects[source_key]
            self._objects[destination_key] = (data, ct, datetime.now(timezone.utc))

    def move_object(self, source_key: str, destination_key: str) -> None:
        with self._lock:
            if source_key not in self._objects:
                raise StorageObjectNotFoundError(f"Source object '{source_key}' does not exist in storage.")
            item = self._objects.pop(source_key)
            self._objects[destination_key] = (item[0], item[1], datetime.now(timezone.utc))

    def object_exists(self, object_key: str) -> bool:
        with self._lock:
            return object_key in self._objects

    def get_object_metadata(self, object_key: str) -> StorageObjectMetadata:
        with self._lock:
            if object_key not in self._objects:
                raise StorageObjectNotFoundError(f"Object '{object_key}' does not exist in storage.")
            data, ct, ts = self._objects[object_key]
            etag = hashlib.md5(data).hexdigest()
            return StorageObjectMetadata(
                key=object_key,
                size_bytes=len(data),
                content_type=ct,
                etag=etag,
                last_modified=ts,
            )

    def verify_bucket_configuration(self) -> Dict[str, Any]:
        """In-memory verification for test environments."""
        return {
            "status": "verified",
            "backend": "memory",
            "public_access_blocked": True,
        }

    def clear(self) -> None:
        """Test helper to reset storage between test cases."""
        with self._lock:
            self._objects.clear()


class LocalStorageService(StorageService):
    """Local filesystem storage with path traversal defenses."""

    @property
    def backend_name(self) -> str:
        return "local"

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

    def get_object(self, object_key: str, max_bytes: Optional[int] = None) -> bytes:
        file_path = self._resolve_key(object_key)
        if not file_path.exists() or not file_path.is_file():
            raise StorageObjectNotFoundError(f"Object '{object_key}' does not exist on disk.")
        file_size = file_path.stat().st_size
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
        if file_size > limit:
            raise StoragePayloadTooLargeError(
                f"File '{object_key}' size ({file_size} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        return file_path.read_bytes()

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        limit = getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
        if len(data) > limit:
            raise StoragePayloadTooLargeError(
                f"File '{object_key}' size ({len(data)} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        file_path = self._resolve_key(object_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)

    async def stream_upload_object(
        self,
        object_key: str,
        stream: Any,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> int:
        final_path = self._resolve_key(object_key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = final_path.parent / f".tmp_{uuid4().hex}"
        total_bytes = 0
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)

        try:
            with open(temp_path, "wb") as f:
                if hasattr(stream, "__aiter__"):
                    async for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > limit:
                            raise StoragePayloadTooLargeError(
                                f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                            )
                        f.write(chunk)
                else:
                    for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > limit:
                            raise StoragePayloadTooLargeError(
                                f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                            )
                        f.write(chunk)

            if total_bytes == 0:
                if temp_path.exists():
                    temp_path.unlink()
                raise ValueError("Uploaded stream payload is empty (0 bytes).")

            temp_path.replace(final_path)
            return total_bytes
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            if final_path.exists():
                try:
                    final_path.unlink()
                except OSError:
                    pass
            raise

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
            raise StorageObjectNotFoundError(f"Object '{object_key}' does not exist on disk.")
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

    def verify_bucket_configuration(self) -> Dict[str, Any]:
        """Verifies local directory storage security."""
        if not self.base_path.exists():
            raise StorageSecurityError(f"Local storage path does not exist: {self.base_path}")
        return {
            "status": "verified",
            "backend": "local",
            "public_access_blocked": True,
            "path": str(self.base_path),
        }


class S3StorageService(StorageService):
    """S3-compatible object storage provider (AWS S3, MinIO, Cloudflare R2, Google Cloud Storage S3 API)."""

    @property
    def backend_name(self) -> str:
        return "s3"

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        use_ssl: Optional[bool] = None,
    ):
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.access_key = access_key or settings.S3_ACCESS_KEY
        self.secret_key = secret_key or settings.S3_SECRET_KEY
        self.region = region or settings.S3_REGION
        self.use_ssl = use_ssl if use_ssl is not None else getattr(settings, "S3_USE_SSL", False)
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
        """Generates presigned upload with provider policy enforcing content-length-range and exact object key."""
        client = self._get_client()
        conditions = [
            ["content-length-range", 1, max_size_bytes],
            {"key": object_key},
        ]
        fields = {}
        if content_type:
            conditions.append(["eq", "$Content-Type", content_type])
            fields["Content-Type"] = content_type

        try:
            post_data = client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expires_in_seconds,
            )
            return PresignedUrlInfo(
                url=post_data["url"],
                expires_in_seconds=expires_in_seconds,
                method="POST",
                headers={},
                fields=post_data["fields"],
            )
        except Exception as e:
            logger.error(
                "s3_presigned_post_generation_failed",
                bucket=self.bucket_name,
                object_key=object_key,
                error=str(e),
            )
            raise StorageSecurityError(
                f"Failed to generate secure S3 presigned POST policy with upload-time size enforcement for object '{object_key}': {e}"
            ) from e

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

    def get_object(self, object_key: str, max_bytes: Optional[int] = None) -> bytes:
        """Retrieves object bytes with pre-read size inspection preventing unbounded memory loading."""
        client = self._get_client()
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)

        try:
            head = client.head_object(Bucket=self.bucket_name, Key=object_key)
            size = head.get("ContentLength", 0)
            if size > limit:
                raise StoragePayloadTooLargeError(
                    f"S3 object '{object_key}' size ({size} bytes) exceeds maximum permitted limit ({limit} bytes)."
                )
        except Exception as e:
            if isinstance(e, StoragePayloadTooLargeError):
                raise
            # If head_object fails with 404, let get_object raise or handle below

        response = client.get_object(Bucket=self.bucket_name, Key=object_key)
        content_len = response.get("ContentLength", 0)
        if content_len > limit:
            raise StoragePayloadTooLargeError(
                f"S3 object '{object_key}' size ({content_len} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        return response["Body"].read()

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        limit = getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
        if len(data) > limit:
            raise StoragePayloadTooLargeError(
                f"S3 object '{object_key}' size ({len(data)} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        client = self._get_client()
        params = {"Bucket": self.bucket_name, "Key": object_key, "Body": data}
        if content_type:
            params["ContentType"] = content_type
        client.put_object(**params)

    async def stream_upload_object(
        self,
        object_key: str,
        stream: Any,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> int:
        """Uploads an incoming byte stream to S3 using bounded disk spooling.
        
        Architecture Note:
        Incoming stream chunks are spooled to a restricted temporary file (mode 0600)
        with per-chunk byte limit enforcement to guarantee memory bounds. Once the stream
        completes within the permitted ceiling (<= 25MB), it is uploaded to S3 via put_object.
        The temporary spool file is unlinked in all cases within the finally block.
        """
        import tempfile
        client = self._get_client()
        total_bytes = 0
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)

        fd, raw_temp_path = tempfile.mkstemp(prefix="regulens_s3_spool_", suffix=".tmp")
        try:
            os.chmod(raw_temp_path, 0o600)
        except OSError as chmod_err:
            os.close(fd)
            try:
                Path(raw_temp_path).unlink(missing_ok=True)
            except Exception:
                pass
            raise StorageSecurityError(
                f"Failed to set secure permissions (0600) on temporary spool file: {chmod_err}"
            ) from chmod_err
        os.close(fd)

        temp_path = Path(raw_temp_path)
        try:
            with open(temp_path, "wb") as f:
                if hasattr(stream, "__aiter__"):
                    async for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > limit:
                            raise StoragePayloadTooLargeError(
                                f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                            )
                        f.write(chunk)
                else:
                    for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > limit:
                            raise StoragePayloadTooLargeError(
                                f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                            )
                        f.write(chunk)

            if total_bytes == 0:
                raise ValueError("Uploaded stream payload is empty (0 bytes).")

            with open(temp_path, "rb") as f:
                params = {"Bucket": self.bucket_name, "Key": object_key, "Body": f}
                if content_type:
                    params["ContentType"] = content_type
                client.put_object(**params)
            return total_bytes
        except Exception as e:
            logger.error("s3_stream_upload_failed", object_key=object_key, error=str(e))
            try:
                self.delete_object(object_key)
            except Exception as del_err:
                logger.warning("s3_cleanup_partial_object_failed", object_key=object_key, error=str(del_err))
            raise
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug("s3_temporary_upload_spool_cleaned", path=str(temp_path))
                except OSError as unlink_err:
                    logger.warning("s3_temporary_upload_spool_cleanup_failed", path=str(temp_path), error=str(unlink_err))

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

    def verify_bucket_configuration(self) -> Dict[str, Any]:
        """Verifies S3 bucket existence and public access block security settings."""
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.bucket_name)
        except Exception as e:
            raise StorageSecurityError(
                f"Storage security check failed: Unable to access S3 bucket '{self.bucket_name}': {e}"
            ) from e

        try:
            pab = client.get_public_access_block(Bucket=self.bucket_name)
            cfg = pab.get("PublicAccessBlockConfiguration", {})
            is_blocked = all([
                cfg.get("BlockPublicAcls", False),
                cfg.get("IgnorePublicAcls", False),
                cfg.get("BlockPublicPolicy", False),
                cfg.get("RestrictPublicBuckets", False),
            ])
            if not is_blocked:
                raise StorageSecurityError(
                    f"Storage security violation: S3 bucket '{self.bucket_name}' has incomplete public access block controls: {cfg}"
                )
            return {"status": "verified", "public_access_blocked": True, "configuration": cfg}
        except Exception as e:
            if isinstance(e, StorageSecurityError):
                raise
            raise StorageSecurityError(
                f"Storage security violation: S3 bucket '{self.bucket_name}' has no PublicAccessBlock configured: {e}"
            ) from e


class GCSStorageService(StorageService):
    """Google Cloud Storage (GCS) provider implementing private bucket controls."""

    @property
    def backend_name(self) -> str:
        return "gcs"

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
        credentials_file: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or getattr(settings, "GCS_BUCKET_NAME", "regulens-documents")
        self.project_id = project_id or getattr(settings, "GCS_PROJECT_ID", None)
        self.credentials_file = credentials_file or getattr(settings, "GCS_CREDENTIALS_FILE", None)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError:
                raise RuntimeError(
                    "google-cloud-storage is required for GCSStorageService. Install google-cloud-storage or use MemoryStorageService/S3StorageService."
                )

            if self.credentials_file:
                self._client = storage.Client.from_service_account_json(
                    self.credentials_file, project=self.project_id
                )
            else:
                self._client = storage.Client(project=self.project_id)
        return self._client

    @property
    def supports_direct_upload(self) -> bool:
        """GCS signed PUT URLs cannot enforce content-length-range policies at the upload boundary.
        Direct presigned uploads are disabled for GCS in favor of the authenticated server-mediated
        bounded streaming upload endpoint (/upload-content) which strictly enforces the 25MB ceiling.
        """
        return False

    def generate_presigned_upload_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        content_type: Optional[str] = None,
        max_size_bytes: int = 25 * 1024 * 1024,
    ) -> PresignedUrlInfo:
        raise StorageSecurityError(
            "Direct presigned uploads are disabled for Google Cloud Storage because GCS signed PUT URLs "
            "cannot enforce maximum upload size at the provider boundary. Use the authenticated server-mediated "
            "bounded upload endpoint (/upload-content) to enforce the 25MB upload limit."
        )

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 900,
        response_content_disposition: Optional[str] = None,
    ) -> PresignedUrlInfo:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_key)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in_seconds),
            method="GET",
            response_disposition=response_content_disposition,
        )
        return PresignedUrlInfo(
            url=url,
            expires_in_seconds=expires_in_seconds,
            method="GET",
        )

    def get_object(self, object_key: str, max_bytes: Optional[int] = None) -> bytes:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_key)
        if not blob.exists():
            raise StorageObjectNotFoundError(f"GCS object '{object_key}' does not exist.")
        blob.reload()
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
        if blob.size and blob.size > limit:
            raise StoragePayloadTooLargeError(
                f"GCS object '{object_key}' size ({blob.size} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        return blob.download_as_bytes()

    def put_object(self, object_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        limit = getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)
        if len(data) > limit:
            raise StoragePayloadTooLargeError(
                f"GCS object '{object_key}' size ({len(data)} bytes) exceeds maximum permitted limit ({limit} bytes)."
            )
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_key)
        blob.upload_from_string(data, content_type=content_type)

    async def stream_upload_object(
        self,
        object_key: str,
        stream: Any,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> int:
        """Uploads an incoming byte stream to GCS using bounded disk spooling.
        
        Architecture Note:
        Incoming stream chunks are spooled to a restricted temporary file (mode 0600)
        with per-chunk byte limit enforcement to guarantee memory bounds. Once the stream
        completes within the permitted ceiling (<= 25MB), it is uploaded to GCS via upload_from_filename.
        The temporary spool file is unlinked in all cases within the finally block.
        """
        import tempfile
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_key)
        total_bytes = 0
        limit = max_bytes or getattr(settings, "MAX_DOCUMENT_SIZE_BYTES", 25 * 1024 * 1024)

        fd, raw_temp_path = tempfile.mkstemp(prefix="regulens_gcs_spool_", suffix=".tmp")
        try:
            os.chmod(raw_temp_path, 0o600)
        except OSError as chmod_err:
            os.close(fd)
            try:
                Path(raw_temp_path).unlink(missing_ok=True)
            except Exception:
                pass
            raise StorageSecurityError(
                f"Failed to set secure permissions (0600) on temporary spool file: {chmod_err}"
            ) from chmod_err
        os.close(fd)

        temp_path = Path(raw_temp_path)
        try:
            with open(temp_path, "wb") as f:
                if hasattr(stream, "__aiter__"):
                    async for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > limit:
                            raise StoragePayloadTooLargeError(
                                f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                            )
                        f.write(chunk)
                else:
                    for chunk in stream:
                        total_bytes += len(chunk)
                        if total_bytes > limit:
                            raise StoragePayloadTooLargeError(
                                f"Uploaded stream exceeded maximum permitted limit of {limit} bytes."
                            )
                        f.write(chunk)

            if total_bytes == 0:
                raise ValueError("Uploaded stream payload is empty (0 bytes).")

            blob.upload_from_filename(str(temp_path), content_type=content_type)
            return total_bytes
        except Exception as e:
            logger.error("gcs_stream_upload_failed", object_key=object_key, error=str(e))
            try:
                if blob.exists():
                    blob.delete()
            except Exception as del_err:
                logger.warning("gcs_cleanup_partial_object_failed", object_key=object_key, error=str(del_err))
            raise
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug("gcs_temporary_upload_spool_cleaned", path=str(temp_path))
                except OSError as unlink_err:
                    logger.warning("gcs_temporary_upload_spool_cleanup_failed", path=str(temp_path), error=str(unlink_err))

    def delete_object(self, object_key: str) -> bool:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_key)
        if blob.exists():
            blob.delete()
            return True
        return False

    def copy_object(self, source_key: str, destination_key: str) -> None:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        src_blob = bucket.blob(source_key)
        if not src_blob.exists():
            raise StorageObjectNotFoundError(f"Source GCS object '{source_key}' does not exist.")
        bucket.copy_blob(src_blob, bucket, destination_key)

    def move_object(self, source_key: str, destination_key: str) -> None:
        self.copy_object(source_key, destination_key)
        self.delete_object(source_key)

    def object_exists(self, object_key: str) -> bool:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        return bucket.blob(object_key).exists()

    def get_object_metadata(self, object_key: str) -> StorageObjectMetadata:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_key)
        if not blob.exists():
            raise StorageObjectNotFoundError(f"GCS object '{object_key}' does not exist.")
        blob.reload()
        return StorageObjectMetadata(
            key=object_key,
            size_bytes=blob.size or 0,
            content_type=blob.content_type or "application/octet-stream",
            etag=blob.etag or "",
            last_modified=blob.updated or datetime.now(timezone.utc),
        )

    def verify_bucket_configuration(self) -> Dict[str, Any]:
        """Verifies GCS bucket uniform bucket-level access and private access controls."""
        client = self._get_client()
        try:
            bucket = client.get_bucket(self.bucket_name)
        except Exception as e:
            raise StorageSecurityError(
                f"Storage security check failed: Unable to access GCS bucket '{self.bucket_name}': {e}"
            ) from e

        iam_cfg = getattr(bucket, "iam_configuration", None)
        ubla = getattr(iam_cfg, "uniform_bucket_level_access_enabled", False) if iam_cfg else False
        pap = getattr(iam_cfg, "public_access_prevention", None) if iam_cfg else None

        if not ubla:
            raise StorageSecurityError(
                f"Storage security violation: GCS bucket '{self.bucket_name}' must have Uniform Bucket-Level Access (UBLA) enabled."
            )
        if pap != "enforced":
            raise StorageSecurityError(
                f"Storage security violation: GCS bucket '{self.bucket_name}' must have Public Access Prevention set to 'enforced'."
            )
        return {
            "status": "verified",
            "uniform_bucket_level_access": True,
            "public_access_prevention": "enforced",
        }


# Global storage service instance for dependency injection
_storage_instance: Optional[StorageService] = None
_storage_lock = threading.Lock()


def get_storage_service() -> StorageService:
    """Returns the configured storage service instance.

    Security guarantees:
    - Never silently falls back to MemoryStorageService on unknown types.
    - Prohibits in-memory or local storage in production/staging environments.
    - Strictly enforces persistent private cloud storage ('s3' or 'gcs') in production.
    """
    global _storage_instance
    with _storage_lock:
        if _storage_instance is None:
            raw_backend = getattr(settings, "STORAGE_BACKEND", None)
            if not raw_backend:
                raise ValueError("Storage configuration error: STORAGE_BACKEND is not set.")

            backend = str(raw_backend).strip().lower()
            env = (getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
            is_production = env in {"production", "prod", "staging"}

            if is_production and backend in {"memory", "local"}:
                raise RuntimeError(
                    f"Production security violation: In-memory or local filesystem storage ('{backend}') "
                    "is strictly forbidden in production/staging environments. Must be 's3' or 'gcs'."
                )

            if backend == "local":
                _storage_instance = LocalStorageService(
                    base_path=getattr(settings, "LOCAL_STORAGE_PATH", "./data/storage")
                )
            elif backend == "s3":
                _storage_instance = S3StorageService()
            elif backend == "gcs":
                _storage_instance = GCSStorageService()
            elif backend == "memory":
                _storage_instance = MemoryStorageService()
            else:
                raise ValueError(
                    f"Unknown storage backend: '{raw_backend}'. Supported backends: ['s3', 'gcs', 'local', 'memory']."
                )
    return _storage_instance


def set_storage_service(service: StorageService) -> None:
    """Allows test fixtures to inject mock storage."""
    global _storage_instance
    with _storage_lock:
        _storage_instance = service
