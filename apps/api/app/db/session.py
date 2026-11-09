"""Database session management and transaction-local tenant context binding."""
from uuid import UUID
from typing import AsyncGenerator
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text
from app.core.config import settings

# Async SQLAlchemy engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


class ReguLensAppSession(Session):
    """Dedicated SQLAlchemy sync session subclass for runtime application sessions only.
    
    Ensures transaction-level event listeners are strictly scoped to the application
    runtime and are never inherited by administrative test or migration sessions.
    """
    pass


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    sync_session_class=ReguLensAppSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session per request."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Sets the PostgreSQL transaction-local session variable for Row Level Security.
    
    Using the third argument `is_local = true` ensures the configuration is strictly
    scoped to the current database transaction and automatically cleared upon commit/rollback.
    Also records tenant_id in session.sync_session.info for the application session lifecycle.
    """
    session.sync_session.info["tenant_id"] = tenant_id
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


class DatabaseSecurityError(RuntimeError):
    """Raised when connected database role violates security boundaries or role verification fails."""
    pass


async def verify_database_role(session: AsyncSession) -> str:
    """Verifies that the connected database role is the unprivileged runtime role.
    
    Fail-closed security guarantees:
    1. Rejects superuser connections (rolsuper == True).
    2. Rejects roles with BYPASSRLS privilege (rolbypassrls == True).
    3. Rejects privileged administrative roles ('postgres', 'regulens_migrator').
    4. Enforces exact match against settings.EXPECTED_DB_RUNTIME_ROLE ('regulens_app').
    5. Never leaks passwords in error messages or exceptions.
    6. Raises DatabaseSecurityError on any security policy violation or verification failure.
    """
    stmt = text("""
        SELECT rolname, rolsuper, rolbypassrls
        FROM pg_roles
        WHERE rolname = current_user;
    """)
    result = await session.execute(stmt)
    row = result.first()
    if not row:
        raise DatabaseSecurityError("Database role verification failed: Unable to query pg_roles for current_user.")

    rolname, rolsuper, rolbypassrls = row

    if rolname in {"postgres", "regulens_migrator"}:
        raise DatabaseSecurityError(
            f"Security violation: Application connected using privileged database role '{rolname}'. "
            f"The application must connect exclusively using unprivileged role '{settings.EXPECTED_DB_RUNTIME_ROLE}'."
        )

    if rolsuper:
        raise DatabaseSecurityError(
            f"Security violation: Connected database role '{rolname}' has superuser privileges."
        )

    if rolbypassrls:
        raise DatabaseSecurityError(
            f"Security violation: Connected database role '{rolname}' has BYPASSRLS privilege."
        )

    if rolname != settings.EXPECTED_DB_RUNTIME_ROLE:
        raise DatabaseSecurityError(
            f"Security violation: Connected database role '{rolname}' does not match expected runtime role '{settings.EXPECTED_DB_RUNTIME_ROLE}'."
        )

    return rolname
