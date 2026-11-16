"""Unit tests for quarantine retention cleanup service."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.db.models import Document
from app.services.cleanup import purge_abandoned_quarantine_objects, CleanupReport
from app.services.storage import MemoryStorageService


@pytest.mark.asyncio
async def test_purge_abandoned_quarantine_objects():
    """Cleanup service purges expired quarantine objects (>24h) and preserves active uploads (<24h)."""
    storage = MemoryStorageService()
    now = datetime.now(timezone.utc)
    tenant_id = uuid.uuid4()

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
    mock_result = MagicMock()
    # The SQL query filters created_at < cutoff, so DB returns only old_doc
    mock_result.scalars.return_value.all.return_value = [old_doc]
    mock_session.execute.return_value = mock_result

    report = await purge_abandoned_quarantine_objects(
        db=mock_session,
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
