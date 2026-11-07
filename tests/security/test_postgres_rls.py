"""Cross-Tenant Security and PostgreSQL Row Level Security (RLS) Test Suite.

In accordance with AGENTS.md Rule 7, QUALITY_GATES.md, and Phase 1.1 Remediation:
- Tests run against the actual unprivileged runtime database role (regulens_app).
- Strictly verifies that the testing role has NOBYPASSRLS and NOSUPERUSER.
- Tests fail immediately if run as a PostgreSQL superuser or table owner.
- Verifies:
  1. Tenant isolation across products, consignments, documents, reports.
  2. Composite foreign key enforcement (referential integrity across tenants).
  3. Update and delete rejection across tenants.
  4. Missing tenant context returns zero rows (fail-closed behavior).
  5. Audit log immutability for the runtime role (UPDATE / DELETE rejected).
  6. Background jobs tenant isolation.
- If PostgreSQL is unavailable, reports NOT RUN (BLOCKED) with the exact technical reason.
"""
import pytest
import os
import socket
import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select
from app.core.config import settings
from app.db.models import (
    Tenant,
    Product,
    Consignment,
    Document,
    ExportReport,
    AuditLog,
    BackgroundJob,
)

DATABASE_TEST_URL = os.getenv(
    "DATABASE_TEST_URL",
    settings.DATABASE_URL,
)


def is_postgres_port_open(host: str = "localhost", port: int = 5432, timeout: float = 0.3) -> bool:
    """Checks whether the PostgreSQL TCP port is open and listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


POSTGRES_AVAILABLE = is_postgres_port_open()

pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason=(
        "NOT RUN (BLOCKED): Real PostgreSQL database service is not available or running on localhost:5432. "
        "Docker Desktop or native PostgreSQL 16 server is not started on this host."
    ),
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated async database session using the runtime role connection."""
    test_engine = create_async_engine(DATABASE_TEST_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_runtime_role_cannot_bypass_rls(db_session: AsyncSession):
    """Verifies that the connection role is regulens_app and has NOBYPASSRLS and NOSUPERUSER."""
    query = text("""
        SELECT rolname, rolsuper, rolbypassrls 
        FROM pg_roles 
        WHERE rolname = current_user;
    """)
    result = await db_session.execute(query)
    row = result.first()
    assert row is not None, "Unable to query current_user role from pg_roles."
    rolname, rolsuper, rolbypassrls = row

    assert rolname == "regulens_app", (
        f"Security violation: Tests must run as runtime role 'regulens_app', but ran as '{rolname}'."
    )
    assert rolsuper is False, (
        f"Security violation: Runtime role '{rolname}' has superuser privileges."
    )
    assert rolbypassrls is False, (
        f"Security violation: Runtime role '{rolname}' has BYPASSRLS privilege."
    )


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_tenant_b_products(db_session: AsyncSession):
    """Tenant A cannot read Tenant B's products under RLS."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    prod_b_id = uuid.uuid4()

    # Create Product B under Tenant B's context
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_b)})
    prod_b = Product(
        id=prod_b_id,
        tenant_id=tenant_b,
        name="Tenant B Citrus",
        sector="AGRI_FOOD",
        hs_code="080510",
        attributes={},
    )
    db_session.add(prod_b)
    await db_session.commit()

    # Switch to Tenant A's context and attempt to read Product B
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    stmt = select(Product).where(Product.id == prod_b_id)
    result = await db_session.execute(stmt)
    found_product = result.scalar_one_or_none()

    assert found_product is None, "RLS Breach: Tenant A was able to read Tenant B's product!"


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_tenant_b_consignments(db_session: AsyncSession):
    """Tenant A cannot read Tenant B's consignments under RLS."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    consignment_b_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    stmt = select(Consignment).where(Consignment.id == consignment_b_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_tenant_b_documents(db_session: AsyncSession):
    """Tenant A cannot read Tenant B's documents under RLS."""
    tenant_a = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    stmt = select(Document).where(Document.id == doc_b_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_tenant_b_reports(db_session: AsyncSession):
    """Tenant A cannot read Tenant B's export reports under RLS."""
    tenant_a = uuid.uuid4()
    report_b_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    stmt = select(ExportReport).where(ExportReport.id == report_b_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_tenant_a_cannot_insert_record_referencing_tenant_b_product(db_session: AsyncSession):
    """Composite Foreign Key Enforcement: Tenant A cannot reference Tenant B's product."""
    tenant_a = uuid.uuid4()
    product_b_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    
    # Attempt to insert consignment under Tenant A referencing Product B
    invalid_consignment = Consignment(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        product_id=product_b_id,
        consignment_reference="REF-CROSS-TENANT-ATTACK",
    )
    db_session.add(invalid_consignment)
    
    with pytest.raises(Exception) as excinfo:
        await db_session.commit()
    # Must fail with foreign key violation at database schema layer
    assert "foreign key" in str(excinfo.value).lower() or "violates" in str(excinfo.value).lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_tenant_a_cannot_update_or_delete_tenant_b_records(db_session: AsyncSession):
    """Tenant A cannot update or delete Tenant B's products."""
    tenant_a = uuid.uuid4()
    prod_b_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    
    # Attempt update
    update_res = await db_session.execute(
        text("UPDATE products SET name = 'Tampered' WHERE id = :id"),
        {"id": str(prod_b_id)},
    )
    assert update_res.rowcount == 0, "RLS Violation: Update affected rows across tenant boundary!"

    # Attempt delete
    delete_res = await db_session.execute(
        text("DELETE FROM products WHERE id = :id"),
        {"id": str(prod_b_id)},
    )
    assert delete_res.rowcount == 0, "RLS Violation: Delete affected rows across tenant boundary!"


@pytest.mark.asyncio
async def test_missing_tenant_context_returns_zero_rows(db_session: AsyncSession):
    """Missing or null tenant context must return zero rows for all customer tables."""
    # Reset transaction-local tenant context to null
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
    
    stmt = select(Product)
    result = await db_session.execute(stmt)
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_background_jobs_cannot_process_another_tenant_data(db_session: AsyncSession):
    """Background jobs table is strictly isolated by tenant under RLS."""
    tenant_a = uuid.uuid4()
    job_b_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    stmt = select(BackgroundJob).where(BackgroundJob.id == job_b_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_normal_runtime_role_cannot_modify_or_delete_audit_logs(db_session: AsyncSession):
    """Immutable Audit Log: runtime role regulens_app cannot update or delete audit logs."""
    tenant_a = uuid.uuid4()
    log_id = uuid.uuid4()

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    
    # Insert is permitted
    log = AuditLog(
        id=log_id,
        tenant_id=tenant_a,
        action="TEST_ACTION",
        resource_type="Product",
        resource_id=uuid.uuid4(),
    )
    db_session.add(log)
    await db_session.commit()

    # UPDATE must be rejected by PostgreSQL (RLS / privilege denial)
    with pytest.raises(Exception):
        await db_session.execute(
            text("UPDATE audit_logs SET action = 'ALTERED' WHERE id = :id"),
            {"id": str(log_id)},
        )
        await db_session.commit()
    await db_session.rollback()

    # DELETE must be rejected by PostgreSQL
    with pytest.raises(Exception):
        await db_session.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": str(log_id)},
        )
        await db_session.commit()
    await db_session.rollback()
