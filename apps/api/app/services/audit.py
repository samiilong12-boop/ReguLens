"""Append-only audit logging service for document and security events.

In accordance with Package C:
- Enforces append-only audit semantics (INSERT statements only; no UPDATE or DELETE).
- Sanitizes all metadata: never logs presigned URLs, credentials, tokens, or raw payloads.
- Preserves PostgreSQL privileges and RLS tenant boundary constraints.
"""
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
import structlog

logger = structlog.get_logger(__name__)

# Keys strictly forbidden in audit log metadata to prevent credential or URL leakage
FORBIDDEN_METADATA_KEYS = {
    "url",
    "upload_url",
    "download_url",
    "presigned_url",
    "token",
    "jwt",
    "password",
    "secret",
    "authorization",
    "credentials",
    "raw_bytes",
    "payload",
}


def sanitize_audit_details(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitizes audit metadata to prevent leakage of sensitive tokens, presigned URLs, or credentials."""
    if not details:
        return {}

    sanitized: Dict[str, Any] = {}
    for key, value in details.items():
        lower_key = key.lower()
        if any(forbidden in lower_key for forbidden in FORBIDDEN_METADATA_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_audit_details(value)
        elif isinstance(value, str) and ("http://" in value or "https://" in value or "sig=" in value):
            sanitized[key] = "[REDACTED_URL]"
        elif isinstance(value, (bytes, bytearray)):
            sanitized[key] = f"[BINARY_{len(value)}_BYTES]"
        else:
            sanitized[key] = value

    return sanitized


async def log_document_audit_event(
    db: AsyncSession,
    tenant_id: UUID,
    action: str,
    resource_id: UUID,
    user_id: Optional[UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Appends an immutable audit log row within the current tenant transaction.
    
    Security guarantees:
    - Never executes UPDATE or DELETE operations.
    - Sanitizes details against secret, token, and presigned URL leakage.
    - Operates under active transaction context without bypassing RLS.
    """
    clean_details = sanitize_audit_details(details)

    audit_entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type="document",
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=clean_details,
    )
    db.add(audit_entry)
    await db.flush()

    logger.info(
        "document_audit_event_logged",
        action=action,
        document_id=str(resource_id),
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
    )
    return audit_entry
