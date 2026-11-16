"""Quarantine retention cleanup service for abandoned document uploads.

In accordance with Package C, Security Architecture, and Data Retention Policy:
- Purges unfinalized, abandoned quarantine storage objects older than cutoff window (default: 24 hours).
- Protects active uploads (younger than cutoff window) from deletion.
- Operates strictly under authorized tenant and user context via unprivileged regulens_app role.
- Enforces live role-based authorization (requiring OWNER or ADMIN role).
- Rejects non-member, deactivated, or unauthorized actors fail-closed.
- Validates cutoff_hours (rejecting non-positive or unreasonable values).
- Validates storage key prefix (must start with tenants/{tenant_id}/quarantine/).
- Emits sanitized audit events for every purged object without leaking secrets or URLs.
- Operates within database transactions without bypassing RLS (NOBYPASSRLS).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.models import Document, Tenant, TenantUser, User
from app.db.session import set_tenant_context, set_user_context
from app.services.audit import log_document_audit_event
from app.services.storage import StorageService, get_storage_service

logger = structlog.get_logger(__name__)


@dataclass
class CleanupReport:
    """Outcome report for quarantine retention cleanup."""
    cutoff_timestamp: datetime
    tenant_id: UUID
    scanned_count: int = 0
    purged_count: int = 0
    purged_document_ids: List[UUID] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


async def purge_abandoned_quarantine_objects(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: UUID,
    storage_service: Optional[StorageService] = None,
    cutoff_hours: int = 24,
) -> CleanupReport:
    """Identifies and purges expired, abandoned quarantine objects for a specific tenant.
    
    Security invariants:
    1. Rejects missing, invalid, or non-positive cutoff_hours.
    2. Requires valid tenant_id and actor_user_id.
    3. Validates actor user exists and is active.
    4. Establishes transaction-scoped user and tenant context (set_user_context, set_tenant_context).
    5. Validates tenant exists and is active.
    6. Validates actor membership and requires OWNER or ADMIN role (rejects VIEWER / unauthorized).
    7. Only selects documents belonging to the tenant in 'PENDING_UPLOAD' or 'QUARANTINED' status.
    8. Only selects records created strictly before the cutoff timestamp (cutoff_hours ago).
    9. Validates object key path matches tenants/{tenant_id}/quarantine/ before deletion.
    10. Active uploads (< cutoff_hours old) are strictly preserved.
    11. Emits sanitized audit events for every purged object.
    """
    # 1. Validate cutoff_hours
    if cutoff_hours is None or cutoff_hours <= 0:
        raise ValueError("cutoff_hours must be a positive integer greater than 0.")
    if cutoff_hours > 24 * 365:
        raise ValueError("cutoff_hours cannot exceed 1 year (8760 hours).")

    # 2. Validate tenant_id and actor_user_id
    if not tenant_id:
        raise ValueError("tenant_id is required for tenant-scoped quarantine cleanup.")
    if not actor_user_id:
        raise ValueError("actor_user_id is required for authorized audit logging and role validation.")

    if not isinstance(tenant_id, UUID):
        try:
            tenant_id = UUID(str(tenant_id))
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid tenant_id format; must be a valid UUID: {tenant_id}")

    if not isinstance(actor_user_id, UUID):
        try:
            actor_user_id = UUID(str(actor_user_id))
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid actor_user_id format; must be a valid UUID: {actor_user_id}")

    # 3. Verify actor user status (global table, unprivileged SELECT)
    stmt_user = select(User.is_active).where(User.id == actor_user_id)
    user_active = (await db.execute(stmt_user)).scalar_one_or_none()
    if user_active is None:
        raise PermissionError(f"Actor user '{actor_user_id}' does not exist.")
    if not user_active:
        raise PermissionError(f"Actor user '{actor_user_id}' account is deactivated.")

    # 4. Establish transaction-scoped user and tenant context
    await set_user_context(db, actor_user_id)
    await set_tenant_context(db, tenant_id)

    # 5. Verify tenant organization status
    stmt_tenant = select(Tenant.is_active).where(Tenant.id == tenant_id)
    tenant_active = (await db.execute(stmt_tenant)).scalar_one_or_none()
    if tenant_active is None:
        raise PermissionError(f"Target tenant organization '{tenant_id}' does not exist.")
    if not tenant_active:
        raise PermissionError(f"Target tenant organization '{tenant_id}' is inactive or suspended.")

    # 6. Verify live actor membership and role in target tenant
    stmt_role = select(TenantUser.role).where(
        TenantUser.tenant_id == tenant_id,
        TenantUser.user_id == actor_user_id,
    )
    current_role = (await db.execute(stmt_role)).scalar_one_or_none()
    if current_role is None:
        raise PermissionError(
            f"User '{actor_user_id}' is not an active member of tenant organization '{tenant_id}'."
        )
    if current_role not in ("OWNER", "ADMIN"):
        raise PermissionError(
            f"User role '{current_role}' is not authorized to execute quarantine cleanup. "
            f"Requires OWNER or ADMIN role."
        )

    # 7. Initialize storage and cutoff
    storage = storage_service or get_storage_service()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=cutoff_hours)
    report = CleanupReport(cutoff_timestamp=cutoff, tenant_id=tenant_id)

    expected_prefix = f"tenants/{tenant_id}/quarantine/"

    # 8. Query eligible expired records for this tenant
    stmt = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.status.in_(["PENDING_UPLOAD", "QUARANTINED"]),
        Document.created_at < cutoff,
        Document.quarantine_key.is_not(None),
    )
    result = await db.execute(stmt)
    expired_documents = result.scalars().all()
    report.scanned_count = len(expired_documents)

    for doc in expired_documents:
        q_key = doc.quarantine_key
        doc_id = doc.id

        # Safety check: ensure quarantine key belongs to tenant prefix
        if not q_key.startswith(expected_prefix):
            err_msg = (
                f"Security anomaly: Quarantine key '{q_key}' for document {doc_id} "
                f"does not match expected tenant prefix '{expected_prefix}'. Skipping."
            )
            logger.error("quarantine_purge_prefix_mismatch", document_id=str(doc_id), key=q_key)
            report.errors.append(err_msg)
            continue

        try:
            # Delete from storage backend if object exists
            if storage.object_exists(q_key):
                storage.delete_object(q_key)

            # Update document metadata
            doc.quarantine_key = None
            doc.status = "EXPIRED"
            doc.rejection_reason = (
                f"Quarantine object purged: upload was abandoned and exceeded the {cutoff_hours}-hour retention window."
            )

            # Log sanitized audit event
            await log_document_audit_event(
                db=db,
                tenant_id=tenant_id,
                action="DOCUMENT_QUARANTINE_PURGED",
                resource_id=doc_id,
                user_id=actor_user_id,
                details={
                    "reason": doc.rejection_reason,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "cutoff_hours": cutoff_hours,
                    "purged_quarantine_key": q_key,
                },
            )

            report.purged_count += 1
            report.purged_document_ids.append(doc_id)

            logger.info(
                "quarantine_object_purged",
                document_id=str(doc_id),
                tenant_id=str(tenant_id),
                cutoff_hours=cutoff_hours,
            )
        except Exception as e:
            err_msg = f"Failed to purge quarantine for document {doc_id}: {e}"
            logger.error("quarantine_purge_failed", document_id=str(doc_id), error=str(e))
            report.errors.append(err_msg)

    await db.commit()
    return report


if __name__ == "__main__":
    import argparse
    import asyncio
    import sys
    from app.db.session import async_session_maker

    parser = argparse.ArgumentParser(
        description="Purge abandoned quarantine document uploads for a specific tenant."
    )
    parser.add_argument(
        "--tenant-id",
        type=str,
        required=True,
        help="Target tenant UUID.",
    )
    parser.add_argument(
        "--actor-user-id",
        type=str,
        required=True,
        help="Authorized actor user UUID (requires OWNER or ADMIN role).",
    )
    parser.add_argument(
        "--cutoff-hours",
        type=int,
        default=24,
        help="Age in hours beyond which unfinalized quarantine uploads are purged (default: 24).",
    )
    args = parser.parse_args()

    try:
        parsed_tenant = UUID(args.tenant_id)
        parsed_actor = UUID(args.actor_user_id)
    except ValueError as val_err:
        print(f"Error: Invalid UUID argument: {val_err}", file=sys.stderr)
        sys.exit(1)

    async def run_cli():
        async with async_session_maker() as session:
            try:
                report = await purge_abandoned_quarantine_objects(
                    db=session,
                    tenant_id=parsed_tenant,
                    actor_user_id=parsed_actor,
                    cutoff_hours=args.cutoff_hours,
                )
                print(
                    f"Quarantine Cleanup Completed for Tenant {parsed_tenant}: "
                    f"Scanned {report.scanned_count}, Purged {report.purged_count}"
                )
                if report.errors:
                    print(f"Errors: {report.errors}", file=sys.stderr)
            except Exception as exc:
                print(f"Quarantine cleanup failed: {exc}", file=sys.stderr)
                sys.exit(1)

    asyncio.run(run_cli())
