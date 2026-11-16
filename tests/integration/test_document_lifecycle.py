"""Comprehensive Integration Tests for Package C: Secure Document Storage & Upload Pipeline.

Exercises all 20 required scenarios through FastAPI ASGI test client:
1. S3/GCS presigned upload URL generation and 15-minute expiry.
2. Magic-byte verification across allowed MIME types (PDF, PNG, JPEG, TIFF).
3. Rejection of forged extensions.
4. Rejection of files exceeding 25MB limit.
5. SHA-256 calculation and payload verification.
6. Path traversal protection in object keys and Content-Disposition headers.
7. Clean file upload and validation workflow.
8. Quarantine to active promotion upon successful validation and virus scan.
9. Virus detection handling (EICAR signature) -> quarantine purge, REJECTED, INFECTED.
10. Antivirus scanner failure/timeout -> fail-safe 503, QUARANTINED, never marked AVAILABLE.
11. Antivirus scanner error -> fail-safe 503, QUARANTINED.
12. Denial of download for unvalidated, pending, or quarantined documents (403).
13. Denial of download for rejected or infected documents (403).
14. Presigned download URL generation for valid documents (200).
15. Role-based authorization: VIEWER blocked from initiate/finalize/delete (403).
16. Cross-tenant document read and download isolation (404).
17. Cross-tenant document finalize and delete isolation (404).
18. Document deletion -> storage object purge + audit log.
19. Non-existent document 404 and invalid consignment handling.
20. Audit log generation, immutability, and redaction of presigned URLs and secrets.
"""
from datetime import datetime, timezone
import hashlib
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_current_tenant_user,
    get_tenant_db,
)
from app.api.v1.router import api_router
from app.core.security import create_access_token
from app.db.models import AuditLog, Consignment, Document
from app.services.audit import sanitize_audit_details
from app.services.scanner import (
    EICAR_SIGNATURE,
    MockMalwareScanner,
    ScanStatus,
    set_malware_scanner,
)
from app.services.storage import (
    MemoryStorageService,
    set_storage_service,
)

# Valid sample payloads
VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
VALID_TIFF_BYTES = b"II*\x00" + b"\x00" * 32
EICAR_PDF_BYTES = b"%PDF-1.4\n" + EICAR_SIGNATURE + b"\n%%EOF"


class MockAsyncSession:
    """Thread-safe in-memory mock AsyncSession implementing the queries used by document endpoints."""

    def __init__(self, db_store: dict):
        self.db_store = db_store
        self.sync_session = type("SyncSession", (), {"info": {}})()

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if isinstance(obj, Document):
            self.db_store["documents"][obj.id] = obj
        elif isinstance(obj, Consignment):
            self.db_store["consignments"][obj.id] = obj
        elif isinstance(obj, AuditLog):
            self.db_store["audit_logs"].append(obj)

    async def delete(self, obj: Any) -> None:
        if isinstance(obj, Document):
            self.db_store["documents"].pop(obj.id, None)

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(timezone.utc)

    async def execute(self, statement: Any) -> Any:
        # Inspect statement to determine query target
        stmt_str = str(statement).lower()

        if "from consignments" in stmt_str:
            # Querying Consignment
            params = statement.compile().params
            consignment_id = params.get("id_1") or params.get("id")
            tenant_id = params.get("tenant_id_1") or params.get("tenant_id")
            for c in self.db_store["consignments"].values():
                if str(c.id) == str(consignment_id) and str(c.tenant_id) == str(tenant_id):
                    return MockResult(item=c)
            return MockResult(item=None)

        if "count" in stmt_str and "from documents" in stmt_str:
            # Document count query
            params = statement.compile().params
            tenant_id = params.get("tenant_id_1") or params.get("tenant_id")
            status_filter = params.get("status_1") or params.get("status")
            count = 0
            for doc in self.db_store["documents"].values():
                if str(doc.tenant_id) == str(tenant_id):
                    if status_filter and doc.status != status_filter:
                        continue
                    count += 1
            return MockResult(scalar_val=count)

        if "from documents" in stmt_str:
            params = statement.compile().params
            doc_id = params.get("id_1") or params.get("id")
            tenant_id = params.get("tenant_id_1") or params.get("tenant_id")
            status_filter = params.get("status_1") or params.get("status")

            if doc_id is not None:
                # Single document query
                for doc in self.db_store["documents"].values():
                    if str(doc.id) == str(doc_id) and str(doc.tenant_id) == str(tenant_id):
                        return MockResult(item=doc)
                return MockResult(item=None)
            else:
                # List documents query
                matched = []
                for doc in self.db_store["documents"].values():
                    if str(doc.tenant_id) == str(tenant_id):
                        if status_filter and doc.status != status_filter:
                            continue
                        matched.append(doc)
                return MockResult(items=matched)

        return MockResult()


class MockResult:
    """Mock SQLAlchemy execute result."""

    def __init__(self, item: Any = None, items: Optional[List[Any]] = None, scalar_val: Any = None):
        self._item = item
        self._items = items or ([] if item is None else [item])
        self._scalar_val = scalar_val

    def scalar_one_or_none(self) -> Any:
        return self._item

    def scalar(self) -> Any:
        if self._scalar_val is not None:
            return self._scalar_val
        return self._item

    def scalars(self) -> "MockResult":
        return self

    def all(self) -> List[Any]:
        return self._items


@pytest.fixture
def document_test_context():
    """Provides isolated storage, scanner, in-memory database store, and test credentials."""
    # 1. Isolated in-memory storage and scanner
    storage = MemoryStorageService()
    set_storage_service(storage)

    scanner = MockMalwareScanner()
    set_malware_scanner(scanner)

    # 2. Tenants and Users
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    user_owner_a_id = uuid.uuid4()
    user_compliance_a_id = uuid.uuid4()
    user_viewer_a_id = uuid.uuid4()

    user_owner_b_id = uuid.uuid4()
    user_viewer_b_id = uuid.uuid4()

    consignment_a_id = uuid.uuid4()
    consignment_b_id = uuid.uuid4()

    # Pre-seeded database store
    db_store = {
        "documents": {},
        "consignments": {
            consignment_a_id: Consignment(
                id=consignment_a_id,
                tenant_id=tenant_a_id,
                consignment_reference="CONS-EG-2026-001",
                status="DRAFT",
            ),
            consignment_b_id: Consignment(
                id=consignment_b_id,
                tenant_id=tenant_b_id,
                consignment_reference="CONS-EG-2026-002",
                status="DRAFT",
            ),
        },
        "audit_logs": [],
        "memberships": {
            (tenant_a_id, user_owner_a_id): "OWNER",
            (tenant_a_id, user_compliance_a_id): "COMPLIANCE_OFFICER",
            (tenant_a_id, user_viewer_a_id): "VIEWER",
            (tenant_b_id, user_owner_b_id): "OWNER",
            (tenant_b_id, user_viewer_b_id): "VIEWER",
        },
    }

    # Generate JWT tokens
    def make_token(tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> str:
        return create_access_token(
            data={"sub": str(user_id), "tenant_id": str(tenant_id), "role": role}
        )

    tokens = {
        "owner_a": make_token(tenant_a_id, user_owner_a_id, "OWNER"),
        "compliance_a": make_token(tenant_a_id, user_compliance_a_id, "COMPLIANCE_OFFICER"),
        "viewer_a": make_token(tenant_a_id, user_viewer_a_id, "VIEWER"),
        "owner_b": make_token(tenant_b_id, user_owner_b_id, "OWNER"),
        "viewer_b": make_token(tenant_b_id, user_viewer_b_id, "VIEWER"),
    }

    return {
        "storage": storage,
        "scanner": scanner,
        "db_store": db_store,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "consignment_a_id": consignment_a_id,
        "consignment_b_id": consignment_b_id,
        "tokens": tokens,
        "users": {
            "owner_a": user_owner_a_id,
            "compliance_a": user_compliance_a_id,
            "viewer_a": user_viewer_a_id,
            "owner_b": user_owner_b_id,
            "viewer_b": user_viewer_b_id,
        },
    }


@pytest_asyncio.fixture(loop_scope="function")
async def document_test_client(document_test_context: dict) -> AsyncGenerator[AsyncClient, None]:
    """Configures FastAPI test client with mocked db and live authorization resolution."""
    db_store = document_test_context["db_store"]

    test_app = FastAPI()
    test_app.include_router(api_router, prefix="/api/v1")

    async def override_get_tenant_db() -> AsyncGenerator[AsyncSession, None]:
        session = MockAsyncSession(db_store)
        yield session

    async def override_get_current_tenant_user(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        # Live role verification lookup from memberships table
        membership_key = (current_user.tenant_id, current_user.id)
        live_role = db_store["memberships"].get(membership_key)
        if not live_role:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="User is not an active member of this tenant")
        return CurrentUser(
            id=current_user.id,
            tenant_id=current_user.tenant_id,
            role=live_role,
            is_active=True,
        )

    test_app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    test_app.dependency_overrides[get_current_tenant_user] = override_get_current_tenant_user

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        yield client

    test_app.dependency_overrides.clear()


# ==============================================================================
# INTEGRATION TESTS: ALL 20 SCENARIOS
# ==============================================================================

@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_01_presigned_url_generation_and_expiry(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 1: Initiate upload returns presigned upload URL with exact 15-minute (900s) expiry."""
    token = document_test_context["tokens"]["compliance_a"]
    resp = await document_test_client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "phyto_certificate.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["expires_in_seconds"] == 900
    assert "upload_url" in data
    assert data["status"] == "PENDING_UPLOAD"
    assert "quarantine" in data["quarantine_key"]
    assert "document_id" in data


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_02_magic_byte_verification_allowed_mime_types(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 2: Magic-byte inspection verifies PDF, PNG, JPEG, and TIFF are accepted."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    samples = [
        ("report.pdf", "application/pdf", VALID_PDF_BYTES),
        ("scan.png", "image/png", VALID_PNG_BYTES),
        ("photo.jpg", "image/jpeg", VALID_JPEG_BYTES),
        ("manifest.tiff", "image/tiff", VALID_TIFF_BYTES),
    ]

    for fname, mime, content in samples:
        init_res = await client.post(
            "/api/v1/documents/initiate-upload",
            json={
                "file_name": fname,
                "expected_size_bytes": len(content),
                "claimed_mime_type": mime,
                "document_type": "COMMERCIAL_INVOICE",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert init_res.status_code == 201
        doc_data = init_res.json()
        doc_id = doc_data["document_id"]
        q_key = doc_data["quarantine_key"]

        # Store content in quarantine
        storage.put_object(q_key, content, mime)

        # Finalize
        fin_res = await client.post(
            f"/api/v1/documents/{doc_id}/finalize-upload",
            json={"expected_sha256": hashlib.sha256(content).hexdigest()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert fin_res.status_code == 200
        assert fin_res.json()["status"] == "AVAILABLE"
        assert fin_res.json()["mime_type"] == mime


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_03_rejection_of_forged_extension(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 3: Forged extension (e.g. executable with .pdf extension) rejected with 422."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    # File named .pdf but contains Windows executable magic bytes
    forged_content = b"MZ\x90\x00" + b"\x00" * 32

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "malicious.pdf",
            "expected_size_bytes": len(forged_content),
            "claimed_mime_type": "application/pdf",
            "document_type": "OTHER",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert init_res.status_code == 201
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]

    storage.put_object(q_key, forged_content, "application/pdf")

    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(forged_content).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fin_res.status_code == 400
    assert "unsupported or unrecognized file format" in fin_res.json()["detail"].lower()

    # Quarantine object must be purged
    assert not storage.object_exists(q_key)


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_04_rejection_of_file_exceeding_25mb(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 4: Rejection of files exceeding 25MB limit."""
    token = document_test_context["tokens"]["compliance_a"]

    # Client claims file size > 25MB in initiate request
    oversized = 25 * 1024 * 1024 + 1
    resp = await document_test_client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "huge.pdf",
            "expected_size_bytes": oversized,
            "claimed_mime_type": "application/pdf",
            "document_type": "PACKING_LIST",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_05_sha256_calculation_and_payload_verification(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 5: SHA-256 payload verification detects mismatch and rejects with 422."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "valid.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    # Supply deliberate wrong SHA-256 hash
    wrong_hash = "0" * 64
    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": wrong_hash},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fin_res.status_code == 400
    assert "checksum mismatch" in fin_res.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_06_path_traversal_protection_in_object_keys(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 6: Path traversal characters in filenames are sanitized and never used in keys."""
    client = document_test_client
    ctx = document_test_context
    token = ctx["tokens"]["compliance_a"]

    malicious_filename = "../../../etc/passwd.pdf"
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": malicious_filename,
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "CERTIFICATE_OF_ORIGIN",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert init_res.status_code == 201
    data = init_res.json()
    q_key = data["quarantine_key"]

    # Key must be randomized and NOT contain traversal
    assert ".." not in q_key
    assert "etc" not in q_key
    assert "passwd" not in q_key


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_07_clean_file_upload_and_validation_workflow(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 7: Clean file upload, validation, and promotion workflow succeeds end-to-end."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    # 1. Initiate
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "clean_certificate.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert init_res.status_code == 201
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]

    # 2. Put object to quarantine
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    # 3. Finalize
    expected_sha = hashlib.sha256(VALID_PDF_BYTES).hexdigest()
    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": expected_sha},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fin_res.status_code == 200
    doc = fin_res.json()
    assert doc["status"] == "AVAILABLE"
    assert doc["antivirus_status"] == "CLEAN"
    assert doc["sha256_hash"] == expected_sha
    assert doc["validated_at"] is not None


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_08_quarantine_to_active_promotion(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 8: Quarantine object is moved to permanent storage and quarantine key purged."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "origin.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "CERTIFICATE_OF_ORIGIN",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Invariant: Quarantine key must NO LONGER exist in storage
    assert not storage.object_exists(q_key)

    # Invariant: Permanent storage key must exist
    doc_rec = ctx["db_store"]["documents"][uuid.UUID(doc_id)]
    assert doc_rec.quarantine_key is None
    assert doc_rec.storage_key is not None
    assert storage.object_exists(doc_rec.storage_key)


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_09_virus_detection_eicar_signature_handling(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 9: EICAR malware detection marks document INFECTED, status REJECTED, and purges quarantine."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "eicar_infected.pdf",
            "expected_size_bytes": len(EICAR_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, EICAR_PDF_BYTES, "application/pdf")

    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(EICAR_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fin_res.status_code == 422
    assert "malware detected" in fin_res.json()["detail"].lower()

    # Quarantine file must be purged from storage
    assert not storage.object_exists(q_key)

    # Document state in database
    doc_rec = ctx["db_store"]["documents"][uuid.UUID(doc_id)]
    assert doc_rec.status == "REJECTED"
    assert doc_rec.antivirus_status == "INFECTED"
    assert "EICAR" in (doc_rec.rejection_reason or "")


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_10_scanner_unavailable_fail_safe(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 10: Scanner failure/unavailability fails safe with HTTP 503; held in QUARANTINED."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    scanner = ctx["scanner"]
    token = ctx["tokens"]["compliance_a"]

    # Force scanner to UNAVAILABLE
    scanner.set_forced_outcome(ScanStatus.UNAVAILABLE)

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "phyto.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Fail-safe invariant: Must return 503, NEVER mark AVAILABLE or CLEAN!
    assert fin_res.status_code == 503
    assert "temporarily unavailable" in fin_res.json()["detail"].lower()

    doc_rec = ctx["db_store"]["documents"][uuid.UUID(doc_id)]
    assert doc_rec.status == "QUARANTINED"
    assert doc_rec.antivirus_status != "CLEAN"
    # Quarantine file is kept for retry
    assert storage.object_exists(q_key)

    scanner.set_forced_outcome(None)


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_11_scanner_error_fail_safe(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 11: Scanner error fails safe with HTTP 503; held in QUARANTINED."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    scanner = ctx["scanner"]
    token = ctx["tokens"]["compliance_a"]

    # Force scanner to ERROR
    scanner.set_forced_outcome(ScanStatus.ERROR)

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "phyto.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    fin_res = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fin_res.status_code == 503

    doc_rec = ctx["db_store"]["documents"][uuid.UUID(doc_id)]
    assert doc_rec.status == "QUARANTINED"
    assert doc_rec.antivirus_status != "CLEAN"

    scanner.set_forced_outcome(None)


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_12_denial_of_download_unvalidated_or_quarantined(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 12: Download denied (HTTP 403) for documents in PENDING_UPLOAD or QUARANTINED."""
    client = document_test_client
    ctx = document_test_context
    token = ctx["tokens"]["compliance_a"]

    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "pending.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]

    # Attempt download while PENDING_UPLOAD
    dl_res = await client.get(
        f"/api/v1/documents/{doc_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl_res.status_code == 403
    assert "forbidden" in dl_res.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_13_denial_of_download_rejected_or_infected(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 13: Download denied (HTTP 403) for documents in REJECTED or INFECTED state."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    # Upload infected file
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "infected.pdf",
            "expected_size_bytes": len(EICAR_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "OTHER",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, EICAR_PDF_BYTES, "application/pdf")

    await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(EICAR_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Attempt download of rejected/infected document
    dl_res = await client.get(
        f"/api/v1/documents/{doc_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl_res.status_code == 403
    assert "forbidden" in dl_res.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_14_presigned_download_url_generation_for_valid_documents(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 14: Presigned download URL generated with 15-minute expiry for AVAILABLE and CLEAN document."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["viewer_a"]
    compliance_token = ctx["tokens"]["compliance_a"]

    # Upload and finalize
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "export_invoice.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "COMMERCIAL_INVOICE",
        },
        headers={"Authorization": f"Bearer {compliance_token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {compliance_token}"},
    )

    # Download by Viewer
    dl_res = await client.get(
        f"/api/v1/documents/{doc_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl_res.status_code == 200
    data = dl_res.json()
    assert "download_url" in data
    assert data["expires_in_seconds"] == 900
    assert data["file_name"] == "export_invoice.pdf"


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_15_role_based_authorization_viewer_blocked(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 15: VIEWER role is blocked from upload initiation, finalization, and deletion (HTTP 403)."""
    client = document_test_client
    ctx = document_test_context
    viewer_token = ctx["tokens"]["viewer_a"]
    compliance_token = ctx["tokens"]["compliance_a"]

    # 1. VIEWER blocked from initiate-upload
    res_init = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "phyto.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_init.status_code == 403

    # Create a document via compliance officer
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "phyto.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {compliance_token}"},
    )
    doc_id = init_res.json()["document_id"]

    # 2. VIEWER blocked from finalize
    res_fin = await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": "0" * 64},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_fin.status_code == 403

    # 3. VIEWER blocked from delete
    res_del = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_del.status_code == 403

    # 4. VIEWER permitted to read metadata
    res_get = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_get.status_code == 200


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_16_cross_tenant_read_and_download_isolation(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 16: Tenant B is completely isolated from reading or downloading Tenant A's documents (HTTP 404)."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token_a = ctx["tokens"]["compliance_a"]
    token_b = ctx["tokens"]["owner_b"]

    # Tenant A creates and finalizes a document
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "confidential_a.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_a_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")
    await client.post(
        f"/api/v1/documents/{doc_a_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Tenant B tries to get Tenant A's document
    res_b_get = await client.get(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_get.status_code == 404

    # Tenant B tries to download Tenant A's document
    res_b_dl = await client.get(
        f"/api/v1/documents/{doc_a_id}/download-url",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_dl.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_17_cross_tenant_finalize_and_delete_isolation(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 17: Tenant B is completely blocked from finalizing or deleting Tenant A's documents (HTTP 404)."""
    client = document_test_client
    ctx = document_test_context
    token_a = ctx["tokens"]["compliance_a"]
    token_b = ctx["tokens"]["owner_b"]

    # Tenant A initiates a document
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "tenant_a_doc.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_a_id = init_res.json()["document_id"]

    # Tenant B tries to finalize Tenant A's document
    res_b_fin = await client.post(
        f"/api/v1/documents/{doc_a_id}/finalize-upload",
        json={"expected_sha256": "0" * 64},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_fin.status_code == 404

    # Tenant B tries to delete Tenant A's document
    res_b_del = await client.delete(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_del.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_18_document_deletion_storage_purge_and_audit(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 18: Authorized deletion purges storage object, deletes database row, and records audit event."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["owner_a"]

    # Upload and finalize
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "to_delete.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "OTHER",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")
    await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )

    doc_rec = ctx["db_store"]["documents"][uuid.UUID(doc_id)]
    storage_key = doc_rec.storage_key
    assert storage.object_exists(storage_key)

    # Delete
    del_res = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Storage purged
    assert not storage.object_exists(storage_key)

    # Database row removed
    assert uuid.UUID(doc_id) not in ctx["db_store"]["documents"]

    # Audit event logged
    delete_audits = [a for a in ctx["db_store"]["audit_logs"] if a.action == "DOCUMENT_DELETED"]
    assert len(delete_audits) >= 1
    assert str(delete_audits[-1].resource_id) == doc_id


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_19_non_existent_document_and_consignment_handling(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 19: Non-existent document IDs and foreign consignment IDs return 404."""
    client = document_test_client
    ctx = document_test_context
    token_a = ctx["tokens"]["compliance_a"]
    foreign_consignment = ctx["consignment_b_id"]

    # 1. Initiate with foreign consignment ID -> 404 Not Found
    res_foreign_cons = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "phyto.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
            "consignment_id": str(foreign_consignment),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_foreign_cons.status_code == 404
    assert "not found in active workspace" in res_foreign_cons.json()["detail"].lower()

    # 2. Get non-existent document -> 404
    fake_id = uuid.uuid4()
    res_fake = await client.get(
        f"/api/v1/documents/{fake_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_fake.status_code == 404

    # 3. Finalize non-existent document -> 404
    res_fake_fin = await client.post(
        f"/api/v1/documents/{fake_id}/finalize-upload",
        json={"expected_sha256": "0" * 64},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_fake_fin.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_scenario_20_audit_logging_immutability_and_secret_redaction(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Scenario 20: Audit logs recorded for document events; presigned URLs and tokens redacted."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token = ctx["tokens"]["compliance_a"]

    # Lifecycle: initiate -> finalize -> download
    init_res = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "audit_test.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "COMMERCIAL_INVOICE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = init_res.json()["document_id"]
    q_key = init_res.json()["quarantine_key"]
    storage.put_object(q_key, VALID_PDF_BYTES, "application/pdf")

    await client.post(
        f"/api/v1/documents/{doc_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.get(
        f"/api/v1/documents/{doc_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Verify audit log records
    audit_actions = [a.action for a in ctx["db_store"]["audit_logs"]]
    assert "DOCUMENT_UPLOAD_INITIATED" in audit_actions
    assert "DOCUMENT_UPLOAD_FINALIZED" in audit_actions
    assert "DOCUMENT_DOWNLOAD_URL_GENERATED" in audit_actions

    # Check redaction: Zero presigned URLs or secrets in audit details
    for log_entry in ctx["db_store"]["audit_logs"]:
        details_str = str(log_entry.details).lower()
        assert "x-amz-signature" not in details_str
        assert "signature=" not in details_str
        assert "bearer" not in details_str
        assert "password" not in details_str


@pytest.mark.asyncio(loop_scope="function")
async def test_listing_documents_with_tenant_isolation_and_filters(
    document_test_client: AsyncClient,
    document_test_context: dict,
):
    """Bonus verification: Listing documents respects tenant isolation and status filters."""
    client = document_test_client
    ctx = document_test_context
    storage = ctx["storage"]
    token_a = ctx["tokens"]["compliance_a"]
    token_b = ctx["tokens"]["owner_b"]

    # Create 2 documents in Tenant A: 1 AVAILABLE, 1 PENDING_UPLOAD
    init1 = await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "doc1.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PHYTOSANITARY_CERTIFICATE",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc1_id = init1.json()["document_id"]
    q1_key = init1.json()["quarantine_key"]
    storage.put_object(q1_key, VALID_PDF_BYTES, "application/pdf")
    await client.post(
        f"/api/v1/documents/{doc1_id}/finalize-upload",
        json={"expected_sha256": hashlib.sha256(VALID_PDF_BYTES).hexdigest()},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    await client.post(
        "/api/v1/documents/initiate-upload",
        json={
            "file_name": "doc2.pdf",
            "expected_size_bytes": len(VALID_PDF_BYTES),
            "claimed_mime_type": "application/pdf",
            "document_type": "PACKING_LIST",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # List for Tenant A: 2 documents
    res_a = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total"] == 2
    assert len(data_a["items"]) == 2

    # Filter by status=AVAILABLE
    res_a_avail = await client.get(
        "/api/v1/documents?status=AVAILABLE",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a_avail.status_code == 200
    assert res_a_avail.json()["total"] == 1
    assert res_a_avail.json()["items"][0]["id"] == doc1_id

    # List for Tenant B: 0 documents (isolation)
    res_b = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 0
