"""Application configuration management using Pydantic Settings.

Secrets are strictly read from environment variables.
"""
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    DEBUG: bool = Field(default=False)

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

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(
        default="dev_secret_key_minimum_32_characters_long_for_security_testing_only"
    )
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


settings = Settings()
