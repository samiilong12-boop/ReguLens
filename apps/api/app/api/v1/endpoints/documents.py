"""Document storage, validation, and lifecycle endpoints."""
from datetime import datetime, timezone
import re
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_tenant_user,
    get_tenant_db,
    require_compliance_officer,
    require_viewer,
)
from app.core.config import settings
from app.db.models import Document, Consignment
from app.schemas.document import (
    DocumentUploadInitiateRequest,
    DocumentUploadInitiateResponse,
    DocumentFinalizeRequest,
    DocumentResponse,
    DocumentDownloadResponse,
    DocumentListResponse,
)
from app.services.audit import log_document_audit_event
from app.services.file_validation import validate_file_content
from app.services.scanner import ScanStatus, get_malware_scanner
from app.services.storage import (
    generate_tenant_object_key,
    get_storage_service,
    StoragePayloadTooLargeError,
    StorageSecurityError,
)
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


def sanitize_download_filename(filename: str) -> str:
    """Sanitizes filename for Content-Disposition header against header injection."""
    clean = re.sub(r'[\r\n"\\/]', '_', filename)
    return clean[:200] or "document"


@router.post(
    "/initiate-upload",
    response_model=DocumentUploadInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a secure document upload and obtain a presigned quarantine URL",
)
async def initiate_upload(
    payload: DocumentUploadInitiateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_compliance_officer),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentUploadInitiateResponse:
    """Initiates an upload request by:
    1. Enforcing role authorization (Owner, Admin, or Compliance Officer).
    2. Validating consignment ownership under active tenant if consignment_id is provided.
    3. Generating opaque quarantine and permanent storage keys (no user filenames in paths).
    4. Storing a pending document record.
    5. Generating a 15-minute presigned upload URL directly to the quarantine area.
    6. Appending an immutable audit log entry.
    """
    storage_service = get_storage_service()

    # If consignment_id is provided, verify it belongs to this tenant (RLS enforces tenant scope)
    if payload.consignment_id:
        stmt_consignment = select(Consignment.id).where(
            Consignment.id == payload.consignment_id,
            Consignment.tenant_id == current_user.tenant_id,
        )
        consignment_exists = (await db.execute(stmt_consignment)).scalar_one_or_none()
        if not consignment_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Consignment '{payload.consignment_id}' was not found in active workspace.",
            )

    # Generate opaque keys
    quarantine_key = generate_tenant_object_key(current_user.tenant_id, is_quarantine=True)
    storage_key = generate_tenant_object_key(current_user.tenant_id, is_quarantine=False)

    # Create document record in PENDING_UPLOAD state
    document = Document(
        tenant_id=current_user.tenant_id,
        consignment_id=payload.consignment_id,
        document_type=payload.document_type,
        file_name=payload.file_name,
        file_size_bytes=payload.expected_size_bytes,
        mime_type=payload.claimed_mime_type,
        storage_key=storage_key,
        quarantine_key=quarantine_key,
        sha256_hash=payload.expected_sha256,
        status="PENDING_UPLOAD",
        antivirus_status="PENDING",
        uploaded_by_user_id=current_user.id,
    )
    db.add(document)
    await db.flush()

    # Generate upload transport configuration based on backend capabilities
    if not storage_service.supports_direct_upload:
        # Bounded server-mediated upload endpoint (e.g. for GCS where signed PUT lacks provider content-length-range)
        upload_mode = "server_mediated"
        upload_url = f"/api/v1/documents/{document.id}/upload-content"
        upload_method = "POST"
        upload_fields = None
        expires_in = 900
    else:
        try:
            presigned = storage_service.generate_presigned_upload_url(
                object_key=quarantine_key,
                expires_in_seconds=900,
                content_type=payload.claimed_mime_type,
                max_size_bytes=min(payload.expected_size_bytes, settings.MAX_DOCUMENT_SIZE_BYTES),
            )
            upload_mode = "direct"
            upload_url = presigned.url
            upload_method = presigned.method
            upload_fields = presigned.fields or None
            expires_in = presigned.expires_in_seconds
        except StorageSecurityError as e:
            logger.error("presigned_upload_generation_failed", error=str(e), key=quarantine_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Secure upload policy generation failed. Please retry or contact support.",
            )

    # Log immutable audit event
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await log_document_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        action="DOCUMENT_UPLOAD_INITIATED",
        resource_id=document.id,
        user_id=current_user.id,
        details={
            "file_name": payload.file_name,
            "expected_size_bytes": payload.expected_size_bytes,
            "claimed_mime_type": payload.claimed_mime_type,
            "document_type": payload.document_type,
            "consignment_id": str(payload.consignment_id) if payload.consignment_id else None,
            "expires_in_seconds": expires_in,
            "upload_method": upload_method,
            "upload_mode": upload_mode,
        },
        ip_address=ip,
        user_agent=ua,
    )

    await db.commit()
    await db.refresh(document)

    return DocumentUploadInitiateResponse(
        document_id=document.id,
        upload_url=upload_url,
        expires_in_seconds=expires_in,
        quarantine_key=quarantine_key,
        status=document.status,
        created_at=document.created_at,
        upload_method=upload_method,
        upload_fields=upload_fields,
        upload_mode=upload_mode,
    )


@router.post(
    "/{document_id}/upload-content",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Direct bounded streaming upload to quarantine with upload-time size enforcement",
)
async def upload_document_content(
    document_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_compliance_officer),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentResponse:
    """Direct bounded streaming upload endpoint providing upload-time size enforcement.

    Security guarantees:
    - Rejects Content-Length headers exceeding 25MB before streaming.
    - Aborts immediately if streamed payload exceeds 25MB (26,214,400 bytes).
    - Prevents unbounded memory accumulation during upload.
    - Writes directly into quarantine isolation path.
    """
    storage_service = get_storage_service()

    # 1. Fetch document under RLS
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if document.status != "PENDING_UPLOAD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not pending upload (current status: '{document.status}').",
        )

    # 2. Check Content-Length header ceiling
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            cl = int(content_length_header)
            if cl > settings.MAX_DOCUMENT_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content-Length ({cl} bytes) exceeds maximum permitted limit of {settings.MAX_DOCUMENT_SIZE_BYTES} bytes.",
                )
        except ValueError:
            pass

    # 3. Stream chunks with hard byte count ceiling and bounded storage-level streaming
    max_limit = settings.MAX_DOCUMENT_SIZE_BYTES
    try:
        total_bytes = await storage_service.stream_upload_object(
            object_key=document.quarantine_key,
            stream=request.stream(),
            max_bytes=max_limit,
            content_type=document.mime_type,
        )
    except StoragePayloadTooLargeError as e:
        storage_service.delete_object(document.quarantine_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        storage_service.delete_object(document.quarantine_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("upload_streaming_failed", document_id=str(document_id), error=str(e))
        storage_service.delete_object(document.quarantine_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload streaming failed due to a server error. Please retry.",
        )

    document.file_size_bytes = total_bytes
    await db.commit()
    await db.refresh(document)
    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/finalize-upload",
    response_model=DocumentResponse,
    summary="Finalize upload, verify stored object (size, magic bytes, SHA-256), and scan for malware",
)
async def finalize_upload(
    document_id: UUID,
    request: Request,
    payload: Optional[DocumentFinalizeRequest] = None,
    current_user: CurrentUser = Depends(require_compliance_officer),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentResponse:
    """Finalizes an uploaded document:
    1. Fetches raw object from quarantine.
    2. Validates exact file size (<= 25 MB).
    3. Validates file signature (magic bytes) against approved MIME list.
    4. Computes server-side SHA-256 and validates against client expectation if supplied.
    5. Executes malware scanning (fails safe if scanner is unavailable or infected).
    6. Moves object from quarantine to permanent storage only on CLEAN scan.
    7. Sets status to AVAILABLE.
    """
    storage_service = get_storage_service()
    scanner = get_malware_scanner()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    # Fetch document under RLS
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.status != "PENDING_UPLOAD":
        if document.status == "AVAILABLE":
            return DocumentResponse.model_validate(document)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not pending upload (current status: '{document.status}').",
        )

    # Verify object exists in storage quarantine or already promoted in permanent storage from a prior attempt
    has_quarantine = bool(document.quarantine_key and storage_service.object_exists(document.quarantine_key))
    has_permanent = bool(document.storage_key and storage_service.object_exists(document.storage_key))

    if not has_quarantine and not has_permanent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload payload not found in storage. Please upload file before finalization.",
        )

    active_object_key = document.quarantine_key if has_quarantine else document.storage_key

    # Pre-read metadata inspection: prevent unbounded memory consumption
    try:
        metadata = storage_service.get_object_metadata(active_object_key)
    except Exception as e:
        logger.error("quarantine_metadata_inspection_failed", document_id=str(document_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to inspect quarantine object metadata. Please retry.",
        )

    if metadata.size_bytes > settings.MAX_DOCUMENT_SIZE_BYTES:
        storage_service.delete_object(active_object_key)
        document.status = "REJECTED"
        document.antivirus_status = "REJECTED_OVERSIZED"
        document.rejection_reason = (
            f"File size ({metadata.size_bytes} bytes) exceeds maximum permitted limit of {settings.MAX_DOCUMENT_SIZE_BYTES} bytes."
        )
        document.file_size_bytes = metadata.size_bytes
        await log_document_audit_event(
            db=db,
            tenant_id=current_user.tenant_id,
            action="DOCUMENT_VALIDATION_FAILED",
            resource_id=document.id,
            user_id=current_user.id,
            details={
                "reason": document.rejection_reason,
                "file_size_bytes": metadata.size_bytes,
                "max_permitted_bytes": settings.MAX_DOCUMENT_SIZE_BYTES,
            },
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=document.rejection_reason,
        )

    if metadata.size_bytes == 0:
        storage_service.delete_object(active_object_key)
        document.status = "REJECTED"
        document.antivirus_status = "REJECTED_EMPTY_FILE"
        document.rejection_reason = "File payload is empty (0 bytes)."
        document.file_size_bytes = 0
        await log_document_audit_event(
            db=db,
            tenant_id=current_user.tenant_id,
            action="DOCUMENT_VALIDATION_FAILED",
            resource_id=document.id,
            user_id=current_user.id,
            details={"reason": document.rejection_reason},
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=document.rejection_reason,
        )

    # Read payload bytes bounded by MAX_DOCUMENT_SIZE_BYTES
    data = storage_service.get_object(active_object_key, max_bytes=settings.MAX_DOCUMENT_SIZE_BYTES)

    # Expected SHA-256 can come from initiation or finalize payload
    expected_sha256 = (payload.expected_sha256 if payload else None) or document.sha256_hash

    # 1. Server-side file validation (size, magic bytes, sha256)
    validation = validate_file_content(
        data=data,
        claimed_mime=document.mime_type,
        expected_sha256=expected_sha256,
    )

    if not validation.is_valid:
        # Delete invalid file from quarantine
        storage_service.delete_object(document.quarantine_key)
        document.status = "REJECTED"
        document.antivirus_status = "REJECTED_VALIDATION_FAILED"
        document.rejection_reason = validation.error_message
        document.file_size_bytes = validation.file_size_bytes
        document.sha256_hash = validation.sha256_hash

        await log_document_audit_event(
            db=db,
            tenant_id=current_user.tenant_id,
            action="DOCUMENT_VALIDATION_FAILED",
            resource_id=document.id,
            user_id=current_user.id,
            details={
                "reason": validation.error_message,
                "detected_mime": validation.detected_mime,
                "file_size_bytes": validation.file_size_bytes,
            },
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {validation.error_message}",
        )

    # 2. Malware scanning
    scan_result = scanner.scan(data)

    if scan_result.status == ScanStatus.INFECTED:
        # Malware detected: delete immediately from quarantine
        storage_service.delete_object(document.quarantine_key)
        document.status = "REJECTED"
        document.antivirus_status = "INFECTED"
        document.rejection_reason = f"Malware detected: {scan_result.virus_name}"
        document.file_size_bytes = validation.file_size_bytes
        document.sha256_hash = validation.sha256_hash

        await log_document_audit_event(
            db=db,
            tenant_id=current_user.tenant_id,
            action="DOCUMENT_MALWARE_SCAN_COMPLETED",
            resource_id=document.id,
            user_id=current_user.id,
            details={"status": "INFECTED", "virus_name": scan_result.virus_name},
            ip_address=ip,
            user_agent=ua,
        )
        await log_document_audit_event(
            db=db,
            tenant_id=current_user.tenant_id,
            action="DOCUMENT_VALIDATION_FAILED",
            resource_id=document.id,
            user_id=current_user.id,
            details={"reason": f"Malware detected: {scan_result.virus_name}"},
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Security check failed: Malware detected ({scan_result.virus_name}). File rejected and purged.",
        )

    if scan_result.status in (ScanStatus.UNAVAILABLE, ScanStatus.ERROR):
        # Fail safe: Do NOT mark clean. Hold in quarantine.
        document.status = "QUARANTINED"
        document.antivirus_status = scan_result.status.value
        document.rejection_reason = "Malware scanner unavailable or error during scan"
        document.file_size_bytes = validation.file_size_bytes
        document.sha256_hash = validation.sha256_hash

        await log_document_audit_event(
            db=db,
            tenant_id=current_user.tenant_id,
            action="DOCUMENT_MALWARE_SCAN_COMPLETED",
            resource_id=document.id,
            user_id=current_user.id,
            details={"status": scan_result.status.value, "details": scan_result.details},
            ip_address=ip,
            user_agent=ua,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Malware scanner service is temporarily unavailable. Document remains quarantined.",
        )

    # 3. Clean and validated: promote from quarantine to permanent storage using Copy-Commit-Purge
    if active_object_key != document.storage_key:
        storage_service.copy_object(active_object_key, document.storage_key)

    quarantine_key_to_purge = document.quarantine_key
    document.quarantine_key = None
    document.status = "AVAILABLE"
    document.antivirus_status = "CLEAN"
    document.file_size_bytes = validation.file_size_bytes
    document.mime_type = validation.detected_mime
    document.sha256_hash = validation.sha256_hash
    document.validated_at = datetime.now(timezone.utc)
    document.rejection_reason = None

    await log_document_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        action="DOCUMENT_MALWARE_SCAN_COMPLETED",
        resource_id=document.id,
        user_id=current_user.id,
        details={"status": "CLEAN"},
        ip_address=ip,
        user_agent=ua,
    )
    await log_document_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        action="DOCUMENT_VALIDATION_PASSED",
        resource_id=document.id,
        user_id=current_user.id,
        details={
            "mime_type": validation.detected_mime,
            "sha256_hash": validation.sha256_hash,
            "file_size_bytes": validation.file_size_bytes,
        },
        ip_address=ip,
        user_agent=ua,
    )
    await log_document_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        action="DOCUMENT_UPLOAD_FINALIZED",
        resource_id=document.id,
        user_id=current_user.id,
        details={"status": "AVAILABLE", "sha256_hash": validation.sha256_hash},
        ip_address=ip,
        user_agent=ua,
    )

    try:
        await db.commit()
    except Exception as commit_err:
        logger.error(
            "document_finalization_commit_failed",
            document_id=str(document.id),
            quarantine_key=quarantine_key_to_purge,
            error=str(commit_err),
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction commit failed during document finalization. Operation is retry-safe; please retry.",
        ) from commit_err

    # Step B: Purge from quarantine post-commit (best-effort; retention cleaner will prune if this fails)
    if quarantine_key_to_purge and storage_service.object_exists(quarantine_key_to_purge):
        try:
            storage_service.delete_object(quarantine_key_to_purge)
        except Exception as purge_err:
            logger.warning(
                "quarantine_cleanup_post_finalize_failed",
                document_id=str(document.id),
                quarantine_key=quarantine_key_to_purge,
                error=str(purge_err),
            )

    await db.refresh(document)
    return DocumentResponse.model_validate(document)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata and verification status",
)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentResponse:
    """Retrieves document record. Scoped strictly by PostgreSQL RLS."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return DocumentResponse.model_validate(document)


@router.get(
    "/{document_id}/download-url",
    response_model=DocumentDownloadResponse,
    summary="Generate a short-lived presigned download URL for an accepted, clean document",
)
async def get_download_url(
    document_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentDownloadResponse:
    """Generates an authorized presigned download URL:
    1. Verifies membership in active tenant under RLS.
    2. Enforces that document status is AVAILABLE and antivirus_status is CLEAN.
    3. Fails closed (403) if validation or scan is incomplete or failed.
    4. Issues 15-minute presigned URL with Content-Disposition header.
    5. Appends audit log event without storing signed URL in audit metadata.
    """
    storage_service = get_storage_service()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Security gate: only AVAILABLE and CLEAN documents can be downloaded
    if document.status != "AVAILABLE" or document.antivirus_status != "CLEAN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Document download forbidden: File status is '{document.status}' and "
                f"antivirus status is '{document.antivirus_status}'. Only verified clean documents may be downloaded."
            ),
        )

    if not storage_service.object_exists(document.storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored document file payload was not found in storage.",
        )

    safe_name = sanitize_download_filename(document.file_name)
    disposition = f'attachment; filename="{safe_name}"'

    presigned = storage_service.generate_presigned_download_url(
        object_key=document.storage_key,
        expires_in_seconds=900,
        response_content_disposition=disposition,
    )

    # Log audit event (NO URL in metadata)
    await log_document_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        action="DOCUMENT_DOWNLOAD_URL_GENERATED",
        resource_id=document.id,
        user_id=current_user.id,
        details={
            "file_name": safe_name,
            "expires_in_seconds": presigned.expires_in_seconds,
            "sha256_hash": document.sha256_hash,
        },
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()

    return DocumentDownloadResponse(
        document_id=document.id,
        download_url=presigned.url,
        expires_in_seconds=presigned.expires_in_seconds,
        file_name=document.file_name,
        mime_type=document.mime_type,
        sha256_hash=document.sha256_hash or "",
    )


@router.delete(
    "/{document_id}",
    summary="Delete a document and purge storage objects",
)
async def delete_document(
    document_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_compliance_officer),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Deletes a document:
    1. Enforces role authorization (Owner, Admin, or Compliance Officer).
    2. Verifies document exists in active tenant.
    3. Purges storage objects from permanent and quarantine storage.
    4. Deletes database record while preserving append-only audit history.
    """
    storage_service = get_storage_service()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    file_name = document.file_name
    sha256_hash = document.sha256_hash
    storage_key_to_purge = document.storage_key
    quarantine_key_to_purge = document.quarantine_key

    # 1. Delete row from documents table within transaction
    await db.delete(document)

    # 2. Record append-only audit event within transaction
    await log_document_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        action="DOCUMENT_DELETED",
        resource_id=document_id,
        user_id=current_user.id,
        details={"file_name": file_name, "sha256_hash": sha256_hash},
        ip_address=ip,
        user_agent=ua,
    )

    try:
        await db.commit()
    except Exception as commit_err:
        logger.error(
            "document_deletion_commit_failed",
            document_id=str(document_id),
            error=str(commit_err),
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction commit failed during document deletion. Document was not deleted.",
        ) from commit_err

    # 3. Purge storage objects post-commit (if storage fails, orphaned objects are logged for reconciliation)
    for key in (storage_key_to_purge, quarantine_key_to_purge):
        if key and storage_service.object_exists(key):
            try:
                storage_service.delete_object(key)
            except Exception as e:
                logger.error(
                    "storage_object_purge_failed_post_delete_commit",
                    key=key,
                    document_id=str(document_id),
                    error=str(e),
                )

    return {"status": "deleted", "document_id": str(document_id)}


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents belonging to the active tenant",
)
async def list_documents(
    consignment_id: Optional[UUID] = Query(None, description="Filter by consignment ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by document status"),
    current_user: CurrentUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentListResponse:
    """Lists documents for active tenant with optional filtering."""
    stmt = select(Document).where(Document.tenant_id == current_user.tenant_id)
    if consignment_id:
        stmt = stmt.where(Document.consignment_id == consignment_id)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter.upper())

    stmt = stmt.order_by(Document.created_at.desc())
    results = (await db.execute(stmt)).scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in results],
        total=len(results),
    )
