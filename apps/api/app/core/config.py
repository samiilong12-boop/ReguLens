"""Application configuration management using Pydantic Settings.

Secrets are strictly read from environment variables.
"""
from typing import List
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

    # Object Storage
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "regulens-documents"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

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
        else:
            # Non-production: if bypass is requested, ensure environment is strictly 'development'
            if self.ALLOW_DEV_TENANT_BYPASS and env != "development":
                raise ValueError(
                    "Security configuration error: ALLOW_DEV_TENANT_BYPASS is only permitted in 'development' environment."
                )

        return self


settings = Settings()
