"""Authentication and tenant switching request/response schemas."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    tenant_name: str
    country: str
    role: str
    is_current: bool


class SwitchTenantRequest(BaseModel):
    tenant_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    active_tenant_id: UUID
    active_tenant_name: str
    role: str
