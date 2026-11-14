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
async def test_x_tenant_id_header_rejected_with_http_400():
    """Supplying deprecated X-Tenant-ID header on domain dependencies fails with 400 Bad Request."""
    fake_tenant = uuid.uuid4()
    with pytest.raises(HTTPException) as excinfo:
        await get_current_tenant_id(
            authorization=None,
            x_tenant_id=str(fake_tenant),
            db=AsyncMock(),
        )
    assert excinfo.value.status_code == 400
    assert "deprecated and unsupported" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_token_without_tenant_id_rejected_with_http_400():
    """Token lacking active tenant context fails with 400 Bad Request."""
    user_id = uuid.uuid4()
    token = create_access_token({
        "sub": str(user_id),
        "email": "user@example.com",
    })
    with pytest.raises(HTTPException) as excinfo:
        await get_current_tenant_id(
            authorization=f"Bearer {token}",
            x_tenant_id=None,
            db=AsyncMock(),
        )
    assert excinfo.value.status_code == 400
    assert "missing tenant context" in excinfo.value.detail.lower()

