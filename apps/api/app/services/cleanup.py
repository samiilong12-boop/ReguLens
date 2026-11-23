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
import re
from typing import List, Optional
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.models import Document, StorageCleanupTask, Tenant, TenantUser, User
from app.db.session import set_tenant_context, set_user_context
from app.services.audit import log_document_audit_event
from app.services.storage import StorageSecurityError, StorageService, get_storage_service

logger = structlog.get_logger(__name__)


@dataclass
class ReconciliationReport:
    """Outcome report for storage cleanup outbox reconciliation."""
    tenant_id: UUID
    scanned_count: int = 0
    completed_count: int = 0
    retried_count: int = 0
    failed_count: int = 0
    task_ids_completed: List[UUID] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


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


async def create_cleanup_task(
    db: AsyncSession,
    tenant_id: UUID,
    object_key: str,
    cleanup_reason: str,
    storage_backend: Optional[str] = None,
) -> StorageCleanupTask:
    """Creates a durable storage cleanup task within the active database transaction.

    Security invariants:
    1. Validates that object_key starts strictly with tenants/{tenant_id}/.
    2. Resolves storage_backend dynamically if omitted.
    3. Adds the task to the current database session so it commits atomically with parent operations.
    """
    if not tenant_id:
        raise ValueError("tenant_id is required to create a storage cleanup task.")
    if not object_key:
        raise ValueError("object_key is required to create a storage cleanup task.")

    if not isinstance(tenant_id, UUID):
        try:
            tenant_id = UUID(str(tenant_id))
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid tenant_id format; must be a valid UUID: {tenant_id}")

    expected_prefix = f"tenants/{tenant_id}/"
    if not object_key.startswith(expected_prefix):
        raise StorageSecurityError(
            f"Security violation: Object key '{object_key}' does not match tenant prefix '{expected_prefix}'."
        )

    if not storage_backend:
        storage = get_storage_service()
        storage_backend = getattr(storage, "backend_name", "unknown")

    task = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend=storage_backend,
        object_key=object_key,
        cleanup_reason=cleanup_reason,
        status="PENDING",
        attempts=0,
        max_attempts=5,
        next_retry_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(task)
    return task


async def execute_cleanup_task(
    db: AsyncSession,
    task: StorageCleanupTask,
    storage_service: Optional[StorageService] = None,
) -> bool:
    """Executes a single storage cleanup task idempotently and with bounded retries.

    Security invariants:
    1. Validates prefix: object_key must start with tenants/{task.tenant_id}/.
       If invalid, immediately marks task FAILED with security error and returns False.
    2. Checks if object exists before deletion. If already absent, treats as idempotent success.
    3. Deletes object from storage backend.
    4. On success: marks COMPLETED with completed_at timestamp.
    5. On storage exception: increments attempts, calculates exponential backoff (30s, 60s, 120s, 240s, 480s),
       sanitizes diagnostic message in last_error (no leaked URLs or secrets), and marks FAILED if attempts >= max_attempts.
    6. Commits task state change to database.
    """
    expected_prefix = f"tenants/{task.tenant_id}/"
    if not task.object_key.startswith(expected_prefix):
        err_msg = (
            f"Security anomaly: Storage cleanup object key '{task.object_key}' "
            f"does not match expected tenant prefix '{expected_prefix}'. Terminating task."
        )
        logger.error(
            "storage_cleanup_prefix_mismatch",
            task_id=str(task.id),
            tenant_id=str(task.tenant_id),
            object_key=task.object_key,
        )
        task.status = "FAILED"
        task.last_error = err_msg
        task.locked_at = None
        task.locked_by = None
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return False

    storage = storage_service or get_storage_service()

    try:
        if storage.object_exists(task.object_key):
            storage.delete_object(task.object_key)

        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        task.last_error = None
        task.locked_at = None
        task.locked_by = None
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(
            "storage_cleanup_task_completed",
            task_id=str(task.id),
            tenant_id=str(task.tenant_id),
            object_key=task.object_key,
            reason=task.cleanup_reason,
        )
        return True
    except Exception as exc:
        task.attempts += 1
        raw_error = str(exc)
        sanitized_error = re.sub(r"(https?://\S+|\?[^ \s]+)", "[REDACTED_URL]", raw_error)[:500]
        logger.warning(
            "storage_cleanup_task_attempt_failed",
            task_id=str(task.id),
            tenant_id=str(task.tenant_id),
            object_key=task.object_key,
            attempt=task.attempts,
            max_attempts=task.max_attempts,
            error=sanitized_error,
        )

        if task.attempts >= task.max_attempts:
            task.status = "FAILED"
            task.last_error = f"Max attempts ({task.max_attempts}) reached. Last error: {sanitized_error}"
        else:
            task.status = "PENDING"
            backoff_seconds = min(3600, 30 * (2 ** (task.attempts - 1)))
            task.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            task.last_error = f"Attempt {task.attempts} failed: {sanitized_error}"

        task.locked_at = None
        task.locked_by = None
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return False


async def reconcile_storage_cleanup_tasks(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: UUID,
    storage_service: Optional[StorageService] = None,
    limit: int = 50,
    worker_id: Optional[str] = None,
    lock_timeout_seconds: int = 600,
) -> ReconciliationReport:
    """Reconciles due storage cleanup tasks for a specific tenant under authorized context.

    Security invariants:
    1. Requires explicit tenant_id and actor_user_id.
    2. Validates actor user exists and is active.
    3. Establishes transaction-scoped user and tenant context (set_user_context, set_tenant_context).
    4. Validates tenant exists and is active.
    5. Validates actor membership and requires OWNER or ADMIN role (rejects VIEWER / unauthorized).
    6. Selects due tasks (PENDING with next_retry_at <= now, or stale PROCESSING past lock_timeout).
    7. Uses FOR UPDATE SKIP LOCKED for high concurrency and lease claiming.
    8. Executes each task safely and updates the report.
    """
    if limit is None or limit <= 0:
        raise ValueError("limit must be a positive integer greater than 0.")
    if limit > 500:
        raise ValueError("limit cannot exceed 500 tasks per reconciliation batch.")

    if not tenant_id:
        raise ValueError("tenant_id is required for tenant-scoped storage reconciliation.")
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

    # Verify actor user status
    stmt_user = select(User.is_active).where(User.id == actor_user_id)
    user_active = (await db.execute(stmt_user)).scalar_one_or_none()
    if user_active is None:
        raise PermissionError(f"Actor user '{actor_user_id}' does not exist.")
    if not user_active:
        raise PermissionError(f"Actor user '{actor_user_id}' account is deactivated.")

    # Establish transaction-scoped user and tenant context
    await set_user_context(db, actor_user_id)
    await set_tenant_context(db, tenant_id)

    # Verify tenant organization status
    stmt_tenant = select(Tenant.is_active).where(Tenant.id == tenant_id)
    tenant_active = (await db.execute(stmt_tenant)).scalar_one_or_none()
    if tenant_active is None:
        raise PermissionError(f"Target tenant organization '{tenant_id}' does not exist.")
    if not tenant_active:
        raise PermissionError(f"Target tenant organization '{tenant_id}' is inactive or suspended.")

    # Verify live actor membership and role in target tenant
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
            f"User role '{current_role}' is not authorized to execute storage reconciliation. "
            f"Requires OWNER or ADMIN role."
        )

    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(seconds=lock_timeout_seconds)
    effective_worker_id = worker_id or f"reconciler_{uuid.uuid4().hex[:8]}"

    report = ReconciliationReport(tenant_id=tenant_id)
    storage = storage_service or get_storage_service()

    # Query due tasks: PENDING tasks due for retry OR stale PROCESSING tasks abandoned by dead workers
    stmt = (
        select(StorageCleanupTask)
        .where(
            StorageCleanupTask.tenant_id == tenant_id,
            (
                (StorageCleanupTask.status == "PENDING") & (StorageCleanupTask.next_retry_at <= now)
            ) | (
                (StorageCleanupTask.status == "PROCESSING") & (StorageCleanupTask.locked_at < stale_threshold)
            )
        )
        .order_by(StorageCleanupTask.next_retry_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await db.execute(stmt)
    due_tasks = result.scalars().all()
    report.scanned_count = len(due_tasks)

    for task in due_tasks:
        # Claim lease
        task.status = "PROCESSING"
        task.locked_at = datetime.now(timezone.utc)
        task.locked_by = effective_worker_id
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Execute cleanup
        success = await execute_cleanup_task(db=db, task=task, storage_service=storage)
        if success:
            report.completed_count += 1
            report.task_ids_completed.append(task.id)
        else:
            if task.status == "FAILED":
                report.failed_count += 1
                if task.last_error:
                    report.errors.append(task.last_error)
            else:
                report.retried_count += 1

    return report


if __name__ == "__main__":
    import argparse
    import asyncio
    import sys
    from app.db.session import async_session_maker

    parser = argparse.ArgumentParser(
        description="ReguLens Storage Cleanup and Retention Service CLI."
    )
    subparsers = parser.add_subparsers(dest="command", help="Cleanup subcommand to execute.")

    # 1. Purge abandoned quarantine uploads
    purge_parser = subparsers.add_parser("purge", help="Purge abandoned quarantine uploads.")
    purge_parser.add_argument("--tenant-id", type=str, required=True, help="Target tenant UUID.")
    purge_parser.add_argument("--actor-user-id", type=str, required=True, help="Authorized actor user UUID (OWNER or ADMIN).")
    purge_parser.add_argument("--cutoff-hours", type=int, default=24, help="Age in hours (default: 24).")

    # 2. Reconcile storage cleanup outbox
    reconcile_parser = subparsers.add_parser("reconcile", help="Reconcile due storage cleanup outbox tasks.")
    reconcile_parser.add_argument("--tenant-id", type=str, required=True, help="Target tenant UUID.")
    reconcile_parser.add_argument("--actor-user-id", type=str, required=True, help="Authorized actor user UUID (OWNER or ADMIN).")
    reconcile_parser.add_argument("--limit", type=int, default=50, help="Maximum tasks to process (default: 50).")

    # Backward compatibility: top-level arguments for legacy invocations
    parser.add_argument("--tenant-id", type=str, required=False, help="Target tenant UUID (legacy default: purge).")
    parser.add_argument("--actor-user-id", type=str, required=False, help="Authorized actor user UUID.")
    parser.add_argument("--cutoff-hours", type=int, default=24, help="Age in hours (default: 24).")

    args = parser.parse_args()

    command = args.command
    tenant_id_arg = getattr(args, "tenant_id", None)
    actor_id_arg = getattr(args, "actor_user_id", None)

    if not tenant_id_arg or not actor_id_arg:
        print("Error: --tenant-id and --actor-user-id are required.", file=sys.stderr)
        sys.exit(1)

    try:
        parsed_tenant = UUID(tenant_id_arg)
        parsed_actor = UUID(actor_id_arg)
    except ValueError as val_err:
        print(f"Error: Invalid UUID argument: {val_err}", file=sys.stderr)
        sys.exit(1)

    async def run_cli():
        async with async_session_maker() as session:
            try:
                if command == "reconcile":
                    limit = getattr(args, "limit", 50)
                    report = await reconcile_storage_cleanup_tasks(
                        db=session,
                        tenant_id=parsed_tenant,
                        actor_user_id=parsed_actor,
                        limit=limit,
                    )
                    print(
                        f"Reconciliation Completed for Tenant {parsed_tenant}: "
                        f"Scanned {report.scanned_count}, Completed {report.completed_count}, "
                        f"Retried {report.retried_count}, Failed {report.failed_count}"
                    )
                    if report.errors:
                        print(f"Errors: {report.errors}", file=sys.stderr)
                else:
                    cutoff_hours = getattr(args, "cutoff_hours", 24)
                    report = await purge_abandoned_quarantine_objects(
                        db=session,
                        tenant_id=parsed_tenant,
                        actor_user_id=parsed_actor,
                        cutoff_hours=cutoff_hours,
                    )
                    print(
                        f"Quarantine Cleanup Completed for Tenant {parsed_tenant}: "
                        f"Scanned {report.scanned_count}, Purged {report.purged_count}"
                    )
                    if report.errors:
                        print(f"Errors: {report.errors}", file=sys.stderr)
            except Exception as exc:
                print(f"Cleanup operation failed: {exc}", file=sys.stderr)
                sys.exit(1)

    asyncio.run(run_cli())
