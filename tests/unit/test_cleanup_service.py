"""Unit tests for quarantine retention cleanup service."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.db.models import Document, StorageCleanupTask
from app.services.cleanup import (
    purge_abandoned_quarantine_objects,
    create_cleanup_task,
    execute_cleanup_task,
    reconcile_storage_cleanup_tasks,
    CleanupReport,
    ReconciliationReport,
)
from app.services.storage import MemoryStorageService, StorageSecurityError


@pytest.mark.asyncio(loop_scope="function")
async def test_purge_abandoned_quarantine_objects_success():
    """Cleanup service purges expired quarantine objects (>24h) and preserves active uploads (<24h)."""
    storage = MemoryStorageService()
    now = datetime.now(timezone.utc)
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()

    # 1. Old expired upload (30 hours old) -> MUST BE PURGED
    old_doc_id = uuid.uuid4()
    old_key = f"tenants/{tenant_id}/quarantine/old_uuid"
    storage.put_object(old_key, b"old-abandoned-data")
    old_doc = Document(
        id=old_doc_id,
        tenant_id=tenant_id,
        status="PENDING_UPLOAD",
        quarantine_key=old_key,
        created_at=now - timedelta(hours=30),
    )

    # 2. Fresh active upload (2 hours old) -> MUST BE PRESERVED
    fresh_doc_id = uuid.uuid4()
    fresh_key = f"tenants/{tenant_id}/quarantine/fresh_uuid"
    storage.put_object(fresh_key, b"fresh-active-data")
    fresh_doc = Document(
        id=fresh_doc_id,
        tenant_id=tenant_id,
        status="PENDING_UPLOAD",
        quarantine_key=fresh_key,
        created_at=now - timedelta(hours=2),
    )

    # Mock AsyncSession
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.sync_session = MagicMock()
    mock_session.sync_session.info = {}

    # Define sequential return values for session.execute:
    # 1. User is_active check -> True
    # 2. set_user_context -> text execute
    # 3. set_tenant_context -> text execute
    # 4. Tenant is_active check -> True
    # 5. TenantUser role check -> "ADMIN"
    # 6. Document query -> returns [old_doc]
    # 7. Audit log flush (if any)
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = True

    mock_tenant_res = MagicMock()
    mock_tenant_res.scalar_one_or_none.return_value = True

    mock_role_res = MagicMock()
    mock_role_res.scalar_one_or_none.return_value = "ADMIN"

    mock_docs_res = MagicMock()
    mock_docs_res.scalars.return_value.all.return_value = [old_doc]

    async def mock_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt).lower()
        if "from users" in stmt_str:
            return mock_user_res
        elif "from tenants" in stmt_str:
            return mock_tenant_res
        elif "from tenant_users" in stmt_str:
            return mock_role_res
        elif "from documents" in stmt_str:
            return mock_docs_res
        return MagicMock()

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    report = await purge_abandoned_quarantine_objects(
        db=mock_session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        storage_service=storage,
        cutoff_hours=24,
    )

    assert report.scanned_count == 1
    assert report.purged_count == 1
    assert old_doc_id in report.purged_document_ids
    assert len(report.errors) == 0

    # Old object purged from storage and document marked EXPIRED
    assert not storage.object_exists(old_key)
    assert old_doc.status == "EXPIRED"
    assert old_doc.quarantine_key is None
    assert "abandoned" in old_doc.rejection_reason

    # Fresh object remains intact in storage
    assert storage.object_exists(fresh_key)
    assert fresh_doc.status == "PENDING_UPLOAD"

    # Commit called
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_purge_input_validation():
    """Validates input constraints on cutoff_hours, tenant_id, and actor_user_id."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    # 1. Non-positive cutoff_hours
    with pytest.raises(ValueError, match="cutoff_hours must be a positive integer"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            cutoff_hours=0,
        )

    with pytest.raises(ValueError, match="cutoff_hours must be a positive integer"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            cutoff_hours=-5,
        )

    # 2. Missing tenant_id or actor_user_id
    with pytest.raises(ValueError, match="tenant_id is required"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=None,
            actor_user_id=actor_id,
        )

    with pytest.raises(ValueError, match="actor_user_id is required"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=None,
        )

    # 3. Invalid UUID strings
    with pytest.raises(ValueError, match="Invalid tenant_id format"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id="invalid-uuid",
            actor_user_id=actor_id,
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_purge_authorization_and_role_checks():
    """Validates role-based authorization: rejects inactive users, non-members, and VIEWER roles."""
    mock_session = AsyncMock()
    mock_session.sync_session = MagicMock()
    mock_session.sync_session.info = {}
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    # 1. Deactivated user
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = False
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    with pytest.raises(PermissionError, match="account is deactivated"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
        )

    # 2. Inactive tenant
    mock_user_active = MagicMock()
    mock_user_active.scalar_one_or_none.return_value = True
    mock_tenant_inactive = MagicMock()
    mock_tenant_inactive.scalar_one_or_none.return_value = False

    async def mock_exec_inactive_tenant(stmt, *args, **kwargs):
        s = str(stmt).lower()
        if "from users" in s:
            return mock_user_active
        if "from tenants" in s:
            return mock_tenant_inactive
        return MagicMock()

    mock_session.execute = AsyncMock(side_effect=mock_exec_inactive_tenant)
    with pytest.raises(PermissionError, match="inactive or suspended"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
        )

    # 3. Non-member user
    mock_tenant_active = MagicMock()
    mock_tenant_active.scalar_one_or_none.return_value = True
    mock_role_none = MagicMock()
    mock_role_none.scalar_one_or_none.return_value = None

    async def mock_exec_non_member(stmt, *args, **kwargs):
        s = str(stmt).lower()
        if "from users" in s:
            return mock_user_active
        if "from tenants" in s:
            return mock_tenant_active
        if "from tenant_users" in s:
            return mock_role_none
        return MagicMock()

    mock_session.execute = AsyncMock(side_effect=mock_exec_non_member)
    with pytest.raises(PermissionError, match="not an active member"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
        )

    # 4. Member with VIEWER role
    mock_role_viewer = MagicMock()
    mock_role_viewer.scalar_one_or_none.return_value = "VIEWER"

    async def mock_exec_viewer(stmt, *args, **kwargs):
        s = str(stmt).lower()
        if "from users" in s:
            return mock_user_active
        if "from tenants" in s:
            return mock_tenant_active
        if "from tenant_users" in s:
            return mock_role_viewer
        return MagicMock()

    mock_session.execute = AsyncMock(side_effect=mock_exec_viewer)
    with pytest.raises(PermissionError, match="Requires OWNER or ADMIN role"):
        await purge_abandoned_quarantine_objects(
            db=mock_session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_create_cleanup_task_success():
    """create_cleanup_task enqueues a valid outbox task within active transaction."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    tenant_id = uuid.uuid4()
    valid_key = f"tenants/{tenant_id}/quarantine/test-object.pdf"

    task = await create_cleanup_task(
        db=mock_session,
        tenant_id=tenant_id,
        object_key=valid_key,
        cleanup_reason="QUARANTINE_POST_FINALIZE",
        storage_backend="memory",
    )

    assert task.tenant_id == tenant_id
    assert task.object_key == valid_key
    assert task.storage_backend == "memory"
    assert task.cleanup_reason == "QUARANTINE_POST_FINALIZE"
    assert task.status == "PENDING"
    assert task.attempts == 0
    assert task.max_attempts == 5
    mock_session.add.assert_called_once_with(task)


@pytest.mark.asyncio(loop_scope="function")
async def test_create_cleanup_task_prefix_mismatch_raises_security_error():
    """create_cleanup_task strictly forbids object keys not matching tenants/{tenant_id}/."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Cross-tenant key
    cross_key = f"tenants/{tenant_b}/quarantine/forbidden.pdf"
    with pytest.raises(StorageSecurityError, match="does not match tenant prefix"):
        await create_cleanup_task(
            db=mock_session,
            tenant_id=tenant_a,
            object_key=cross_key,
            cleanup_reason="QUARANTINE_POST_FINALIZE",
        )

    # Arbitrary root path
    with pytest.raises(StorageSecurityError, match="does not match tenant prefix"):
        await create_cleanup_task(
            db=mock_session,
            tenant_id=tenant_a,
            object_key="etc/passwd",
            cleanup_reason="DOCUMENT_DELETION",
        )

    mock_session.add.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
async def test_execute_cleanup_task_idempotent_success():
    """execute_cleanup_task purges existing object and marks task COMPLETED."""
    storage = MemoryStorageService()
    tenant_id = uuid.uuid4()
    key = f"tenants/{tenant_id}/quarantine/file_to_delete.pdf"
    storage.put_object(key, b"dummy-data")

    task = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend="memory",
        object_key=key,
        cleanup_reason="QUARANTINE_POST_FINALIZE",
        status="PENDING",
    )

    mock_session = AsyncMock()
    success = await execute_cleanup_task(db=mock_session, task=task, storage_service=storage)

    assert success is True
    assert task.status == "COMPLETED"
    assert task.completed_at is not None
    assert not storage.object_exists(key)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_execute_cleanup_task_idempotent_absent_object():
    """execute_cleanup_task treats already absent object as idempotent success."""
    storage = MemoryStorageService()
    tenant_id = uuid.uuid4()
    key = f"tenants/{tenant_id}/quarantine/already_absent.pdf"

    task = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend="memory",
        object_key=key,
        cleanup_reason="DOCUMENT_DELETION",
        status="PENDING",
    )

    mock_session = AsyncMock()
    success = await execute_cleanup_task(db=mock_session, task=task, storage_service=storage)

    assert success is True
    assert task.status == "COMPLETED"
    assert task.completed_at is not None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_execute_cleanup_task_prefix_mismatch_fails_closed():
    """execute_cleanup_task immediately marks task FAILED if key does not match tenant prefix."""
    storage = MemoryStorageService()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    foreign_key = f"tenants/{tenant_b}/documents/secret.pdf"
    storage.put_object(foreign_key, b"secret-payload")

    task = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        storage_backend="memory",
        object_key=foreign_key,
        cleanup_reason="DOCUMENT_DELETION",
        status="PENDING",
    )

    mock_session = AsyncMock()
    success = await execute_cleanup_task(db=mock_session, task=task, storage_service=storage)

    assert success is False
    assert task.status == "FAILED"
    assert "Security anomaly" in task.last_error
    # Storage object was NOT deleted
    assert storage.object_exists(foreign_key)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_execute_cleanup_task_retry_and_exponential_backoff():
    """execute_cleanup_task increments attempts, sets exponential backoff, and sanitizes errors."""
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.delete_object.side_effect = RuntimeError(
        "S3 503 SlowDown: https://s3.amazonaws.com/bucket/key?Signature=SECRET123"
    )

    tenant_id = uuid.uuid4()
    key = f"tenants/{tenant_id}/documents/transient_fail.pdf"

    task = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend="s3",
        object_key=key,
        cleanup_reason="DOCUMENT_DELETION",
        status="PENDING",
        attempts=1,  # Will become attempt 2
        max_attempts=5,
    )

    mock_session = AsyncMock()
    before = datetime.now(timezone.utc)
    success = await execute_cleanup_task(db=mock_session, task=task, storage_service=storage)

    assert success is False
    assert task.status == "PENDING"
    assert task.attempts == 2
    # 30 * 2^(2-1) = 60 seconds backoff
    assert task.next_retry_at >= before + timedelta(seconds=55)
    # Check sanitized error: secret URL should be redacted
    assert "SECRET123" not in task.last_error
    assert "[REDACTED_URL]" in task.last_error
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_execute_cleanup_task_max_attempts_exceeded_marks_failed():
    """execute_cleanup_task marks task FAILED when max_attempts is reached."""
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.delete_object.side_effect = RuntimeError("Permanent storage corruption")

    tenant_id = uuid.uuid4()
    key = f"tenants/{tenant_id}/documents/permanent_fail.pdf"

    task = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend="s3",
        object_key=key,
        cleanup_reason="DOCUMENT_DELETION",
        status="PENDING",
        attempts=4,  # Next attempt is 5, reaching max_attempts=5
        max_attempts=5,
    )

    mock_session = AsyncMock()
    success = await execute_cleanup_task(db=mock_session, task=task, storage_service=storage)

    assert success is False
    assert task.status == "FAILED"
    assert task.attempts == 5
    assert "Max attempts (5) reached" in task.last_error
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="function")
async def test_reconcile_storage_cleanup_tasks_worker_lease_and_stale_recovery():
    """reconcile_storage_cleanup_tasks claims due tasks, claims stale leases, and executes cleanup."""
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    storage = MemoryStorageService()

    # 1. Normal due PENDING task
    key1 = f"tenants/{tenant_id}/documents/due1.pdf"
    storage.put_object(key1, b"content1")
    task1 = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend="memory",
        object_key=key1,
        cleanup_reason="DOCUMENT_DELETION",
        status="PENDING",
        next_retry_at=now - timedelta(minutes=5),
    )

    # 2. Stale PROCESSING task abandoned by dead worker (>10 min ago)
    key2 = f"tenants/{tenant_id}/quarantine/abandoned_lease.pdf"
    storage.put_object(key2, b"content2")
    task2 = StorageCleanupTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        storage_backend="memory",
        object_key=key2,
        cleanup_reason="QUARANTINE_POST_FINALIZE",
        status="PROCESSING",
        locked_at=now - timedelta(minutes=15),
        locked_by="crashed_worker_123",
    )

    mock_session = AsyncMock()
    mock_session.sync_session = MagicMock()
    mock_session.sync_session.info = {}

    mock_user_active = MagicMock()
    mock_user_active.scalar_one_or_none.return_value = True

    mock_tenant_active = MagicMock()
    mock_tenant_active.scalar_one_or_none.return_value = True

    mock_role_admin = MagicMock()
    mock_role_admin.scalar_one_or_none.return_value = "ADMIN"

    mock_tasks_res = MagicMock()
    mock_tasks_res.scalars.return_value.all.return_value = [task1, task2]

    async def mock_exec(stmt, *args, **kwargs):
        s = str(stmt).lower()
        if "from users" in s:
            return mock_user_active
        if "from tenants" in s:
            return mock_tenant_active
        if "from tenant_users" in s:
            return mock_role_admin
        if "from storage_cleanup_tasks" in s:
            return mock_tasks_res
        return MagicMock()

    mock_session.execute = AsyncMock(side_effect=mock_exec)

    report = await reconcile_storage_cleanup_tasks(
        db=mock_session,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        storage_service=storage,
        limit=50,
        worker_id="active_worker_999",
    )

    assert report.scanned_count == 2
    assert report.completed_count == 2
    assert report.failed_count == 0
    assert task1.id in report.task_ids_completed
    assert task2.id in report.task_ids_completed

    # Both objects purged
    assert not storage.object_exists(key1)
    assert not storage.object_exists(key2)
    assert task1.status == "COMPLETED"
    assert task2.status == "COMPLETED"
