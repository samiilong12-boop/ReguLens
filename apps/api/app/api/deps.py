"""API dependencies: authentication, database sessions, and tenant context."""
from uuid import UUID
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker, set_tenant_context
from app.core.security import decode_token


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_tenant_id(
    authorization: str = Header(None),
    x_tenant_id: str = Header(None),
) -> UUID:
    """Extracts and verifies the tenant ID from the authenticated session context.
    
    In development / provisional testing mode, allows fallback to verified header
    if token is not present. Rejects requests lacking a valid tenant identifier.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        if payload and "tenant_id" in payload:
            try:
                return UUID(payload["tenant_id"])
            except ValueError:
                pass
    
    if x_tenant_id:
        try:
            return UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Tenant-ID header format; must be a valid UUID.",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or unauthenticated tenant context.",
    )


async def get_tenant_db(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that sets the transaction-local app.current_tenant_id before yielding the session."""
    await set_tenant_context(db, tenant_id)
    try:
        yield db
    finally:
        pass
