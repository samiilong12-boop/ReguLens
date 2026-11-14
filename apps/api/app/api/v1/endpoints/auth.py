"""Authentication, membership discovery, and secure tenant switching endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Tenant, TenantUser, User
from app.db.session import set_user_context
from app.schemas.auth import MembershipResponse, SwitchTenantRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/memberships", response_model=List[MembershipResponse])
async def list_user_memberships(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MembershipResponse]:
    """Lists all active tenant organizations the authenticated user belongs to.
    
    Security controls:
    1. Authenticates the user via bearer JWT.
    2. Rejects deactivated user accounts (401 Unauthorized).
    3. Establishes user-scoped database context (app.current_user_id) for RLS.
    4. Evaluates dual RLS policies on tenant_users and tenants.
    5. Returns only organizations where the user has verified membership and tenant is active.
    """
    # 1. Verify user account active status
    stmt_user = select(User.is_active).where(User.id == current_user.id)
    user_active = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Establish user-scoped context for RLS
    await set_user_context(db, current_user.id)

    # 3. Query memberships and tenant metadata
    stmt = (
        select(
            Tenant.id,
            Tenant.name,
            Tenant.country,
            TenantUser.role,
        )
        .join(TenantUser, Tenant.id == TenantUser.tenant_id)
        .where(TenantUser.user_id == current_user.id)
        .where(Tenant.is_active.is_(True))
        .order_by(Tenant.name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        MembershipResponse(
            tenant_id=row.id,
            tenant_name=row.name,
            country=row.country,
            role=row.role,
            is_current=(current_user.tenant_id == row.id if current_user.tenant_id else False),
        )
        for row in rows
    ]


@router.post("/switch-tenant", response_model=TokenResponse)
async def switch_active_tenant(
    request: SwitchTenantRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticates and switches the active tenant context for the user, issuing a new token.
    
    Security controls:
    1. Authenticates user via bearer JWT.
    2. Rejects deactivated user accounts (401 Unauthorized).
    3. Establishes user-scoped database context (app.current_user_id).
    4. Verifies live membership row in tenant_users and live active status in tenants.
    5. Derives user role strictly from the database, never trusting client input.
    6. Issues a new short-lived access token bound to the selected tenant.
    """
    # 1. Verify user account active status
    stmt_user = select(User.is_active).where(User.id == current_user.id)
    user_active = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Establish user-scoped context for RLS
    await set_user_context(db, current_user.id)

    # 3. Query membership and target organization status
    stmt = (
        select(
            TenantUser.role,
            Tenant.name,
            Tenant.is_active,
        )
        .join(Tenant, Tenant.id == TenantUser.tenant_id)
        .where(TenantUser.user_id == current_user.id)
        .where(TenantUser.tenant_id == request.tenant_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User is not an authorized member of the requested tenant.",
        )

    role, tenant_name, tenant_active = row

    if not tenant_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Requested tenant organization is inactive or suspended.",
        )

    # 4. Mint new access token bound to the target tenant with database-derived role
    token_data = {
        "sub": str(current_user.id),
        "tenant_id": str(request.tenant_id),
        "role": role,
        "email": current_user.email,
    }
    new_token = create_access_token(token_data)

    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        active_tenant_id=request.tenant_id,
        active_tenant_name=tenant_name,
        role=role,
    )
