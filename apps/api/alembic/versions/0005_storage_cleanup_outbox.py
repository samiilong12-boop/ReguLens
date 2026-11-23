"""Create storage_cleanup_tasks table for durable storage cleanup outbox and reconciliation.

In accordance with Package C: Secure Document Storage & Upload Pipeline:
- Durable, retryable outbox table for failed post-commit storage deletions.
- Solves Scenario A (quarantine purge post-finalization) and Scenario B (storage purge post-deletion).
- Fully protected by PostgreSQL 16 Row Level Security (RLS) with FORCE RLS.
- Tenant isolation policy enforces NULLIF(current_setting('app.current_tenant_id', true), '')::uuid.
- Granted to unprivileged runtime role regulens_app with NOBYPASSRLS.
- Fully reversible upgrade and downgrade.

Revision ID: 0005_storage_cleanup_outbox
Revises: 0004_document_storage_fields
Create Date: 2026-11-23 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_storage_cleanup_outbox"
down_revision: Union[str, None] = "0004_document_storage_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create storage_cleanup_tasks table
    op.create_table(
        "storage_cleanup_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("cleanup_reason", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("tenant_id", "id", name="uq_storage_cleanup_tasks_tenant_id"),
    )

    # 2. Create indexes for reconciliation queries
    op.create_index("idx_storage_cleanup_due", "storage_cleanup_tasks", ["status", "next_retry_at"])
    op.create_index("idx_storage_cleanup_tenant", "storage_cleanup_tasks", ["tenant_id", "status"])

    # 3. Enable and enforce Row Level Security
    op.execute("ALTER TABLE storage_cleanup_tasks ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE storage_cleanup_tasks FORCE ROW LEVEL SECURITY;")

    # 4. Create Tenant Isolation RLS Policy
    op.execute("""
        CREATE POLICY storage_cleanup_tasks_tenant_isolation_policy ON storage_cleanup_tasks
        FOR ALL
        TO regulens_app
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    # 5. Grant required DML permissions to unprivileged runtime role regulens_app
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE storage_cleanup_tasks TO regulens_app;")


def downgrade() -> None:
    # 1. Remove FORCE ROW LEVEL SECURITY for safe teardown
    op.execute("ALTER TABLE storage_cleanup_tasks NO FORCE ROW LEVEL SECURITY;")

    # 2. Drop indexes
    op.drop_index("idx_storage_cleanup_tenant", table_name="storage_cleanup_tasks")
    op.drop_index("idx_storage_cleanup_due", table_name="storage_cleanup_tasks")

    # 3. Drop table with cascade
    op.drop_table("storage_cleanup_tasks")
