"""API dependencies: authentication, database sessions, and tenant context."""
from uuid import UUID
from typing import AsyncGenerator, Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker, set_tenant_context, set_user_context
from app.db.models import Tenant, TenantUser, User
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
    """Extracts and validates user identity from JWT bearer token for authentication-only flows.
    
    NOTE: The role claim in the JWT is informational from minting time and MUST NOT
    be used for privileged authorization decisions in tenant context. Use get_current_tenant_user
    or require_role() to guarantee evaluation against the live database membership role.
    """
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
    """Resolves and authorizes the active tenant identifier from the token-bound context.
    
    Security guarantees:
    1. Rejects deprecated X-Tenant-ID header with 400 Bad Request to prevent header-spoofing.
    2. Authenticates the user via JWT bearer token.
    3. Extracts tenant_id strictly from cryptographically verified token claims.
    4. Fails closed (401 Unauthorized) when unauthenticated, invalid, or expired.
    5. Fails closed (400 Bad Request) if token carries no active tenant context.
    """
    if x_tenant_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The 'X-Tenant-ID' header is deprecated and unsupported on domain endpoints. "
                "Tenant context is strictly token-bound. "
                "Please switch tenant via POST /api/v1/auth/switch-tenant."
            ),
        )

    user = await get_current_user(authorization=authorization)
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant context: No active tenant specified in token claims.",
        )
    return user.tenant_id


async def get_tenant_db(
    authorization: Optional[str] = Header(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that sets the transaction-local app.current_tenant_id and app.current_user_id
    before yielding the session, after performing real-time status and membership checks."""
    user = await get_current_user(authorization=authorization)

    # 1. Real-time user account status check (global table, unprivileged SELECT)
    stmt_user = select(User.is_active).where(User.id == user.id)
    user_active = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Establish transaction-scoped user and tenant context
    await set_user_context(db, user.id)
    await set_tenant_context(db, tenant_id)

    # 3. Real-time tenant organization status check (RLS on tenants permits reading own row)
    stmt_tenant = select(Tenant.is_active).where(Tenant.id == tenant_id)
    tenant_active = (await db.execute(stmt_tenant)).scalar_one_or_none()
    if not tenant_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Requested tenant organization is inactive or suspended.",
        )

    # 4. Real-time membership and role check in tenant_users (RLS permits reading under tenant context)
    stmt_member = select(TenantUser.role).where(
        TenantUser.tenant_id == tenant_id,
        TenantUser.user_id == user.id,
    )
    current_role = (await db.execute(stmt_member)).scalar_one_or_none()
    if current_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User is not an active member of this organization.",
        )

    # 5. Bind live verified authorized user to the session info for downstream dependency access
    authorized_user = CurrentUser(
        id=user.id,
        email=user.email,
        role=current_role,
        tenant_id=tenant_id,
    )
    db.sync_session.info["authorized_user"] = authorized_user

    try:
        yield db
    finally:
        pass


async def get_current_tenant_user(
    db: AsyncSession = Depends(get_tenant_db),
) -> CurrentUser:
    """Provides the live database-verified CurrentUser for the active tenant.
    
    Security guarantees:
    1. Depends on get_tenant_db, guaranteeing that transaction-scoped GUCs are armed
       and that User.is_active, Tenant.is_active, and TenantUser membership were verified.
    2. role is guaranteed to be the live TenantUser.role from PostgreSQL, NEVER the stale JWT claim.
    3. Exposes the authorized user to downstream role-based access control dependencies.
    """
    authorized_user = db.sync_session.info.get("authorized_user")
    if not authorized_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Unable to resolve authorized tenant user context.",
        )
    return authorized_user


def require_role(*allowed_roles: str):
    """Factory for dependency that enforces membership role authorization.
    
    Strictly checks the live database membership role (via get_current_tenant_user),
    never the unverified or stale JWT role.
    """
    normalized_allowed = {r.strip().upper() for r in allowed_roles}

    async def role_checker(
        current_user: CurrentUser = Depends(get_current_tenant_user),
    ) -> CurrentUser:
        if not current_user.role or current_user.role.strip().upper() not in normalized_allowed:
            logger.warning(
                "role_authorization_denied",
                user_id=str(current_user.id),
                tenant_id=str(current_user.tenant_id),
                required_roles=sorted(list(normalized_allowed)),
                actual_role=current_user.role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient permissions for this operation. Required role: {', '.join(sorted(normalized_allowed))}.",
            )
        return current_user

    return role_checker


# Granular role guards adhering to docs/SECURITY_ARCHITECTURE.md
require_owner = require_role("OWNER")
require_admin = require_role("OWNER", "ADMIN")
require_compliance_officer = require_role("OWNER", "ADMIN", "COMPLIANCE_OFFICER")
require_reviewer = require_role("OWNER", "ADMIN", "COMPLIANCE_OFFICER", "HUMAN_REVIEWER")
require_viewer = require_role("OWNER", "ADMIN", "COMPLIANCE_OFFICER", "HUMAN_REVIEWER", "VIEWER")
