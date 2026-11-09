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
from typing import AsyncGenerator, Tuple

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.models import AuditLog, Product, Tenant
from app.db.session import ReguLensAppSession, async_session_maker, set_tenant_context

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


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated async database session using the runtime role connection (regulens_app)."""
    test_engine = create_async_engine(DATABASE_TEST_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest.fixture
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


@pytest.fixture
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


# ==============================================================================
# TEST SUITE
# ==============================================================================

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
    assert rolsuper is False, f"Security violation: Runtime role '{rolname}' has superuser privileges."
    assert rolbypassrls is False, f"Security violation: Runtime role '{rolname}' has BYPASSRLS privilege."


@pytest.mark.asyncio
async def test_admin_session_does_not_inherit_application_listener(admin_session: AsyncSession):
    """Verifies that administrative test sessions use standard Session and do not inherit ReguLensAppSession."""
    sync_session = admin_session.sync_session
    assert not isinstance(sync_session, ReguLensAppSession), (
        "Isolation breach: Administrative session is using ReguLensAppSession subclass!"
    )


@pytest.mark.asyncio
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
    update_res = await db_session.execute(
        text("UPDATE products SET name = 'Tenant A Clementines' WHERE id = :id"),
        {"id": str(prod_a2_id)},
    )
    assert update_res.rowcount == 1, "Tenant A failed to update own Product."
    await db_session.commit()


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_missing_tenant_context_returns_zero_rows(db_session: AsyncSession):
    """Missing or reset tenant context must return zero rows for all customer tables.
    
    Under Migration 0001: RESET sets custom GUC to '', failing with 22P02.
    Under Migration 0002: passes and returns 0 rows safely via NULLIF.
    """
    await db_session.execute(text("RESET app.current_tenant_id;"))
    stmt = select(Product)
    result = await db_session.execute(stmt)
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
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
