"""Integration tests for tenant context extraction and security token decoding."""
import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token, decode_token


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
