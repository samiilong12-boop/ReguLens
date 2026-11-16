"""Quarantine retention cleanup service for abandoned document uploads.

In accordance with Package C and Data Retention Policy:
- Purges unfinalized, abandoned quarantine storage objects older than cutoff window (default: 24 hours).
- Protects active uploads (younger than cutoff window) from deletion.
- Operates under database transactions without exposing presigned URLs or secrets.
- Logs structured audit and operational events.
- Callable programmatically or via CLI runner.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.models import Document
from app.services.audit import log_document_audit_event
from app.services.storage import StorageService, get_storage_service

logger = structlog.get_logger(__name__)


@dataclass
class CleanupReport:
    """Outcome report for quarantine retention cleanup."""
    cutoff_timestamp: datetime
    scanned_count: int = 0
    purged_count: int = 0
    purged_document_ids: List[UUID] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


async def purge_abandoned_quarantine_objects(
    db: AsyncSession,
    storage_service: Optional[StorageService] = None,
    cutoff_hours: int = 24,
) -> CleanupReport:
    """Identifies and purges expired, abandoned quarantine objects.
    
    Security invariants:
    1. Only selects documents in 'PENDING_UPLOAD' or 'QUARANTINED' status.
    2. Only selects records created strictly before the cutoff timestamp (cutoff_hours ago).
    3. Active uploads (< cutoff_hours old) are strictly preserved.
    4. Safely removes storage objects and updates DB record to 'EXPIRED'.
    5. Emits sanitized audit events for every purged object.
    """
    storage = storage_service or get_storage_service()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=cutoff_hours)

    report = CleanupReport(cutoff_timestamp=cutoff)

    # Query eligible expired records
    stmt = select(Document).where(
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
        tenant_id = doc.tenant_id

        try:
            # 1. Purge from storage backend if object exists
            if q_key and storage.object_exists(q_key):
                storage.delete_object(q_key)

            # 2. Update document metadata
            doc.quarantine_key = None
            doc.status = "EXPIRED"
            doc.rejection_reason = (
                f"Quarantine object purged: upload was abandoned and exceeded the {cutoff_hours}-hour retention window."
            )

            # 3. Log sanitized audit event
            await log_document_audit_event(
                db=db,
                tenant_id=tenant_id,
                action="DOCUMENT_QUARANTINE_PURGED",
                resource_id=doc_id,
                user_id=doc.uploaded_by_user_id,
                details={
                    "reason": doc.rejection_reason,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "cutoff_hours": cutoff_hours,
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
    from app.db.session import async_session_maker

    parser = argparse.ArgumentParser(description="Purge abandoned quarantine document uploads.")
    parser.add_argument(
        "--cutoff-hours",
        type=int,
        default=24,
        help="Age in hours beyond which unfinalized quarantine uploads are purged (default: 24).",
    )
    args = parser.parse_args()

    async def run_cli():
        async with async_session_maker() as session:
            report = await purge_abandoned_quarantine_objects(session, cutoff_hours=args.cutoff_hours)
            print(f"Quarantine Cleanup Completed: Scanned {report.scanned_count}, Purged {report.purged_count}")
            if report.errors:
                print(f"Errors: {report.errors}")

    asyncio.run(run_cli())
