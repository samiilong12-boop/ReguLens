"""Unit tests for configuration loading and sensitive field redaction."""
from app.core.config import Settings
from app.core.logging import redact_sensitive_data


def test_settings_defaults():
    settings = Settings()
    assert settings.PROJECT_NAME == "ReguLens API"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.ENVIRONMENT == "development"
    assert "http://localhost:3000" in settings.API_CORS_ORIGINS


def test_secret_redaction_in_logging():
    event_dict = {
        "event": "user_login",
        "password": "secret_password_123",
        "authorization": "Bearer eyJhbGciOi...",
        "user_email": "exporter@example.com",
        "nested": {"token": "secret_token_abc", "safe_field": 42},
    }
    redacted = redact_sensitive_data(None, "info", event_dict)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["user_email"] == "exporter@example.com"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == 42
