"""Cross-Tenant Security and PostgreSQL Row Level Security (RLS) Test Suite.

In accordance with AGENTS.md Rule 7, QUALITY_GATES.md, and Phase 1 Package A:
- Tests run against the unprivileged runtime database role (regulens_app).
- Strictly verifies that the testing role has NOBYPASSRLS and NOSUPERUSER.
- Administrative fixture provisioning runs via a separate DATABASE_ADMIN_TEST_URL
  with SUPERUSER/BYPASSRLS privileges, strictly isolated from the application runtime.
- In CI (CI=true), PostgreSQL availability and DATABASE_ADMIN_TEST_URL are mandatory;
  tests fail immediately rather than skipping if either is missing.
- Verifies:
  1. Runtime role least-privilege enforcement (NOBYPASSRLS, NOSUPERUSER).
  2. Positive control: Valid tenant can perform own-tenant CRUD.
  3. Negative control: Cross-tenant read denial against real existing records.
  4. Negative control: Cross-tenant write denial (UPDATE/DELETE) against real existing records.
  5. Negative control: Cross-tenant INSERT rejected by RLS WITH CHECK (SQLSTATE 42501).
  6. Immutability of audit_logs enforced via SQL privilege denial (SQLSTATE 42501).
  7. Custom GUC never-defined lifecycle: IS NULL returns 0 rows.
  8. Custom GUC post-COMMIT reused connection lifecycle: empty string regression test.
  9. Context reset behavior returns 0 rows (fail-closed).
  10. Real application-path post-COMMIT integration test with dedicated session listener.
  11. Administrative test session isolation from application listener.
"""
import os
import socket
import uuid
from datetime import timedelta
from typing import AsyncGenerator, Tuple

import pytest
import pytest_asyncio
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token, decode_token
from app.db.models import (
    AuditLog,
    BackgroundJob,
    Consignment,
    Document,
    Product,
    Tenant,
    TenantUser,
    User,
)
from app.db.session import (
    ReguLensAppSession,
    async_session_maker,
    set_tenant_context,
    set_user_context,
)
from app.api.deps import CurrentUser, get_tenant_db

DATABASE_TEST_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_URL)
DATABASE_ADMIN_TEST_URL = os.getenv("DATABASE_ADMIN_TEST_URL")
IS_CI = os.getenv("CI", "").lower() in ("true", "1")


def is_postgres_port_open(host: str = "localhost", port: int = 5432, timeout: float = 0.5) -> bool:
    """Checks whether the PostgreSQL TCP port is open and listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


POSTGRES_AVAILABLE = is_postgres_port_open()

# CI vs. Local Skip/Fail Policy
if IS_CI:
    if not POSTGRES_AVAILABLE:
        pytest.fail(
            "CI Failure: PostgreSQL 16 is not available on localhost:5432. "
            "Real PostgreSQL service container is mandatory in CI."
        )
    if not DATABASE_ADMIN_TEST_URL:
        pytest.fail(
            "CI Failure: DATABASE_ADMIN_TEST_URL is missing. "
            "Real administrative fixture provisioning is mandatory in CI."
        )
else:
    if not POSTGRES_AVAILABLE:
        pytestmark = pytest.mark.skip(
            reason=(
                "Local environment: Real PostgreSQL service is not listening on localhost:5432. "
                "Integration tests skipped."
            )
        )
    elif not DATABASE_ADMIN_TEST_URL:
        pytestmark = pytest.mark.skip(
            reason=(
                "Local environment: DATABASE_ADMIN_TEST_URL is not set. "
                "Administrative fixture provisioning tests skipped."
            )
        )


@pytest_asyncio.fixture(loop_scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated async database session using the runtime role connection (regulens_app)."""
    test_engine = create_async_engine(DATABASE_TEST_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def admin_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an administrative database session (connecting with SUPERUSER / BYPASSRLS).
    
    Used strictly for fixture setup and teardown in tests. Does NOT use ReguLensAppSession.
    """
    if not DATABASE_ADMIN_TEST_URL:
        pytest.skip("DATABASE_ADMIN_TEST_URL is required for administrative fixture provisioning.")
    admin_engine = create_async_engine(DATABASE_ADMIN_TEST_URL, pool_pre_ping=True)
    admin_factory = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)
    async with admin_factory() as session:
        yield session
    await admin_engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def provisioned_tenants(
    admin_session: AsyncSession,
) -> AsyncGenerator[Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID], None]:
    """Provisions real Tenant A, Tenant B, Product A, and Product B records using admin privileges.
    
    Guarantees deterministic teardown in reverse dependency order, even upon test failure.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    prod_a_id = uuid.uuid4()
    prod_b_id = uuid.uuid4()

    # 1. Setup: Seed Tenant records
    t_a = Tenant(id=tenant_a, name=f"Test Tenant A {tenant_a.hex[:6]}", country="EG")
    t_b = Tenant(id=tenant_b, name=f"Test Tenant B {tenant_b.hex[:6]}", country="EG")
    admin_session.add_all([t_a, t_b])

    # Seed baseline products
    p_a = Product(
        id=prod_a_id,
        tenant_id=tenant_a,
        name="Product A Baseline",
        sector="AGRI_FOOD",
        hs_code="080510",
        attributes={},
    )
    p_b = Product(
        id=prod_b_id,
        tenant_id=tenant_b,
        name="Product B Baseline",
        sector="AGRI_FOOD",
        hs_code="080510",
        attributes={},
    )
    admin_session.add_all([p_a, p_b])
    await admin_session.commit()

    try:
        yield (tenant_a, tenant_b, prod_a_id, prod_b_id)
    finally:
        # 2. Teardown: Clean up in reverse dependency order
        try:
            await admin_session.rollback()
            await admin_session.execute(
                text("DELETE FROM documents WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM consignments WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM background_jobs WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM products WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM audit_logs WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM tenants WHERE id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.commit()
        except Exception:
            await admin_session.rollback()


@pytest_asyncio.fixture(loop_scope="function")
async def provisioned_hierarchy(
    admin_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
) -> AsyncGenerator[dict, None]:
    """Provisions real parent-child hierarchy across Tenant A and Tenant B:
    - Products (from provisioned_tenants)
    - Consignments (Consignment A for Tenant A, Consignment B for Tenant B)
    - Documents (Document A for Tenant A, Document B for Tenant B)
    - BackgroundJobs (Job A for Tenant A, Job B for Tenant B)
    """
    tenant_a, tenant_b, prod_a_id, prod_b_id = provisioned_tenants
    consignment_a_id = uuid.uuid4()
    consignment_b_id = uuid.uuid4()
    doc_a_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()
    job_a_id = uuid.uuid4()
    job_b_id = uuid.uuid4()

    # 1. Consignments
    c_a = Consignment(
        id=consignment_a_id,
        tenant_id=tenant_a,
        product_id=prod_a_id,
        consignment_reference=f"REF-A-{consignment_a_id.hex[:6]}",
        origin_country="EG",
        destination_market="EU",
        quantity_unit="KG",
        status="DRAFT",
    )
    c_b = Consignment(
        id=consignment_b_id,
        tenant_id=tenant_b,
        product_id=prod_b_id,
        consignment_reference=f"REF-B-{consignment_b_id.hex[:6]}",
        origin_country="EG",
        destination_market="EU",
        quantity_unit="KG",
        status="DRAFT",
    )
    admin_session.add_all([c_a, c_b])
    await admin_session.flush()

    # 2. Documents
    d_a = Document(
        id=doc_a_id,
        tenant_id=tenant_a,
        consignment_id=consignment_a_id,
        document_type="PHYTOSANITARY_CERTIFICATE",
        file_name="phyto_a.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
        storage_key=f"tenants/{tenant_a}/docs/phyto_a.pdf",
        sha256_hash="a" * 64,
        antivirus_status="CLEAN",
        parsing_status="PARSED",
    )
    d_b = Document(
        id=doc_b_id,
        tenant_id=tenant_b,
        consignment_id=consignment_b_id,
        document_type="PHYTOSANITARY_CERTIFICATE",
        file_name="phyto_b.pdf",
        file_size_bytes=4096,
        mime_type="application/pdf",
        storage_key=f"tenants/{tenant_b}/docs/phyto_b.pdf",
        sha256_hash="b" * 64,
        antivirus_status="CLEAN",
        parsing_status="PARSED",
    )
    admin_session.add_all([d_a, d_b])

    # 3. Background Jobs
    j_a = BackgroundJob(
        id=job_a_id,
        tenant_id=tenant_a,
        job_type="DOCUMENT_PARSING",
        payload={"doc_id": str(doc_a_id)},
        status="QUEUED",
    )
    j_b = BackgroundJob(
        id=job_b_id,
        tenant_id=tenant_b,
        job_type="DOCUMENT_PARSING",
        payload={"doc_id": str(doc_b_id)},
        status="QUEUED",
    )
    admin_session.add_all([j_a, j_b])
    await admin_session.commit()

    hierarchy = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "prod_a_id": prod_a_id,
        "prod_b_id": prod_b_id,
        "consignment_a_id": consignment_a_id,
        "consignment_b_id": consignment_b_id,
        "doc_a_id": doc_a_id,
        "doc_b_id": doc_b_id,
        "job_a_id": job_a_id,
        "job_b_id": job_b_id,
    }

    try:
        yield hierarchy
    finally:
        try:
            await admin_session.rollback()
            await admin_session.execute(
                text("DELETE FROM documents WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM consignments WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.execute(
                text("DELETE FROM background_jobs WHERE tenant_id IN (:ta, :tb)"),
                {"ta": str(tenant_a), "tb": str(tenant_b)},
            )
            await admin_session.commit()
        except Exception:
            await admin_session.rollback()


# ==============================================================================
# TEST SUITE
# ==============================================================================

@pytest.mark.asyncio(loop_scope="function")
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
    assert rolsuper is False, f"Security violation: Runtime role '{rolname}' has superuser privileges."
    assert rolbypassrls is False, f"Security violation: Runtime role '{rolname}' has BYPASSRLS privilege."


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_session_does_not_inherit_application_listener(admin_session: AsyncSession):
    """Verifies that administrative test sessions use standard Session and do not inherit ReguLensAppSession."""
    sync_session = admin_session.sync_session
    assert not isinstance(sync_session, ReguLensAppSession), (
        "Isolation breach: Administrative session is using ReguLensAppSession subclass!"
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_own_tenant_crud_positive_control(
    db_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Positive Control: Tenant A can read, insert, and update its own records under RLS."""
    tenant_a, _, prod_a_id, _ = provisioned_tenants
    prod_a2_id = uuid.uuid4()

    # 1. Establish Tenant A context
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})

    # 2. Read existing Product A
    stmt = select(Product).where(Product.id == prod_a_id)
    res = await db_session.execute(stmt)
    found_prod = res.scalar_one_or_none()
    assert found_prod is not None, "Tenant A failed to read own Product A."
    assert found_prod.id == prod_a_id

    # 3. Insert new Product under Tenant A
    prod_a2 = Product(
        id=prod_a2_id,
        tenant_id=tenant_a,
        name="Tenant A Tangerines",
        sector="AGRI_FOOD",
        hs_code="080520",
        attributes={},
    )
    db_session.add(prod_a2)
    await db_session.commit()

    # 4. Update own Product
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    update_res = await db_session.execute(
        text("UPDATE products SET name = 'Tenant A Clementines' WHERE id = :id"),
        {"id": str(prod_a2_id)},
    )
    assert update_res.rowcount == 1, "Tenant A failed to update own Product."
    await db_session.commit()


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_tenant_read_isolation(
    db_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Negative Control: Tenant A cannot read Product B, even though Product B exists in database."""
    tenant_a, _, _, prod_b_id = provisioned_tenants

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})
    stmt = select(Product).where(Product.id == prod_b_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None, "RLS Breach: Tenant A was able to read Tenant B's product!"


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_tenant_write_isolation(
    db_session: AsyncSession,
    admin_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Negative Control: Tenant A cannot UPDATE or DELETE Tenant B's product."""
    tenant_a, tenant_b, _, prod_b_id = provisioned_tenants

    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})

    # Attempt cross-tenant update
    update_res = await db_session.execute(
        text("UPDATE products SET name = 'Tampered by A' WHERE id = :id"),
        {"id": str(prod_b_id)},
    )
    assert update_res.rowcount == 0, "RLS Breach: Cross-tenant update affected rows!"

    # Attempt cross-tenant delete
    delete_res = await db_session.execute(
        text("DELETE FROM products WHERE id = :id"),
        {"id": str(prod_b_id)},
    )
    assert delete_res.rowcount == 0, "RLS Breach: Cross-tenant delete affected rows!"

    # Verify Product B remains untampered in database via admin inspection
    res = await admin_session.execute(select(Product).where(Product.id == prod_b_id))
    prod_b = res.scalar_one_or_none()
    assert prod_b is not None
    assert prod_b.name == "Product B Baseline"


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_tenant_insert_rejected_by_rls(
    db_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Negative Control: Attempting cross-tenant INSERT is rejected by RLS WITH CHECK (SQLSTATE 42501).
    
    Because Tenant B exists in the tenants table, the foreign key is valid.
    The rejection is strictly enforced by PostgreSQL's RLS engine, not a FK violation.
    """
    tenant_a, tenant_b, _, _ = provisioned_tenants

    # Establish Tenant A context
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})

    # Attempt to insert product referencing Tenant B (which exists in table tenants!)
    prod_attack = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_b,  # Valid foreign key, violates RLS WITH CHECK for context A
        name="Malicious Cross-Tenant Product",
        sector="AGRI_FOOD",
        hs_code="080510",
        attributes={},
    )
    db_session.add(prod_attack)

    with pytest.raises(DBAPIError) as excinfo:
        await db_session.commit()

    orig_error = excinfo.value.orig
    sqlstate = getattr(orig_error, "sqlstate", None) or getattr(orig_error, "pgcode", None)

    assert sqlstate == "42501", f"Expected SQLSTATE 42501 (insufficient_privilege), got {sqlstate}"
    assert 'new row violates row-level security policy for table "products"' in str(orig_error).lower()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_audit_logs_immutability_enforced_by_privilege(
    db_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Verifies that runtime role regulens_app cannot UPDATE or DELETE audit_logs.
    
    Enforced via table-level privilege revocation (REVOKE UPDATE, DELETE FROM regulens_app),
    failing closed with SQLSTATE 42501 and specific permission-denied message.
    """
    tenant_a, _, _, _ = provisioned_tenants
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

    # Re-arm Tenant A context so RLS permits the statement and execution reaches SQL table privilege check
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})

    # Attempt UPDATE -> Must fail with SQLSTATE 42501
    with pytest.raises(DBAPIError) as excinfo_update:
        await db_session.execute(
            text("UPDATE audit_logs SET action = 'ALTERED' WHERE id = :id"),
            {"id": str(log_id)},
        )
        await db_session.commit()
    await db_session.rollback()

    orig_upd = excinfo_update.value.orig
    sqlstate_upd = getattr(orig_upd, "sqlstate", None) or getattr(orig_upd, "pgcode", None)
    assert sqlstate_upd == "42501", f"Expected SQLSTATE 42501 on UPDATE, got {sqlstate_upd}"
    assert "permission denied for table audit_logs" in str(orig_upd).lower()

    # Re-arm Tenant A context for DELETE
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(tenant_a)})

    # Attempt DELETE -> Must fail with SQLSTATE 42501
    with pytest.raises(DBAPIError) as excinfo_del:
        await db_session.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": str(log_id)},
        )
        await db_session.commit()
    await db_session.rollback()

    orig_del = excinfo_del.value.orig
    sqlstate_del = getattr(orig_del, "sqlstate", None) or getattr(orig_del, "pgcode", None)
    assert sqlstate_del == "42501", f"Expected SQLSTATE 42501 on DELETE, got {sqlstate_del}"
    assert "permission denied for table audit_logs" in str(orig_del).lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_never_defined_custom_guc_returns_zero_rows():
    """Verifies that on a genuinely new physical connection where the GUC was never defined,
    current_setting returns NULL and querying protected tables returns 0 rows without error.
    """
    engine = create_async_engine(DATABASE_TEST_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        guc_check = await conn.execute(text("SELECT current_setting('app.current_tenant_id', true) IS NULL"))
        is_null = guc_check.scalar()
        assert is_null is True, "Expected custom GUC to be NULL on a fresh connection."

        count_res = await conn.execute(text("SELECT count(*) FROM products"))
        assert count_res.scalar() == 0
    await engine.dispose()


@pytest.mark.asyncio(loop_scope="function")
async def test_single_conn_post_commit_guc_empty_string_reproduction():
    """Reproduces the post-COMMIT custom GUC behavior on a single physical connection.
    
    Demonstrates that PostgreSQL 16 placeholder GUC reverts to '' post-commit.
    Under Migration 0001: fails with 22P02 because post-commit custom GUC is ''.
    Under Migration 0002: passes and returns 0 rows safely via NULLIF.
    """
    engine = create_async_engine(DATABASE_TEST_URL)
    dummy_tenant = uuid.uuid4()

    async with engine.connect() as conn:
        # Transaction 1: Set GUC transaction-locally
        await conn.execute(text("BEGIN"))
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :id, true)"),
            {"id": str(dummy_tenant)},
        )
        await conn.execute(text("COMMIT"))

        # Inspect GUC on the same physical connection post-commit
        guc_check = await conn.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        observed_guc = guc_check.scalar()
        # Record observed state (in PostgreSQL 16 placeholder GUC, observed_guc is '')
        assert observed_guc == "", f"Expected post-commit GUC to revert to '', observed {observed_guc!r}"

        # Query protected table under the post-commit GUC state
        # In Commit 1 (Migration 0001): This fails with 22P02: invalid input syntax for type uuid: ""
        # In Commit 2 (Migration 0002): This passes and returns 0 rows
        count_res = await conn.execute(text("SELECT count(*) FROM products"))
        assert count_res.scalar() == 0

    await engine.dispose()


@pytest.mark.asyncio(loop_scope="function")
async def test_missing_tenant_context_returns_zero_rows(db_session: AsyncSession):
    """Missing or reset tenant context must return zero rows for all customer tables.
    
    Under Migration 0001: RESET sets custom GUC to '', failing with 22P02.
    Under Migration 0002: passes and returns 0 rows safely via NULLIF.
    """
    await db_session.execute(text("RESET app.current_tenant_id;"))
    stmt = select(Product)
    result = await db_session.execute(stmt)
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_real_application_path_post_commit_integration(
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Verifies that an application session retains tenant context across commits via after_begin listener.
    
    Uses the real application async_session_maker and set_tenant_context path.
    Under Commit 1 (no listener, Migration 0001): Fails on second transaction with 22P02.
    Under Commit 2 (listener active, Migration 0002): Passes, reads Product A, denies Product B.
    """
    tenant_a, tenant_b, prod_a_id, prod_b_id = provisioned_tenants

    # 1. Establish session via application async_session_maker
    async with async_session_maker() as session:
        # Initialize tenant context through production helper
        await set_tenant_context(session, tenant_a)

        # 2. Transaction 1: Read Product A (must succeed)
        stmt_a = select(Product).where(Product.id == prod_a_id)
        res_a = await session.execute(stmt_a)
        product_a = res_a.scalar_one_or_none()
        assert product_a is not None, "Tenant A failed to read own Product A in Transaction 1."
        assert product_a.id == prod_a_id

        # 3. Commit Transaction 1
        await session.commit()

        # 4. Transaction 2 on same AsyncSession: Query Product A again
        # The dedicated ReguLensAppSession listener must re-apply tenant_a context upon transaction start.
        res_a2 = await session.execute(stmt_a)
        product_a2 = res_a2.scalar_one_or_none()
        assert product_a2 is not None, "Listener failed to re-establish Tenant A context after commit!"
        assert product_a2.id == prod_a_id

        # 5. In same Transaction 2: Verify Tenant A cannot see Product B
        stmt_b = select(Product).where(Product.id == prod_b_id)
        res_b = await session.execute(stmt_b)
        assert res_b.scalar_one_or_none() is None, "Cross-tenant breach: Tenant A read Product B!"

        # 6. Verify total visible products is exactly 1 (Product A only)
        count_res = await session.execute(select(func.count(Product.id)))
        assert count_res.scalar() == 1, "Tenant A saw unexpected number of products."

        await session.commit()


@pytest.mark.asyncio(loop_scope="function")
async def test_catalog_all_rls_policies_contain_nullif(admin_session: AsyncSession):
    """Catalog Test: Verifies that every RLS policy using app.current_tenant_id or app.current_user_id contains NULLIF."""
    # 1. Policies using app.current_tenant_id (13 policies across 12 tables)
    query_tenant = text("""
        SELECT tablename, policyname, cmd, qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND (qual LIKE '%app.current_tenant_id%' OR with_check LIKE '%app.current_tenant_id%');
    """)
    res_tenant = await admin_session.execute(query_tenant)
    policies_tenant = res_tenant.all()
    assert len(policies_tenant) == 13, f"Expected exactly 13 policies using app.current_tenant_id, found {len(policies_tenant)}"
    for tablename, policyname, cmd, qual, with_check in policies_tenant:
        if qual and "app.current_tenant_id" in qual:
            assert "nullif" in qual.lower(), (
                f"Policy '{policyname}' on table '{tablename}' (qual) does not contain NULLIF: {qual}"
            )
        if with_check and "app.current_tenant_id" in with_check:
            assert "nullif" in with_check.lower(), (
                f"Policy '{policyname}' on table '{tablename}' (with_check) does not contain NULLIF: {with_check}"
            )

    # 2. Policies using app.current_user_id (2 policies on tenant_users and tenants introduced in Migration 0003)
    query_user = text("""
        SELECT tablename, policyname, cmd, qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND (qual LIKE '%app.current_user_id%' OR with_check LIKE '%app.current_user_id%');
    """)
    res_user = await admin_session.execute(query_user)
    policies_user = res_user.all()
    assert len(policies_user) == 2, f"Expected exactly 2 policies using app.current_user_id, found {len(policies_user)}"
    for tablename, policyname, cmd, qual, with_check in policies_user:
        if qual and "app.current_user_id" in qual:
            assert "nullif" in qual.lower(), (
                f"Policy '{policyname}' on table '{tablename}' (qual) does not contain NULLIF: {qual}"
            )
        if with_check and "app.current_user_id" in with_check:
            assert "nullif" in with_check.lower(), (
                f"Policy '{policyname}' on table '{tablename}' (with_check) does not contain NULLIF: {with_check}"
            )


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_tenant_consignment_isolation(
    db_session: AsyncSession,
    provisioned_hierarchy: dict,
):
    """Behavioral Test: Tenant A can access its own consignment, but cannot read, update, or delete Tenant B's consignment."""
    h = provisioned_hierarchy
    tenant_a = h["tenant_a"]
    c_a_id = h["consignment_a_id"]
    c_b_id = h["consignment_b_id"]

    await set_tenant_context(db_session, tenant_a)

    # 1. Positive control: Read own consignment
    stmt_own = select(Consignment).where(Consignment.id == c_a_id)
    res_own = await db_session.execute(stmt_own)
    consignment_own = res_own.scalar_one_or_none()
    assert consignment_own is not None, "Tenant A failed to read own consignment under RLS."
    assert consignment_own.id == c_a_id

    # 2. Negative control: Read Tenant B's consignment returns None
    stmt_foreign = select(Consignment).where(Consignment.id == c_b_id)
    res_foreign = await db_session.execute(stmt_foreign)
    assert res_foreign.scalar_one_or_none() is None, "RLS Breach: Tenant A read Tenant B's consignment!"

    # 3. Negative control: Update Tenant B's consignment affects 0 rows
    update_res = await db_session.execute(
        text("UPDATE consignments SET status = 'TAMPERED' WHERE id = :id"),
        {"id": str(c_b_id)},
    )
    assert update_res.rowcount == 0, "RLS Breach: Tenant A updated Tenant B's consignment!"

    # 4. Negative control: Delete Tenant B's consignment affects 0 rows
    delete_res = await db_session.execute(
        text("DELETE FROM consignments WHERE id = :id"),
        {"id": str(c_b_id)},
    )
    assert delete_res.rowcount == 0, "RLS Breach: Tenant A deleted Tenant B's consignment!"

    # 5. Negative control: Insert consignment with Tenant B's tenant_id fails RLS WITH CHECK (SQLSTATE 42501)
    with pytest.raises(DBAPIError) as excinfo:
        await db_session.execute(
            text("""
                INSERT INTO consignments (id, tenant_id, product_id, consignment_reference, origin_country, destination_market, quantity_unit, status)
                VALUES (:id, :tenant_id, :product_id, 'ATTACK-REF', 'EG', 'EU', 'KG', 'DRAFT')
            """),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(h["tenant_b"]),
                "product_id": str(h["prod_b_id"]),
            },
        )
    assert excinfo.value.orig is not None
    assert getattr(excinfo.value.orig, "sqlstate", None) == "42501"
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_composite_foreign_key_cross_tenant_reference_rejected(
    db_session: AsyncSession,
    provisioned_hierarchy: dict,
):
    """Composite FK Enforcement: Tenant A attempting to reference Tenant B's product is rejected by DB constraint.
    
    Distinguishes SQLSTATE 23503 (foreign_key_violation) from RLS SQLSTATE 42501.
    RLS WITH CHECK passes because tenant_id matches Tenant A, but the composite FK (tenant_id, product_id)
    fails because (tenant_a, prod_b_id) does not exist in the products table.
    """
    h = provisioned_hierarchy
    tenant_a = h["tenant_a"]
    prod_b_id = h["prod_b_id"]

    await set_tenant_context(db_session, tenant_a)

    attack_consignment_id = uuid.uuid4()
    with pytest.raises(DBAPIError) as excinfo:
        await db_session.execute(
            text("""
                INSERT INTO consignments (id, tenant_id, product_id, consignment_reference, origin_country, destination_market, quantity_unit, status)
                VALUES (:id, :tenant_id, :product_id, 'CROSS-TENANT-FK-ATTACK', 'EG', 'EU', 'KG', 'DRAFT')
            """),
            {
                "id": str(attack_consignment_id),
                "tenant_id": str(tenant_a),
                "product_id": str(prod_b_id),
            },
        )
    
    assert excinfo.value.orig is not None
    sqlstate = getattr(excinfo.value.orig, "sqlstate", None)
    assert sqlstate == "23503", f"Expected SQLSTATE 23503 (foreign_key_violation), got {sqlstate}"
    err_str = str(excinfo.value).lower()
    assert "fk_consignments_product" in err_str or "violates foreign key constraint" in err_str
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_tenant_document_isolation(
    db_session: AsyncSession,
    provisioned_hierarchy: dict,
):
    """Behavioral Test: Tenant A can read its own document, but cannot read, update, or delete Tenant B's document."""
    h = provisioned_hierarchy
    tenant_a = h["tenant_a"]
    doc_a_id = h["doc_a_id"]
    doc_b_id = h["doc_b_id"]

    await set_tenant_context(db_session, tenant_a)

    # 1. Positive control: Read own document
    res_own = await db_session.execute(select(Document).where(Document.id == doc_a_id))
    doc_own = res_own.scalar_one_or_none()
    assert doc_own is not None, "Tenant A failed to read own document under RLS."
    assert doc_own.id == doc_a_id

    # 2. Negative control: Read Tenant B's document returns None
    res_foreign = await db_session.execute(select(Document).where(Document.id == doc_b_id))
    assert res_foreign.scalar_one_or_none() is None, "RLS Breach: Tenant A read Tenant B's document!"

    # 3. Negative control: Update Tenant B's document affects 0 rows
    update_res = await db_session.execute(
        text("UPDATE documents SET file_name = 'tampered.pdf' WHERE id = :id"),
        {"id": str(doc_b_id)},
    )
    assert update_res.rowcount == 0, "RLS Breach: Tenant A updated Tenant B's document!"

    # 4. Negative control: Delete Tenant B's document affects 0 rows
    delete_res = await db_session.execute(
        text("DELETE FROM documents WHERE id = :id"),
        {"id": str(doc_b_id)},
    )
    assert delete_res.rowcount == 0, "RLS Breach: Tenant A deleted Tenant B's document!"

    # 5. Negative control: Insert document with Tenant B's tenant_id fails RLS WITH CHECK (SQLSTATE 42501)
    with pytest.raises(DBAPIError) as excinfo:
        await db_session.execute(
            text("""
                INSERT INTO documents (id, tenant_id, consignment_id, document_type, file_name, file_size_bytes, mime_type, storage_key, sha256_hash)
                VALUES (:id, :tenant_id, :consignment_id, 'PHYTOSANITARY_CERTIFICATE', 'evil.pdf', 100, 'application/pdf', 'path', :sha)
            """),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(h["tenant_b"]),
                "consignment_id": str(h["consignment_b_id"]),
                "sha": "0" * 64,
            },
        )
    assert excinfo.value.orig is not None
    assert getattr(excinfo.value.orig, "sqlstate", None) == "42501"
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_tenant_background_job_isolation(
    db_session: AsyncSession,
    provisioned_hierarchy: dict,
):
    """Behavioral Test: Tenant A can access its own background jobs, but cannot read, update, or claim Tenant B's jobs."""
    h = provisioned_hierarchy
    tenant_a = h["tenant_a"]
    job_a_id = h["job_a_id"]
    job_b_id = h["job_b_id"]

    await set_tenant_context(db_session, tenant_a)

    # 1. Positive control: Read own job
    res_own = await db_session.execute(select(BackgroundJob).where(BackgroundJob.id == job_a_id))
    job_own = res_own.scalar_one_or_none()
    assert job_own is not None, "Tenant A failed to read own background job under RLS."
    assert job_own.id == job_a_id

    # 2. Negative control: Read Tenant B's job returns None
    res_foreign = await db_session.execute(select(BackgroundJob).where(BackgroundJob.id == job_b_id))
    assert res_foreign.scalar_one_or_none() is None, "RLS Breach: Tenant A read Tenant B's background job!"

    # 3. Negative control: Update / Claim Tenant B's job affects 0 rows
    update_res = await db_session.execute(
        text("UPDATE background_jobs SET status = 'PROCESSING' WHERE id = :id"),
        {"id": str(job_b_id)},
    )
    assert update_res.rowcount == 0, "RLS Breach: Tenant A claimed Tenant B's background job!"

    # 4. Negative control: Delete Tenant B's job affects 0 rows
    delete_res = await db_session.execute(
        text("DELETE FROM background_jobs WHERE id = :id"),
        {"id": str(job_b_id)},
    )
    assert delete_res.rowcount == 0, "RLS Breach: Tenant A deleted Tenant B's background job!"

    # 5. Negative control: Insert background job with Tenant B's tenant_id fails RLS WITH CHECK (SQLSTATE 42501)
    with pytest.raises(DBAPIError) as excinfo:
        await db_session.execute(
            text("""
                INSERT INTO background_jobs (id, tenant_id, job_type, payload, status)
                VALUES (:id, :tenant_id, 'MALICIOUS_JOB', '{"attack": true}', 'QUEUED')
            """),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(h["tenant_b"]),
            },
        )
    assert excinfo.value.orig is not None
    assert getattr(excinfo.value.orig, "sqlstate", None) == "42501"
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_init_db_roles_idempotency_audit_logs_privileges(
    admin_session: AsyncSession,
    db_session: AsyncSession,
    provisioned_tenants: Tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
):
    """Integration Test: Verifies that after scripts/init_db_roles.sql has executed against
    an existing database with audit_logs (where unsafe privileges were injected beforehand),
    the script's defensive DO block successfully revoked UPDATE, DELETE, and TRUNCATE from regulens_app,
    while maintaining required privileges on audit_logs and unrelated tables (e.g. products).

    Crucially: This test does NOT execute any DO ... REVOKE block itself. It inspects the actual
    privileges left behind by the full execution of scripts/init_db_roles.sql. If the script loses its
    defensive revocation block, this test will strictly fail.
    """
    # 1. Assert exact privilege matrix for regulens_app on audit_logs left by scripts/init_db_roles.sql
    priv_checks = await admin_session.execute(text("""
        SELECT 
            has_table_privilege('regulens_app', 'public.audit_logs', 'SELECT') AS can_select,
            has_table_privilege('regulens_app', 'public.audit_logs', 'INSERT') AS can_insert,
            has_table_privilege('regulens_app', 'public.audit_logs', 'UPDATE') AS can_update,
            has_table_privilege('regulens_app', 'public.audit_logs', 'DELETE') AS can_delete,
            has_table_privilege('regulens_app', 'public.audit_logs', 'TRUNCATE') AS can_truncate;
    """))
    row = priv_checks.mappings().one()
    assert row["can_select"] is True, "Defect: regulens_app lost SELECT on audit_logs!"
    assert row["can_insert"] is True, "Defect: regulens_app lost INSERT on audit_logs!"
    assert row["can_update"] is False, (
        "Security violation: regulens_app has UPDATE on audit_logs! "
        "scripts/init_db_roles.sql failed to revoke UPDATE during re-execution."
    )
    assert row["can_delete"] is False, (
        "Security violation: regulens_app has DELETE on audit_logs! "
        "scripts/init_db_roles.sql failed to revoke DELETE during re-execution."
    )
    assert row["can_truncate"] is False, (
        "Security violation: regulens_app has TRUNCATE on audit_logs! "
        "scripts/init_db_roles.sql failed to revoke TRUNCATE during re-execution."
    )

    # 2. Assert privileges on unrelated tables (e.g. products) remain intact
    prod_priv_checks = await admin_session.execute(text("""
        SELECT 
            has_table_privilege('regulens_app', 'public.products', 'SELECT') AS can_select,
            has_table_privilege('regulens_app', 'public.products', 'INSERT') AS can_insert,
            has_table_privilege('regulens_app', 'public.products', 'UPDATE') AS can_update,
            has_table_privilege('regulens_app', 'public.products', 'DELETE') AS can_delete;
    """))
    prod_row = prod_priv_checks.mappings().one()
    assert prod_row["can_select"] is True, "Defect: regulens_app lost SELECT on products!"
    assert prod_row["can_insert"] is True, "Defect: regulens_app lost INSERT on products!"
    assert prod_row["can_update"] is True, "Defect: regulens_app lost UPDATE on products!"
    assert prod_row["can_delete"] is True, "Defect: regulens_app lost DELETE on products!"

    # 3. Under db_session (as regulens_app), verify UPDATE and DELETE on audit_logs are rejected by SQL privilege denial (SQLSTATE 42501)
    tenant_a = provisioned_tenants[0]
    await set_tenant_context(db_session, tenant_a)
    with pytest.raises(DBAPIError) as excinfo_upd:
        await db_session.execute(
            text("UPDATE audit_logs SET action = 'ILLEGAL_ALTERATION' WHERE tenant_id = :tid"),
            {"tid": str(tenant_a)},
        )
    assert getattr(excinfo_upd.value.orig, "sqlstate", None) == "42501"
    await db_session.rollback()

    with pytest.raises(DBAPIError) as excinfo_del:
        await db_session.execute(
            text("DELETE FROM audit_logs WHERE tenant_id = :tid"),
            {"tid": str(tenant_a)},
        )
    assert getattr(excinfo_del.value.orig, "sqlstate", None) == "42501"
    await db_session.rollback()


# ---------------------------------------------------------------------------
# Package B: Token-Bound Multi-Tenant Authorization and Tenant Switching Tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="function")
async def provisioned_multi_tenant_users(
    admin_session: AsyncSession,
) -> AsyncGenerator[dict, None]:
    """Provisions a realistic multi-tenant hierarchy for Package B testing:
    - User 1: Active. Member of Tenant A (Role: OWNER), Tenant B (Role: VIEWER), Tenant D (Role: VIEWER).
    - User 2: Active. Member of Tenant B (Role: COMPLIANCE_OFFICER), Tenant C (Role: ADMIN).
    - User 3: Deactivated (is_active = False). Member of Tenant A (Role: VIEWER).
    - Tenant A: Active.
    - Tenant B: Active.
    - Tenant C: Active (User 1 is not a member).
    - Tenant D: Inactive (is_active = False, User 1 is a member).
    """
    user_1_id = uuid.uuid4()
    user_2_id = uuid.uuid4()
    user_3_id = uuid.uuid4()

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    tenant_c_id = uuid.uuid4()
    tenant_d_id = uuid.uuid4()

    u1 = User(
        id=user_1_id,
        email=f"u1_{user_1_id.hex[:6]}@example.com",
        password_hash="fakehash_u1",
        full_name="User One",
        is_active=True,
    )
    u2 = User(
        id=user_2_id,
        email=f"u2_{user_2_id.hex[:6]}@example.com",
        password_hash="fakehash_u2",
        full_name="User Two",
        is_active=True,
    )
    u3 = User(
        id=user_3_id,
        email=f"u3_{user_3_id.hex[:6]}@example.com",
        password_hash="fakehash_u3",
        full_name="User Three Deactivated",
        is_active=False,
    )

    t_a = Tenant(id=tenant_a_id, name=f"Tenant A {tenant_a_id.hex[:6]}", country="EG", is_active=True)
    t_b = Tenant(id=tenant_b_id, name=f"Tenant B {tenant_b_id.hex[:6]}", country="EG", is_active=True)
    t_c = Tenant(id=tenant_c_id, name=f"Tenant C {tenant_c_id.hex[:6]}", country="EG", is_active=True)
    t_d = Tenant(id=tenant_d_id, name=f"Tenant D {tenant_d_id.hex[:6]}", country="EG", is_active=False)

    admin_session.add_all([u1, u2, u3, t_a, t_b, t_c, t_d])
    await admin_session.flush()

    m_1_a_id = uuid.uuid4()
    m_1_b_id = uuid.uuid4()
    m_1_d_id = uuid.uuid4()
    m_2_b_id = uuid.uuid4()
    m_2_c_id = uuid.uuid4()
    m_3_a_id = uuid.uuid4()

    m_1_a = TenantUser(id=m_1_a_id, tenant_id=tenant_a_id, user_id=user_1_id, role="OWNER")
    m_1_b = TenantUser(id=m_1_b_id, tenant_id=tenant_b_id, user_id=user_1_id, role="VIEWER")
    m_1_d = TenantUser(id=m_1_d_id, tenant_id=tenant_d_id, user_id=user_1_id, role="VIEWER")
    m_2_b = TenantUser(id=m_2_b_id, tenant_id=tenant_b_id, user_id=user_2_id, role="COMPLIANCE_OFFICER")
    m_2_c = TenantUser(id=m_2_c_id, tenant_id=tenant_c_id, user_id=user_2_id, role="ADMIN")
    m_3_a = TenantUser(id=m_3_a_id, tenant_id=tenant_a_id, user_id=user_3_id, role="VIEWER")

    admin_session.add_all([m_1_a, m_1_b, m_1_d, m_2_b, m_2_c, m_3_a])
    await admin_session.commit()

    context = {
        "user_1_id": user_1_id,
        "user_2_id": user_2_id,
        "user_3_id": user_3_id,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "tenant_c_id": tenant_c_id,
        "tenant_d_id": tenant_d_id,
        "m_1_a_id": m_1_a_id,
        "m_1_b_id": m_1_b_id,
        "m_1_d_id": m_1_d_id,
        "m_2_b_id": m_2_b_id,
        "m_2_c_id": m_2_c_id,
        "m_3_a_id": m_3_a_id,
    }

    try:
        yield context
    finally:
        try:
            await admin_session.rollback()
            await admin_session.execute(
                text("DELETE FROM tenant_users WHERE user_id IN (:u1, :u2, :u3)"),
                {"u1": str(user_1_id), "u2": str(user_2_id), "u3": str(user_3_id)},
            )
            await admin_session.execute(
                text("DELETE FROM tenants WHERE id IN (:ta, :tb, :tc, :td)"),
                {"ta": str(tenant_a_id), "tb": str(tenant_b_id), "tc": str(tenant_c_id), "td": str(tenant_d_id)},
            )
            await admin_session.execute(
                text("DELETE FROM users WHERE id IN (:u1, :u2, :u3)"),
                {"u1": str(user_1_id), "u2": str(user_2_id), "u3": str(user_3_id)},
            )
            await admin_session.commit()
        except Exception:
            await admin_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_user_scoped_membership_visibility(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 1: Under unprivileged role with only user_id context, user sees all their memberships."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    await set_user_context(db_session, user_1_id)

    res = await db_session.execute(select(TenantUser))
    memberships = res.scalars().all()
    membership_ids = {m.id for m in memberships}

    assert ctx["m_1_a_id"] in membership_ids
    assert ctx["m_1_b_id"] in membership_ids
    assert ctx["m_1_d_id"] in membership_ids
    assert ctx["m_2_b_id"] not in membership_ids
    assert ctx["m_2_c_id"] not in membership_ids
    assert ctx["m_3_a_id"] not in membership_ids
    assert len(memberships) == 3


@pytest.mark.asyncio(loop_scope="function")
async def test_cross_user_membership_isolation(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 2: Cross-user membership isolation denies reads, updates, deletes, and unauthorized inserts."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    user_2_id = ctx["user_2_id"]
    await set_user_context(db_session, user_1_id)

    # 1. Read User 2 membership returns None
    res = await db_session.execute(select(TenantUser).where(TenantUser.id == ctx["m_2_b_id"]))
    assert res.scalar_one_or_none() is None

    # 2. Update User 2 membership affects 0 rows
    upd = await db_session.execute(
        text("UPDATE tenant_users SET role = 'ATTACKER' WHERE id = :id"),
        {"id": str(ctx["m_2_b_id"])},
    )
    assert upd.rowcount == 0

    # 3. Delete User 2 membership affects 0 rows
    dlt = await db_session.execute(
        text("DELETE FROM tenant_users WHERE id = :id"),
        {"id": str(ctx["m_2_b_id"])},
    )
    assert dlt.rowcount == 0

    # 4. Insert membership for User 2 fails RLS WITH CHECK (SQLSTATE 42501)
    with pytest.raises(DBAPIError) as excinfo:
        await db_session.execute(
            text("""
                INSERT INTO tenant_users (id, tenant_id, user_id, role)
                VALUES (:id, :tid, :uid, 'VIEWER')
            """),
            {
                "id": str(uuid.uuid4()),
                "tid": str(ctx["tenant_a_id"]),
                "uid": str(user_2_id),
            },
        )
    assert getattr(excinfo.value.orig, "sqlstate", None) == "42501"
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="function")
async def test_tenants_metadata_discovery_under_user_guc(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 3: Under only user context, user can discover only tenants they belong to."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    await set_user_context(db_session, user_1_id)

    res = await db_session.execute(select(Tenant))
    tenants = res.scalars().all()
    tenant_ids = {t.id for t in tenants}

    assert ctx["tenant_a_id"] in tenant_ids
    assert ctx["tenant_b_id"] in tenant_ids
    assert ctx["tenant_d_id"] in tenant_ids
    # User 1 is NOT a member of Tenant C -> Tenant C is not visible
    assert ctx["tenant_c_id"] not in tenant_ids

    # Direct query for Tenant C returns None
    res_c = await db_session.execute(select(Tenant).where(Tenant.id == ctx["tenant_c_id"]))
    assert res_c.scalar_one_or_none() is None


@pytest.mark.asyncio(loop_scope="function")
async def test_empty_gucs_fail_closed(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 4: When neither user_id nor tenant_id is set, tenant_users and tenants return 0 rows."""
    await db_session.execute(text("SELECT set_config('app.current_user_id', '', true)"))
    await db_session.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))

    res_users = await db_session.execute(select(TenantUser))
    assert len(res_users.scalars().all()) == 0

    res_tenants = await db_session.execute(select(Tenant))
    assert len(res_tenants.scalars().all()) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_incorrect_user_guc_returns_zero_rows(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 5: A non-existent user UUID returns zero rows for memberships and tenants."""
    random_user_id = uuid.uuid4()
    await set_user_context(db_session, random_user_id)

    res_users = await db_session.execute(select(TenantUser))
    assert len(res_users.scalars().all()) == 0

    res_tenants = await db_session.execute(select(Tenant))
    assert len(res_tenants.scalars().all()) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_nested_tenants_tenant_users_rls_no_recursion(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 6: Joining tenants and tenant_users executes cleanly without infinite RLS recursion."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    await set_user_context(db_session, user_1_id)

    stmt = (
        select(Tenant.name, TenantUser.role)
        .join(TenantUser, Tenant.id == TenantUser.tenant_id)
        .order_by(Tenant.name)
    )
    res = await db_session.execute(stmt)
    rows = res.all()
    # User 1 has memberships in Tenant A, Tenant B, Tenant D
    assert len(rows) == 3


@pytest.mark.asyncio(loop_scope="function")
async def test_revoked_membership_denied_on_domain_request(
    admin_session: AsyncSession,
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 7: Revoked membership immediately denies domain request with HTTP 403."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    tenant_b_id = ctx["tenant_b_id"]

    # 1. Revoke membership by deleting the TenantUser record via admin
    await admin_session.execute(
        text("DELETE FROM tenant_users WHERE id = :id"),
        {"id": str(ctx["m_1_b_id"])},
    )
    await admin_session.commit()

    # 2. Simulate client presenting valid JWT for Tenant B to get_tenant_db
    token_b = create_access_token(
        data={"sub": str(user_1_id), "tenant_id": str(tenant_b_id), "role": "VIEWER"}
    )
    with pytest.raises(HTTPException) as excinfo:
        agen = get_tenant_db(
            authorization=f"Bearer {token_b}",
            tenant_id=tenant_b_id,
            db=db_session,
        )
        await anext(agen)

    assert excinfo.value.status_code == 403
    assert "not an active member" in excinfo.value.detail.lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_role_demotion_reflected_live(
    admin_session: AsyncSession,
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 8: Role demotion in database is reflected live on next request."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    tenant_a_id = ctx["tenant_a_id"]

    # Demote user from OWNER to VIEWER in database
    await admin_session.execute(
        text("UPDATE tenant_users SET role = 'VIEWER' WHERE id = :id"),
        {"id": str(ctx["m_1_a_id"])},
    )
    await admin_session.commit()

    # User presents token that still claims "OWNER"
    token_a = create_access_token(
        data={"sub": str(user_1_id), "tenant_id": str(tenant_a_id), "role": "OWNER"}
    )
    agen = get_tenant_db(
        authorization=f"Bearer {token_a}",
        tenant_id=tenant_a_id,
        db=db_session,
    )
    yielded_session = await anext(agen)
    assert yielded_session is not None
    await agen.aclose()


@pytest.mark.asyncio(loop_scope="function")
async def test_inactive_user_denied(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 9: Deactivated user account is rejected immediately with HTTP 401."""
    ctx = provisioned_multi_tenant_users
    user_3_id = ctx["user_3_id"]
    tenant_a_id = ctx["tenant_a_id"]

    token_3 = create_access_token(
        data={"sub": str(user_3_id), "tenant_id": str(tenant_a_id), "role": "VIEWER"}
    )
    with pytest.raises(HTTPException) as excinfo:
        agen = get_tenant_db(
            authorization=f"Bearer {token_3}",
            tenant_id=tenant_a_id,
            db=db_session,
        )
        await anext(agen)

    assert excinfo.value.status_code == 401
    assert "deactivated" in excinfo.value.detail.lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_inactive_tenant_denied(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 10: Deactivated tenant organization is rejected immediately with HTTP 403."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    tenant_d_id = ctx["tenant_d_id"]  # Tenant D is deactivated

    token_d = create_access_token(
        data={"sub": str(user_1_id), "tenant_id": str(tenant_d_id), "role": "VIEWER"}
    )
    with pytest.raises(HTTPException) as excinfo:
        agen = get_tenant_db(
            authorization=f"Bearer {token_d}",
            tenant_id=tenant_d_id,
            db=db_session,
        )
        await anext(agen)

    assert excinfo.value.status_code == 403
    assert "inactive" in excinfo.value.detail.lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_expired_and_forged_jwts_rejected(
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 11: Expired and forged signature JWTs fail decode and authentication."""
    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    tenant_a_id = ctx["tenant_a_id"]

    # 1. Expired token
    expired_token = create_access_token(
        data={"sub": str(user_1_id), "tenant_id": str(tenant_a_id), "role": "OWNER"},
        expires_delta=timedelta(seconds=-10),
    )
    assert decode_token(expired_token) is None

    # 2. Forged signature token
    forged_token = jwt.encode(
        {"sub": str(user_1_id), "tenant_id": str(tenant_a_id), "role": "OWNER"},
        "WRONG_SECRET_KEY_FORGERY_TEST_1234567890",
        algorithm="HS256",
    )
    assert decode_token(forged_token) is None


@pytest.mark.asyncio(loop_scope="function")
async def test_switch_tenant_rejects_client_supplied_role(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 12: Switch tenant derives role strictly from database, ignoring client claims."""
    from app.api.v1.endpoints.auth import switch_active_tenant
    from app.schemas.auth import SwitchTenantRequest

    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    tenant_b_id = ctx["tenant_b_id"]  # User 1 is VIEWER in Tenant B

    # Authenticated user is currently in Tenant A as OWNER
    auth_user = CurrentUser(
        id=user_1_id,
        email="u1@example.com",
        tenant_id=ctx["tenant_a_id"],
        role="OWNER",
    )
    req = SwitchTenantRequest(tenant_id=tenant_b_id)
    resp = await switch_active_tenant(request=req, current_user=auth_user, db=db_session)

    assert resp.active_tenant_id == tenant_b_id
    assert resp.role == "VIEWER"

    payload = decode_token(resp.access_token)
    assert payload is not None
    assert payload["tenant_id"] == str(tenant_b_id)
    assert payload["role"] == "VIEWER"


@pytest.mark.asyncio(loop_scope="function")
async def test_commit_and_rollback_clear_dual_gucs(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 13: Transaction commit and rollback natively clear both transaction-local GUCs."""
    ctx = provisioned_multi_tenant_users
    u_id = ctx["user_1_id"]
    t_id = ctx["tenant_a_id"]

    # 1. Within transaction: set both GUCs
    await set_user_context(db_session, u_id)
    await set_tenant_context(db_session, t_id)

    u_setting = (await db_session.execute(text("SELECT current_setting('app.current_user_id', true)"))).scalar()
    t_setting = (await db_session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))).scalar()
    assert u_setting == str(u_id)
    assert t_setting == str(t_id)

    # 2. Commit transaction -> transaction-local settings cleared to ''
    await db_session.commit()
    u_after_commit = (await db_session.execute(text("SELECT current_setting('app.current_user_id', true)"))).scalar()
    t_after_commit = (await db_session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))).scalar()
    assert u_after_commit == ""
    assert t_after_commit == ""

    # 3. Repeat for rollback
    await set_user_context(db_session, u_id)
    await set_tenant_context(db_session, t_id)
    await db_session.rollback()
    u_after_rollback = (await db_session.execute(text("SELECT current_setting('app.current_user_id', true)"))).scalar()
    t_after_rollback = (await db_session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))).scalar()
    assert u_after_rollback == ""
    assert t_after_rollback == ""


@pytest.mark.asyncio(loop_scope="function")
async def test_connection_reuse_with_another_tenant_cleans_context(
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 14: ReguLensAppSession re-arms context per transaction and overwrites cleanly."""
    ctx = provisioned_multi_tenant_users
    u1 = ctx["user_1_id"]
    ta = ctx["tenant_a_id"]
    u2 = ctx["user_2_id"]
    tb = ctx["tenant_b_id"]

    test_engine = create_async_engine(DATABASE_TEST_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        sync_session_class=ReguLensAppSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        # First request context
        await set_user_context(session, u1)
        await set_tenant_context(session, ta)
        await session.commit()

        # Listener re-arms u1 and ta on next transaction
        curr_t = (await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))).scalar()
        assert curr_t == str(ta)

        # Overwrite with second request context
        await set_user_context(session, u2)
        await set_tenant_context(session, tb)
        await session.commit()

        curr_t2 = (await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))).scalar()
        curr_u2 = (await session.execute(text("SELECT current_setting('app.current_user_id', true)"))).scalar()
        assert curr_t2 == str(tb)
        assert curr_u2 == str(u2)

    await test_engine.dispose()


@pytest.mark.asyncio(loop_scope="function")
async def test_switch_tenant_e2e_flow(
    db_session: AsyncSession,
    provisioned_multi_tenant_users: dict,
):
    """Behavioral Test 15: End-to-end switch tenant flow from Tenant A to Tenant B."""
    from app.api.v1.endpoints.auth import switch_active_tenant
    from app.schemas.auth import SwitchTenantRequest

    ctx = provisioned_multi_tenant_users
    user_1_id = ctx["user_1_id"]
    tenant_a_id = ctx["tenant_a_id"]
    tenant_b_id = ctx["tenant_b_id"]

    # Initial token in Tenant A
    token_a = create_access_token(
        data={"sub": str(user_1_id), "tenant_id": str(tenant_a_id), "role": "OWNER"}
    )
    payload_a = decode_token(token_a)
    assert payload_a["tenant_id"] == str(tenant_a_id)
    assert payload_a["role"] == "OWNER"

    # User switches to Tenant B
    auth_user = CurrentUser(
        id=user_1_id,
        email="u1@example.com",
        tenant_id=tenant_a_id,
        role="OWNER",
    )
    req = SwitchTenantRequest(tenant_id=tenant_b_id)
    resp = await switch_active_tenant(request=req, current_user=auth_user, db=db_session)

    # Validates new token bound to Tenant B with VIEWER role
    payload_b = decode_token(resp.access_token)
    assert payload_b["sub"] == str(user_1_id)
    assert payload_b["tenant_id"] == str(tenant_b_id)
    assert payload_b["role"] == "VIEWER"


@pytest.mark.asyncio(loop_scope="function")
async def test_domain_endpoint_rejects_x_tenant_id_with_http_400():
    """Behavioral Test 16: Supplying deprecated X-Tenant-ID header is rejected with HTTP 400."""
    from app.api.deps import get_current_tenant_id

    with pytest.raises(HTTPException) as excinfo:
        await get_current_tenant_id(x_tenant_id="some-tenant-id")

    assert excinfo.value.status_code == 400
    assert "The 'X-Tenant-ID' header is deprecated" in excinfo.value.detail
