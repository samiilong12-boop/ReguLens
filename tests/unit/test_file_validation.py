"""Unit tests for magic-byte file signature detection, size limits, and SHA-256 verification."""
import hashlib
import pytest

from app.services.file_validation import (
    detect_mime_type_from_magic_bytes,
    validate_file_content,
    MAX_FILE_SIZE_BYTES,
)

# Sample valid payloads
SAMPLE_PDF = b"%PDF-1.4\n%Demo PDF Content for testing phytosanitary certificate parsing\n%%EOF"
SAMPLE_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
SAMPLE_TIFF_LE = b"II*\x00\x08\x00\x00\x00"
SAMPLE_TIFF_BE = b"MM\x00*\x00\x00\x00\x08"

# Invalid/malicious samples
SAMPLE_EXE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
SAMPLE_HTML = b"<!DOCTYPE html><html><script>alert(1)</script></html>"
SAMPLE_ZIP = b"PK\x03\x04\x14\x00\x00\x00"


def test_detect_mime_type_from_magic_bytes():
    assert detect_mime_type_from_magic_bytes(SAMPLE_PDF) == "application/pdf"
    assert detect_mime_type_from_magic_bytes(SAMPLE_PNG) == "image/png"
    assert detect_mime_type_from_magic_bytes(SAMPLE_JPEG) == "image/jpeg"
    assert detect_mime_type_from_magic_bytes(SAMPLE_TIFF_LE) == "image/tiff"
    assert detect_mime_type_from_magic_bytes(SAMPLE_TIFF_BE) == "image/tiff"

    # Unsupported or deceptive files
    assert detect_mime_type_from_magic_bytes(SAMPLE_EXE) is None
    assert detect_mime_type_from_magic_bytes(SAMPLE_HTML) is None
    assert detect_mime_type_from_magic_bytes(SAMPLE_ZIP) is None
    assert detect_mime_type_from_magic_bytes(b"") is None


def test_validate_file_content_valid_samples():
    # Valid PDF
    res = validate_file_content(SAMPLE_PDF, claimed_mime="application/pdf")
    assert res.is_valid
    assert res.detected_mime == "application/pdf"
    assert res.file_size_bytes == len(SAMPLE_PDF)
    assert res.sha256_hash == hashlib.sha256(SAMPLE_PDF).hexdigest()

    # Valid PNG
    res_png = validate_file_content(SAMPLE_PNG, claimed_mime="image/png")
    assert res_png.is_valid
    assert res_png.detected_mime == "image/png"


def test_validate_file_content_forged_extension_rejected():
    # Executable pretending to be a PDF
    res = validate_file_content(SAMPLE_EXE, claimed_mime="application/pdf")
    assert not res.is_valid
    assert "Unsupported or unrecognized file format" in (res.error_message or "")


def test_validate_file_content_mime_mismatch_rejected():
    # Real PNG submitted with claimed PDF
    res = validate_file_content(SAMPLE_PNG, claimed_mime="application/pdf")
    assert not res.is_valid
    assert "MIME type mismatch" in (res.error_message or "")


def test_validate_file_content_oversized_file_rejected():
    # Mocking oversized data without memory explosion by using a small custom limit
    fake_data = b"%PDF-" + b"0" * 1000
    res = validate_file_content(fake_data, max_size_bytes=500)
    assert not res.is_valid
    assert "exceeds maximum permitted limit" in (res.error_message or "")


def test_validate_file_content_empty_payload_rejected():
    res = validate_file_content(b"")
    assert not res.is_valid
    assert "payload is empty" in (res.error_message or "")


def test_validate_file_content_sha256_matching():
    actual_hash = hashlib.sha256(SAMPLE_PDF).hexdigest()
    # Matching
    res_ok = validate_file_content(SAMPLE_PDF, expected_sha256=actual_hash)
    assert res_ok.is_valid

    # Tampered / Mismatching
    tampered_hash = "f" * 64
    res_bad = validate_file_content(SAMPLE_PDF, expected_sha256=tampered_hash)
    assert not res_bad.is_valid
    assert "SHA-256 checksum mismatch" in (res_bad.error_message or "")
