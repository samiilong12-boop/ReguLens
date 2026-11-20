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
        STORAGE_BACKEND="s3",
        S3_USE_SSL=True,
        S3_ENDPOINT_URL="https://s3.eu-central-1.amazonaws.com",
        S3_BUCKET_NAME="prod-regulens-docs",
        MALWARE_SCANNER_TYPE="clamav",
        CLAMAV_HOST="clamav.internal",
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


# ==============================================================================
# Package C: Storage & Malware Scanner Production Fail-Closed Tests
# ==============================================================================

def test_unknown_storage_backend_rejected_across_all_environments():
    """Unknown storage backend names must raise ValueError immediately."""
    with pytest.raises(ValueError) as excinfo:
        Settings(STORAGE_BACKEND="unsupported_azure_blob")
    assert "Unknown STORAGE_BACKEND 'unsupported_azure_blob'" in str(excinfo.value)


def test_unknown_malware_scanner_type_rejected_across_all_environments():
    """Unknown malware scanner types must raise ValueError immediately."""
    with pytest.raises(ValueError) as excinfo:
        Settings(MALWARE_SCANNER_TYPE="unsupported_kaspersky")
    assert "Unknown MALWARE_SCANNER_TYPE 'unsupported_kaspersky'" in str(excinfo.value)


def test_production_rejects_memory_storage_backend():
    """Production must fail closed if in-memory storage is configured."""
    strong_secret = "f" * 32 + "_production_unique_entropy_key_memory"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="memory",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="clamav.internal",
        )
    assert "Non-persistent storage backend 'memory' is strictly forbidden in production" in str(excinfo.value)


def test_production_rejects_local_storage_backend():
    """Production must fail closed if local filesystem storage is configured."""
    strong_secret = "g" * 32 + "_production_unique_entropy_key_local"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="local",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="clamav.internal",
        )
    assert "Non-persistent storage backend 'local' is strictly forbidden in production" in str(excinfo.value)


def test_production_rejects_mock_malware_scanner():
    """Production must fail closed if MockMalwareScanner is configured."""
    strong_secret = "h" * 32 + "_production_unique_entropy_key_mock_scan"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="s3",
            S3_USE_SSL=True,
            S3_ENDPOINT_URL="https://s3.eu-central-1.amazonaws.com",
            S3_BUCKET_NAME="prod-regulens-docs",
            MALWARE_SCANNER_TYPE="mock",
        )
    assert "MockMalwareScanner is strictly forbidden in production" in str(excinfo.value)


def test_production_rejects_s3_without_ssl():
    """Production must fail closed if S3_USE_SSL is False."""
    strong_secret = "i" * 32 + "_production_unique_entropy_key_ssl"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="s3",
            S3_USE_SSL=False,
            S3_ENDPOINT_URL="https://s3.eu-central-1.amazonaws.com",
            S3_BUCKET_NAME="prod-regulens-docs",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="clamav.internal",
        )
    assert "S3_USE_SSL must be True in production/staging" in str(excinfo.value)


def test_production_rejects_s3_insecure_http_endpoint():
    """Production must fail closed if S3_ENDPOINT_URL uses insecure http://."""
    strong_secret = "j" * 32 + "_production_unique_entropy_key_http"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="s3",
            S3_USE_SSL=True,
            S3_ENDPOINT_URL="http://s3.eu-central-1.amazonaws.com",
            S3_BUCKET_NAME="prod-regulens-docs",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="clamav.internal",
        )
    assert "Insecure HTTP endpoint URL is strictly forbidden in production/staging" in str(excinfo.value)


def test_production_requires_s3_bucket_name():
    """Production must fail closed if S3_BUCKET_NAME is empty."""
    strong_secret = "k" * 32 + "_production_unique_entropy_key_bucket"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="s3",
            S3_USE_SSL=True,
            S3_ENDPOINT_URL="https://s3.eu-central-1.amazonaws.com",
            S3_BUCKET_NAME="",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="clamav.internal",
        )
    assert "S3_BUCKET_NAME must be explicitly configured" in str(excinfo.value)


def test_production_requires_gcs_bucket_name():
    """Production must fail closed if GCS_BUCKET_NAME is empty when GCS backend is selected."""
    strong_secret = "l" * 32 + "_production_unique_entropy_key_gcs"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="gcs",
            GCS_BUCKET_NAME="",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="clamav.internal",
        )
    assert "GCS_BUCKET_NAME must be explicitly configured" in str(excinfo.value)


def test_production_requires_clamav_host():
    """Production must fail closed if CLAMAV_HOST is empty when ClamAV scanner is selected."""
    strong_secret = "m" * 32 + "_production_unique_entropy_key_clamav"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=strong_secret,
            STORAGE_BACKEND="s3",
            S3_USE_SSL=True,
            S3_ENDPOINT_URL="https://s3.eu-central-1.amazonaws.com",
            S3_BUCKET_NAME="prod-regulens-docs",
            MALWARE_SCANNER_TYPE="clamav",
            CLAMAV_HOST="",
        )
    assert "CLAMAV_HOST must be explicitly configured" in str(excinfo.value)


def test_production_succeeds_with_valid_s3_and_clamav_configuration():
    """Production startup succeeds when strong JWT, S3 over HTTPS with SSL, and ClamAV are configured."""
    strong_secret = "n" * 32 + "_production_unique_entropy_key_valid"
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=strong_secret,
        STORAGE_BACKEND="s3",
        S3_USE_SSL=True,
        S3_ENDPOINT_URL="https://s3.eu-central-1.amazonaws.com",
        S3_BUCKET_NAME="prod-regulens-docs",
        MALWARE_SCANNER_TYPE="clamav",
        CLAMAV_HOST="clamav.production.internal",
        CLAMAV_PORT=3310,
    )
    assert prod_settings.STORAGE_BACKEND == "s3"
    assert prod_settings.S3_USE_SSL is True
    assert prod_settings.MALWARE_SCANNER_TYPE == "clamav"


def test_production_succeeds_with_valid_gcs_and_clamav_configuration():
    """Production startup succeeds when strong JWT, GCS, and ClamAV are configured."""
    strong_secret = "o" * 32 + "_production_unique_entropy_key_gcs_valid"
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=strong_secret,
        STORAGE_BACKEND="gcs",
        GCS_BUCKET_NAME="prod-regulens-gcs-docs",
        MALWARE_SCANNER_TYPE="clamav",
        CLAMAV_HOST="clamav.production.internal",
        CLAMAV_PORT=3310,
    )
    assert prod_settings.STORAGE_BACKEND == "gcs"
    assert prod_settings.MALWARE_SCANNER_TYPE == "clamav"

