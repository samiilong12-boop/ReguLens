"""Integration tests for tenant context extraction, security token decoding, and tenant authorization."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from app.core.security import create_access_token, decode_token
from app.api.deps import get_current_user, get_current_tenant_id, CurrentUser
from app.db.models import TenantUser


def test_jwt_token_creation_and_decoding():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    data = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": "COMPLIANCE_OFFICER",
    }
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == str(user_id)
    assert decoded["tenant_id"] == str(tenant_id)
    assert decoded["role"] == "COMPLIANCE_OFFICER"


def test_invalid_jwt_token_returns_none():
    assert decode_token("invalid.token.structure") is None
    assert decode_token("") is None


@pytest.mark.asyncio
async def test_unauthenticated_request_fails_closed():
    """Requests lacking Authorization header fail closed with 401 Unauthorized."""
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(authorization=None)
    assert excinfo.value.status_code == 401
    assert "Authentication required" in excinfo.value.detail


@pytest.mark.asyncio
async def test_forged_x_tenant_id_without_auth_fails_closed():
    """Supplying X-Tenant-ID header without valid auth fails closed with 401."""
    fake_tenant = uuid.uuid4()
    with pytest.raises(HTTPException) as excinfo:
        await get_current_tenant_id(authorization=None, x_tenant_id=str(fake_tenant), db=AsyncMock())
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_header_fails_closed():
    """Invalid bearer token fails closed with 401."""
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(authorization="Bearer completely.invalid.token")
    assert excinfo.value.status_code == 401
    assert "Invalid or expired access token" in excinfo.value.detail


@pytest.mark.asyncio
async def test_authenticated_user_accesses_own_tenant():
    """User with verified token claim accesses their own tenant without error."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token({
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": "COMPLIANCE_OFFICER",
    })
    
    resolved_tenant = await get_current_tenant_id(
        authorization=f"Bearer {token}",
        x_tenant_id=None,
        db=AsyncMock(),
    )
    assert resolved_tenant == tenant_id


@pytest.mark.asyncio
async def test_cross_tenant_access_denied_without_membership():
    """Authenticated user attempting to access foreign tenant without membership gets 403 Forbidden."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()
    
    # Token issued for Tenant A
    token = create_access_token({
        "sub": str(user_id),
        "tenant_id": str(tenant_a),
        "role": "EXPORTER_USER",
    })
    
    # Mock db returns None (no membership in Tenant B)
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as excinfo:
        await get_current_tenant_id(
            authorization=f"Bearer {token}",
            x_tenant_id=str(tenant_b),
            db=mock_db,
        )
    assert excinfo.value.status_code == 403
    assert "User is not an authorized member of the requested tenant" in excinfo.value.detail


@pytest.mark.asyncio
async def test_cross_tenant_access_succeeds_with_valid_membership():
    """Authenticated user attempting to access another tenant where they ARE a member succeeds."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()
    
    token = create_access_token({
        "sub": str(user_id),
        "tenant_id": str(tenant_a),
        "role": "EXPORTER_USER",
    })
    
    # Mock db returns active TenantUser membership for Tenant B
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_membership = TenantUser(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        user_id=user_id,
        role="ANALYST",
    )
    mock_result.scalar_one_or_none.return_value = mock_membership
    mock_db.execute.return_value = mock_result
    
    resolved_tenant = await get_current_tenant_id(
        authorization=f"Bearer {token}",
        x_tenant_id=str(tenant_b),
        db=mock_db,
    )
    assert resolved_tenant == tenant_b

