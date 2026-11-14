"""Harden all 13 PostgreSQL Row Level Security policies with NULLIF against empty-string GUC reset.

In accordance with AGENTS.md Rule 7, QUALITY_GATES.md, and Phase 1 Package A:
- Replaces raw casting `current_setting('app.current_tenant_id', true)::uuid` with
  `NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`.
- Hardens all 13 policies across all 12 tables:
  1. rls_tenants on tenants (FOR SELECT)
  2. rls_tenant_users on tenant_users (FOR ALL)
  3. rls_products on products (FOR ALL)
  4. rls_consignments on consignments (FOR ALL)
  5. rls_documents on documents (FOR ALL)
  6. rls_evidence_items on evidence_items (FOR ALL)
  7. rls_gap_analyses on gap_analyses (FOR ALL)
  8. rls_gap_analysis_items on gap_analysis_items (FOR ALL)
  9. rls_human_reviews on human_reviews (FOR ALL)
  10. rls_export_reports on export_reports (FOR ALL)
  11. rls_background_jobs on background_jobs (FOR ALL)
  12. rls_audit_logs_select on audit_logs (FOR SELECT)
  13. rls_audit_logs_insert on audit_logs (FOR INSERT)
- Fully idempotent and reversible with full downgrade support.

Revision ID: 0002_harden_rls_policies
Revises: 0001_initial_schema
Create Date: 2026-11-14 02:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002_harden_rls_policies"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STANDARD_TENANT_TABLES = [
    "tenant_users",
    "products",
    "consignments",
    "documents",
    "evidence_items",
    "gap_analyses",
    "gap_analysis_items",
    "human_reviews",
    "export_reports",
    "background_jobs",
]


def upgrade() -> None:
    # 1. Update tenants table policy (SELECT based on id)
    op.execute("DROP POLICY IF EXISTS rls_tenants ON tenants;")
    op.execute("""
        CREATE POLICY rls_tenants ON tenants
            FOR SELECT
            USING (id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    # 2. Update 10 standard tenant tables policies (FOR ALL)
    for table in STANDARD_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS rls_{table} ON {table};")
        op.execute(f"""
            CREATE POLICY rls_{table} ON {table}
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """)

    # 3. Update audit_logs policies (SELECT and INSERT)
    op.execute("DROP POLICY IF EXISTS rls_audit_logs_select ON audit_logs;")
    op.execute("""
        CREATE POLICY rls_audit_logs_select ON audit_logs
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("DROP POLICY IF EXISTS rls_audit_logs_insert ON audit_logs;")
    op.execute("""
        CREATE POLICY rls_audit_logs_insert ON audit_logs
            FOR INSERT
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)


def downgrade() -> None:
    # Revert to Migration 0001 definitions
    op.execute("DROP POLICY IF EXISTS rls_tenants ON tenants;")
    op.execute("""
        CREATE POLICY rls_tenants ON tenants
            FOR SELECT
            USING (id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    for table in STANDARD_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS rls_{table} ON {table};")
        op.execute(f"""
            CREATE POLICY rls_{table} ON {table}
                FOR ALL
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
        """)

    op.execute("DROP POLICY IF EXISTS rls_audit_logs_select ON audit_logs;")
    op.execute("""
        CREATE POLICY rls_audit_logs_select ON audit_logs
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    op.execute("DROP POLICY IF EXISTS rls_audit_logs_insert ON audit_logs;")
    op.execute("""
        CREATE POLICY rls_audit_logs_insert ON audit_logs
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)
