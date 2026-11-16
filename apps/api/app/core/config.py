"""Application configuration management using Pydantic Settings.

Secrets are strictly read from environment variables.
"""
from typing import List, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_DEFAULT_JWT_SECRET = "dev_secret_key_minimum_32_characters_long_for_security_testing_only"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Environment
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    DEBUG: bool = Field(default=False)

    # Security & Development Flags
    # Strictly disabled in production. Even in development, defaults to False.
    ALLOW_DEV_TENANT_BYPASS: bool = Field(default=False)

    # API Server
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ReguLens API"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://regulens_app:regulens_pass@localhost:5432/regulens_dev"
    )
    DATABASE_MIGRATION_URL: str = Field(
        default="postgresql+asyncpg://regulens_migrator:regulens_admin_pass@localhost:5432/regulens_dev"
    )
    EXPECTED_DB_RUNTIME_ROLE: str = Field(default="regulens_app")
    CHECK_DB_ROLE_ON_STARTUP: bool = Field(default=True)

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(default=DEV_DEFAULT_JWT_SECRET)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Object Storage & Upload Security (Package C)
    STORAGE_BACKEND: str = Field(default="memory")  # "memory", "local", "s3", "gcs"
    LOCAL_STORAGE_PATH: str = Field(default="./data/storage")
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "regulens-documents"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    MAX_DOCUMENT_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB strict limit
    PRESIGNED_URL_EXPIRE_SECONDS: int = 900  # 15 minutes strict expiry

    # Google Cloud Storage Configuration (Package C - GCP Compatibility)
    GCS_BUCKET_NAME: str = "regulens-documents"
    GCS_PROJECT_ID: Optional[str] = None
    GCS_CREDENTIALS_FILE: Optional[str] = None

    # Malware Scanner Configuration (Package C)
    MALWARE_SCANNER_TYPE: str = Field(default="mock")  # "mock", "clamav"
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: float = 5.0

    # AI Integration Boundary
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        env = (self.ENVIRONMENT or "").strip().lower()
        is_production = env in {"production", "prod", "staging"}

        # Fail closed if environment is missing or ambiguous
        if not env:
            raise ValueError("Environment configuration is missing or ambiguous. System fails closed.")

        # Validate EXPECTED_DB_RUNTIME_ROLE across all environments
        expected_role = (self.EXPECTED_DB_RUNTIME_ROLE or "").strip()
        if not expected_role:
            raise ValueError(
                "Database security configuration error: EXPECTED_DB_RUNTIME_ROLE cannot be empty or whitespace."
            )
        if expected_role in {"postgres", "regulens_migrator"}:
            raise ValueError(
                f"Database security configuration error: Privileged role '{expected_role}' cannot be configured as EXPECTED_DB_RUNTIME_ROLE."
            )

        # Validate storage backend across all environments
        storage_backend = (self.STORAGE_BACKEND or "").strip().lower()
        valid_storage_backends = {"memory", "local", "s3", "gcs"}
        if storage_backend not in valid_storage_backends:
            raise ValueError(
                f"Storage configuration error: Unknown STORAGE_BACKEND '{self.STORAGE_BACKEND}'. "
                f"Must be one of: {sorted(valid_storage_backends)}."
            )

        # Validate malware scanner type across all environments
        scanner_type = (self.MALWARE_SCANNER_TYPE or "").strip().lower()
        valid_scanner_types = {"mock", "clamav"}
        if scanner_type not in valid_scanner_types:
            raise ValueError(
                f"Malware scanner configuration error: Unknown MALWARE_SCANNER_TYPE '{self.MALWARE_SCANNER_TYPE}'. "
                f"Must be one of: {sorted(valid_scanner_types)}."
            )

        if is_production:
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == DEV_DEFAULT_JWT_SECRET:
                raise ValueError(
                    "Production startup failed: JWT_SECRET_KEY must be explicitly set to a unique secret. "
                    "Use of the default development secret in production is strictly forbidden."
                )
            if len(self.JWT_SECRET_KEY) < MIN_JWT_SECRET_LENGTH:
                raise ValueError(
                    f"Production startup failed: JWT_SECRET_KEY length must be at least {MIN_JWT_SECRET_LENGTH} characters."
                )
            if self.ALLOW_DEV_TENANT_BYPASS:
                raise ValueError(
                    "Production startup failed: ALLOW_DEV_TENANT_BYPASS cannot be enabled in a production environment."
                )
            if not self.CHECK_DB_ROLE_ON_STARTUP:
                raise ValueError(
                    "Production startup failed: CHECK_DB_ROLE_ON_STARTUP cannot be disabled in production/staging environments."
                )
            if expected_role != "regulens_app":
                raise ValueError(
                    f"Production startup failed: EXPECTED_DB_RUNTIME_ROLE in production must be 'regulens_app', got '{expected_role}'."
                )

            # Strict production storage requirements (Package C)
            if storage_backend in {"memory", "local"}:
                raise ValueError(
                    f"Production startup failed: Non-persistent storage backend '{storage_backend}' is strictly forbidden "
                    "in production/staging environments. A persistent private cloud backend ('s3' or 'gcs') must be configured."
                )

            if storage_backend == "s3":
                if not self.S3_USE_SSL:
                    raise ValueError(
                        "Production startup failed: S3_USE_SSL must be True in production/staging environments to enforce encrypted transport."
                    )
                if self.S3_ENDPOINT_URL and self.S3_ENDPOINT_URL.strip().lower().startswith("http://"):
                    raise ValueError(
                        "Production startup failed: Insecure HTTP endpoint URL is strictly forbidden in production/staging. S3_ENDPOINT_URL must use https://."
                    )
                if not (self.S3_BUCKET_NAME or "").strip():
                    raise ValueError(
                        "Production startup failed: S3_BUCKET_NAME must be explicitly configured."
                    )

            if storage_backend == "gcs":
                if not (self.GCS_BUCKET_NAME or "").strip():
                    raise ValueError(
                        "Production startup failed: GCS_BUCKET_NAME must be explicitly configured."
                    )

            # Strict production malware scanner requirements (Package C)
            if scanner_type == "mock":
                raise ValueError(
                    "Production startup failed: MockMalwareScanner is strictly forbidden in production/staging environments. "
                    "A real, operational malware scanner (such as 'clamav') must be explicitly configured."
                )
            if scanner_type == "clamav":
                if not (self.CLAMAV_HOST or "").strip():
                    raise ValueError(
                        "Production startup failed: CLAMAV_HOST must be explicitly configured for real malware scanning."
                    )
        else:
            # Non-production: if bypass is requested, ensure environment is strictly 'development'
            if self.ALLOW_DEV_TENANT_BYPASS and env != "development":
                raise ValueError(
                    "Security configuration error: ALLOW_DEV_TENANT_BYPASS is only permitted in 'development' environment."
                )

        return self


settings = Settings()
