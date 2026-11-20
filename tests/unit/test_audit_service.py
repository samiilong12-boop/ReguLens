"""Unit tests for audit logging metadata sanitization."""
import pytest

from app.services.audit import sanitize_audit_details


def test_sanitize_audit_details_redacts_presigned_urls_and_secrets():
    raw_details = {
        "file_name": "clean_certificate.pdf",
        "file_size": 1024,
        "upload_url": "https://storage.regulens.internal/quarantine/upload/abc?sig=secret123",
        "download_url": "https://storage.regulens.internal/documents/download/abc?sig=secret123",
        "presigned_url": "https://s3.amazonaws.com/bucket/key?X-Amz-Signature=secret",
        "token": "bearer_jwt_token_here",
        "password": "super_secret_password",
        "nested": {
            "secret": "confidential",
            "safe_key": "safe_value",
            "link": "https://storage.s3.internal/test?sig=456",
        },
    }

    clean = sanitize_audit_details(raw_details)

    assert clean["file_name"] == "clean_certificate.pdf"
    assert clean["file_size"] == 1024
    assert clean["upload_url"] == "[REDACTED]"
    assert clean["download_url"] == "[REDACTED]"
    assert clean["presigned_url"] == "[REDACTED]"
    assert clean["token"] == "[REDACTED]"
    assert clean["password"] == "[REDACTED]"
    assert clean["nested"]["secret"] == "[REDACTED]"
    assert clean["nested"]["safe_key"] == "safe_value"
    assert clean["nested"]["link"] == "[REDACTED_URL]"
