"""Add user-scoped RLS policies for tenant_users and tenants to support membership resolution.

Revision ID: 0003_membership_rls_policies
Revises: 0002_harden_rls_policies
Create Date: 2026-11-14 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003_membership_rls_policies"
down_revision: Union[str, None] = "0002_harden_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update tenant_users policies
    op.execute("DROP POLICY IF EXISTS rls_tenant_users ON tenant_users;")
    op.execute("DROP POLICY IF EXISTS rls_tenant_users_tenant_scope ON tenant_users;")
    op.execute("DROP POLICY IF EXISTS rls_tenant_users_user_scope ON tenant_users;")

    # 1a. Tenant-scoped policy: Members of active workspace can be viewed/managed by authorized users
    op.execute("""
        CREATE POLICY rls_tenant_users_tenant_scope ON tenant_users
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    # 1b. User-scoped policy: Authenticated user can SELECT their own membership rows across all tenants
    op.execute("""
        CREATE POLICY rls_tenant_users_user_scope ON tenant_users
            FOR SELECT
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    """)

    # 2. Update tenants policies
    op.execute("DROP POLICY IF EXISTS rls_tenants ON tenants;")
    op.execute("DROP POLICY IF EXISTS rls_tenants_tenant_scope ON tenants;")
    op.execute("DROP POLICY IF EXISTS rls_tenants_user_scope ON tenants;")

    # 2a. Active tenant scope: Direct isolation during domain operations
    op.execute("""
        CREATE POLICY rls_tenants_tenant_scope ON tenants
            FOR SELECT
            USING (id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    # 2b. User membership scope: Authenticated user can discover organization metadata for member tenants
    op.execute("""
        CREATE POLICY rls_tenants_user_scope ON tenants
            FOR SELECT
            USING (EXISTS (
                SELECT 1 FROM tenant_users tu
                WHERE tu.tenant_id = tenants.id
                  AND tu.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            ));
    """)


def downgrade() -> None:
    # 1. Revert tenant_users to Migration 0002 definition
    op.execute("DROP POLICY IF EXISTS rls_tenant_users_tenant_scope ON tenant_users;")
    op.execute("DROP POLICY IF EXISTS rls_tenant_users_user_scope ON tenant_users;")
    op.execute("""
        CREATE POLICY rls_tenant_users ON tenant_users
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    # 2. Revert tenants to Migration 0002 definition
    op.execute("DROP POLICY IF EXISTS rls_tenants_tenant_scope ON tenants;")
    op.execute("DROP POLICY IF EXISTS rls_tenants_user_scope ON tenants;")
    op.execute("""
        CREATE POLICY rls_tenants ON tenants
            FOR SELECT
            USING (id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)
