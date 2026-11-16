"""File validation service enforcing magic-byte inspection, size limits, and SHA-256 checksums.

In accordance with Package C:
- Never trusts file extensions, client-provided MIME types, or client-reported file sizes.
- Strict 25 MB maximum file size limit.
- Whitelist of approved trade document MIME types: PDF, PNG, JPEG, TIFF.
- Server-side SHA-256 calculation and verification.
"""
from dataclasses import dataclass
import hashlib
from typing import Dict, List, Optional, Set

from app.core.config import settings

# Approved MIME types for trade consignments (phytosanitary certs, lab reports, invoices, EUR.1, apparel specs)
APPROVED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
}

MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB = 26,214,400 bytes

# Magic bytes (file signatures) mapping
MAGIC_SIGNATURES: Dict[str, List[bytes]] = {
    "application/pdf": [b"%PDF-"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/tiff": [b"II*\x00", b"MM\x00*"],  # Little-endian (Intel) & Big-endian (Motorola)
}


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of server-side file inspection."""
    is_valid: bool
    detected_mime: Optional[str]
    file_size_bytes: int
    sha256_hash: str
    error_message: Optional[str] = None


def detect_mime_type_from_magic_bytes(data: bytes) -> Optional[str]:
    """Detects MIME type strictly by inspecting magic bytes/file signature at head of stream.
    
    Security: Client-supplied Content-Type headers and file extensions are completely ignored.
    """
    if not data or len(data) < 3:
        return None

    # Check PDF (%PDF-)
    if data.startswith(b"%PDF-"):
        return "application/pdf"

    # Check PNG (\x89PNG\r\n\x1a\n)
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # Check JPEG (\xff\xd8\xff)
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # Check TIFF (II*\x00 or MM\x00*)
    if len(data) >= 4 and (data.startswith(b"II*\x00") or data.startswith(b"MM\x00*")):
        return "image/tiff"

    return None


def validate_file_content(
    data: bytes,
    claimed_mime: Optional[str] = None,
    expected_sha256: Optional[str] = None,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> ValidationResult:
    """Performs rigorous server-side verification of raw file payload.
    
    Enforces:
    1. Size > 0 and Size <= 25 MB.
    2. Magic bytes match an approved MIME type.
    3. If claimed_mime provided, actual detected MIME must match.
    4. Computes SHA-256 and verifies against expected_sha256 if supplied.
    """
    size = len(data)
    sha256_hash = hashlib.sha256(data).hexdigest()

    if size == 0:
        return ValidationResult(
            is_valid=False,
            detected_mime=None,
            file_size_bytes=0,
            sha256_hash=sha256_hash,
            error_message="Uploaded file payload is empty (0 bytes).",
        )

    if size > max_size_bytes:
        return ValidationResult(
            is_valid=False,
            detected_mime=None,
            file_size_bytes=size,
            sha256_hash=sha256_hash,
            error_message=f"File size ({size} bytes) exceeds maximum permitted limit of {max_size_bytes} bytes (25 MB).",
        )

    detected_mime = detect_mime_type_from_magic_bytes(data)
    if not detected_mime or detected_mime not in APPROVED_MIME_TYPES:
        return ValidationResult(
            is_valid=False,
            detected_mime=detected_mime,
            file_size_bytes=size,
            sha256_hash=sha256_hash,
            error_message=(
                f"Unsupported or unrecognized file format. Detected MIME: '{detected_mime}'. "
                f"Approved formats: {', '.join(sorted(APPROVED_MIME_TYPES))}."
            ),
        )

    if claimed_mime:
        normalized_claimed = claimed_mime.strip().lower()
        if normalized_claimed != detected_mime:
            return ValidationResult(
                is_valid=False,
                detected_mime=detected_mime,
                file_size_bytes=size,
                sha256_hash=sha256_hash,
                error_message=(
                    f"MIME type mismatch: Client claimed '{claimed_mime}', "
                    f"but server magic-byte inspection detected '{detected_mime}'."
                ),
            )

    if expected_sha256:
        normalized_expected = expected_sha256.strip().lower()
        if normalized_expected != sha256_hash.lower():
            return ValidationResult(
                is_valid=False,
                detected_mime=detected_mime,
                file_size_bytes=size,
                sha256_hash=sha256_hash,
                error_message=(
                    f"SHA-256 checksum mismatch: Client expected '{expected_sha256}', "
                    f"computed hash is '{sha256_hash}'."
                ),
            )

    return ValidationResult(
        is_valid=True,
        detected_mime=detected_mime,
        file_size_bytes=size,
        sha256_hash=sha256_hash,
        error_message=None,
    )
