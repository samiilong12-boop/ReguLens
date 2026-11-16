"""Unit tests for quarantine retention cleanup service."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.db.models import Document
from app.services.cleanup import purge_abandoned_quarantine_objects, CleanupReport
from app.services.storage import MemoryStorageService


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
