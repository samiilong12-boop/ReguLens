"""API dependencies: authentication, database sessions, and tenant context."""
from uuid import UUID
from typing import AsyncGenerator, Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker, set_tenant_context
from app.db.models import TenantUser
from app.core.security import decode_token
from app.core.config import settings
from app.core.logging import logger


class CurrentUser(BaseModel):
    id: UUID
    email: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[UUID] = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> CurrentUser:
    """Extracts, validates, and decodes the authenticated user from the Authorization Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Missing subject claim in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(str(sub))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Malformed user identifier in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_tenant_id = None
    if "tenant_id" in payload and payload["tenant_id"]:
        try:
            token_tenant_id = UUID(str(payload["tenant_id"]))
        except ValueError:
            pass

    return CurrentUser(
        id=user_id,
        email=payload.get("email"),
        role=payload.get("role"),
        tenant_id=token_tenant_id,
    )


async def get_current_tenant_id(
    authorization: Optional[str] = Header(None),
    x_tenant_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Resolves and authorizes the active tenant identifier.
    
    Security guarantees:
    1. Authenticates the user first via JWT before processing any tenant claims.
    2. Never trusts client-supplied X-Tenant-ID without membership verification.
    3. Fails closed (401 Unauthorized) when unauthenticated, invalid, or expired.
    4. Fails closed (403 Forbidden) if the user is not an authorized member of the requested tenant.
    5. Fails closed in production or non-development environments if any dev bypass is attempted.
    """
    env = (settings.ENVIRONMENT or "").strip().lower()

    # Check for temporary development-only bypass
    if not authorization or not authorization.startswith("Bearer "):
        if (
            env == "development"
            and settings.ALLOW_DEV_TENANT_BYPASS is True
            and x_tenant_id
        ):
            logger.warning(
                "dev_tenant_bypass_active",
                environment=env,
                message="Allowing unauthenticated X-Tenant-ID header solely due to explicit dev bypass flag.",
            )
            try:
                return UUID(x_tenant_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid X-Tenant-ID header format; must be a valid UUID.",
                )

        # Fail closed for all other cases
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Authenticate the user
    user = await get_current_user(authorization=authorization)

    # Determine requested tenant
    requested_tenant_id: Optional[UUID] = None
    if x_tenant_id:
        try:
            requested_tenant_id = UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Tenant-ID header format; must be a valid UUID.",
            )
    elif user.tenant_id:
        requested_tenant_id = user.tenant_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant context: No active tenant specified in token claims or request headers.",
        )

    # Verify tenant membership:
    # If the token was issued specifically for this tenant, token carries verified membership claim.
    if user.tenant_id == requested_tenant_id and user.role:
        return requested_tenant_id

    # Verify in tenant_users table if accessing a different tenant than token's default
    try:
        stmt = select(TenantUser).where(
            TenantUser.user_id == user.id,
            TenantUser.tenant_id == requested_tenant_id,
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: User is not an authorized member of the requested tenant.",
            )
        return requested_tenant_id
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "tenant_authorization_check_failed",
            error=str(exc),
            user_id=str(user.id),
            tenant_id=str(requested_tenant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unable to verify tenant membership.",
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
