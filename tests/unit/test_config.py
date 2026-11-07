"""Unit tests for configuration loading, security validation, and sensitive field redaction."""
import pytest
from app.core.config import Settings, DEV_DEFAULT_JWT_SECRET
from app.core.logging import redact_sensitive_data


def test_settings_defaults():
    settings = Settings()
    assert settings.PROJECT_NAME == "ReguLens API"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.ENVIRONMENT == "development"
    assert "http://localhost:3000" in settings.API_CORS_ORIGINS
    assert settings.ALLOW_DEV_TENANT_BYPASS is False


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


def test_production_fails_with_default_jwt_secret():
    """Production must fail startup if JWT secret equals development default."""
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=DEV_DEFAULT_JWT_SECRET,
        )
    err_msg = str(excinfo.value)
    assert "Production startup failed" in err_msg
    assert "default development secret in production is strictly forbidden" in err_msg
    # Ensure secret itself is not leaked in exception
    assert DEV_DEFAULT_JWT_SECRET not in err_msg


def test_production_fails_with_weak_jwt_secret():
    """Production must fail startup if JWT secret length is under 32 characters."""
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="too_short_secret",
        )
    err_msg = str(excinfo.value)
    assert "Production startup failed" in err_msg
    assert "at least 32 characters" in err_msg
    assert "too_short_secret" not in err_msg


def test_production_succeeds_with_strong_unique_jwt_secret():
    """Production succeeds when provided with a strong 32+ character unique secret."""
    strong_secret = "a" * 32 + "_production_unique_entropy_key_12345"
    settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=strong_secret,
        ALLOW_DEV_TENANT_BYPASS=False,
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.JWT_SECRET_KEY == strong_secret


def test_production_blocks_dev_tenant_bypass():
    """Production must never allow dev tenant bypass flag."""
    strong_secret = "b" * 32 + "_production_unique_entropy_key_67890"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            ALLOW_DEV_TENANT_BYPASS=True,
        )
    assert "ALLOW_DEV_TENANT_BYPASS cannot be enabled in a production environment" in str(excinfo.value)


def test_missing_or_ambiguous_environment_fails_closed():
    """Environment configuration must fail closed if missing or empty."""
    with pytest.raises(ValueError) as excinfo:
        Settings(ENVIRONMENT="")
    assert "Environment configuration is missing or ambiguous" in str(excinfo.value)


def test_production_fails_when_check_db_role_on_startup_disabled():
    """Production startup must fail closed if CHECK_DB_ROLE_ON_STARTUP is set to False."""
    strong_secret = "c" * 32 + "_production_unique_entropy_key_check_db"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            CHECK_DB_ROLE_ON_STARTUP=False,
        )
    assert "CHECK_DB_ROLE_ON_STARTUP cannot be disabled in production/staging environments" in str(excinfo.value)


def test_staging_fails_when_check_db_role_on_startup_disabled():
    """Staging startup must fail closed if CHECK_DB_ROLE_ON_STARTUP is set to False."""
    strong_secret = "d" * 32 + "_staging_unique_entropy_key_check_db"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="staging",
            JWT_SECRET_KEY=strong_secret,
            CHECK_DB_ROLE_ON_STARTUP=False,
        )
    assert "CHECK_DB_ROLE_ON_STARTUP cannot be disabled in production/staging environments" in str(excinfo.value)


def test_empty_or_whitespace_expected_db_runtime_role_rejected():
    """Empty or whitespace EXPECTED_DB_RUNTIME_ROLE must be rejected across all environments."""
    with pytest.raises(ValueError) as excinfo:
        Settings(EXPECTED_DB_RUNTIME_ROLE="")
    assert "EXPECTED_DB_RUNTIME_ROLE cannot be empty or whitespace" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        Settings(EXPECTED_DB_RUNTIME_ROLE="   ")
    assert "EXPECTED_DB_RUNTIME_ROLE cannot be empty or whitespace" in str(excinfo.value)


def test_privileged_roles_rejected_as_expected_runtime_role():
    """Privileged roles 'postgres' and 'regulens_migrator' cannot be set as EXPECTED_DB_RUNTIME_ROLE."""
    with pytest.raises(ValueError) as excinfo:
        Settings(EXPECTED_DB_RUNTIME_ROLE="postgres")
    assert "Privileged role 'postgres' cannot be configured" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        Settings(EXPECTED_DB_RUNTIME_ROLE="regulens_migrator")
    assert "Privileged role 'regulens_migrator' cannot be configured" in str(excinfo.value)


def test_production_rejects_non_regulens_app_expected_runtime_role():
    """Production must reject any expected role other than 'regulens_app'."""
    strong_secret = "e" * 32 + "_production_unique_entropy_key_role_name"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            EXPECTED_DB_RUNTIME_ROLE="custom_app_role",
        )
    assert "EXPECTED_DB_RUNTIME_ROLE in production must be 'regulens_app'" in str(excinfo.value)


def test_development_allows_check_db_role_on_startup_false_if_explicitly_configured():
    """Development environment permits disabling CHECK_DB_ROLE_ON_STARTUP for testing."""
    dev_settings = Settings(
        ENVIRONMENT="development",
        CHECK_DB_ROLE_ON_STARTUP=False,
    )
    assert dev_settings.CHECK_DB_ROLE_ON_STARTUP is False


