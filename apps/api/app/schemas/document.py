"""Pydantic schemas for Document upload, validation, and retrieval."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.file_validation import APPROVED_MIME_TYPES, MAX_FILE_SIZE_BYTES


class DocumentUploadInitiateRequest(BaseModel):
    """Payload to request a presigned upload URL."""
    file_name: str = Field(..., min_length=1, max_length=255, description="Original filename for display")
    expected_size_bytes: int = Field(..., ge=1, le=MAX_FILE_SIZE_BYTES, description="Expected file size (max 25MB)")
    claimed_mime_type: str = Field(..., description="Claimed MIME type (must be in approved allowlist)")
    document_type: str = Field(..., min_length=1, max_length=64, description="Regulatory document classification")
    consignment_id: Optional[UUID] = Field(None, description="Optional consignment association")
    expected_sha256: Optional[str] = Field(None, min_length=64, max_length=64, description="Optional expected SHA-256")

    @field_validator("claimed_mime_type")
    @classmethod
    def validate_mime(cls, v: str) -> str:
        norm = v.strip().lower()
        if norm not in APPROVED_MIME_TYPES:
            raise ValueError(f"MIME type '{v}' is not supported. Approved types: {', '.join(sorted(APPROVED_MIME_TYPES))}")
        return norm


class DocumentUploadInitiateResponse(BaseModel):
    """Presigned upload URL and quarantine details."""
    document_id: UUID
    upload_url: str
    expires_in_seconds: int = 900
    quarantine_key: str
    status: str
    created_at: datetime
    upload_method: str = "PUT"
    upload_fields: Optional[dict] = None


class DocumentFinalizeRequest(BaseModel):
    """Optional payload when finalizing and triggering validation."""
    expected_sha256: Optional[str] = Field(None, min_length=64, max_length=64)


class DocumentResponse(BaseModel):
    """Document metadata details."""
    id: UUID
    tenant_id: UUID
    consignment_id: Optional[UUID] = None
    document_type: str
    file_name: str
    file_size_bytes: int
    mime_type: str
    status: str
    antivirus_status: str
    sha256_hash: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    validated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentDownloadResponse(BaseModel):
    """Authorized presigned download details."""
    document_id: UUID
    download_url: str
    expires_in_seconds: int = 900
    file_name: str
    mime_type: str
    sha256_hash: str


class DocumentListResponse(BaseModel):
    """List of tenant documents."""
    items: List[DocumentResponse]
    total: int
