"""Initial schema creation with multi-sector models, composite foreign keys, and RLS policies.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-07 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Global Regulatory Reference Tables
    op.create_table(
        "regulatory_acts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("official_identifier", sa.String(128), unique=True, nullable=False),
        sa.Column("celex_number", sa.String(64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("short_title", sa.String(255), nullable=False),
        sa.Column("issuing_authority", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(64), nullable=False),
        sa.Column("sector", sa.String(64), nullable=False, server_default="CROSS_SECTOR"),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("in_force_date", sa.Date(), nullable=False),
        sa.Column("application_date", sa.Date(), nullable=True),
        sa.Column("repeal_date", sa.Date(), nullable=True),
        sa.Column("lifecycle_state", sa.String(32), nullable=False, server_default="IN_FORCE"),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_regulatory_acts_celex", "regulatory_acts", ["celex_number"])
    op.create_index("idx_regulatory_acts_lifecycle", "regulatory_acts", ["lifecycle_state"])
    op.create_index("idx_regulatory_acts_sector", "regulatory_acts", ["sector"])

    op.create_table(
        "regulatory_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("act_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulatory_acts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requirement_code", sa.String(64), unique=True, nullable=False),
        sa.Column("sector", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("legal_reference", sa.String(255), nullable=False),
        sa.Column("verbatim_text", sa.Text(), nullable=False),
        sa.Column("arabic_translation", sa.Text(), nullable=True),
        sa.Column("check_frequency_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("documentary_check_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("required_document_type", sa.String(64), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="REQUIRES_HUMAN_VERIFICATION"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_reqs_sector_category", "regulatory_requirements", ["sector", "category"])
    op.create_index("idx_reqs_act_id", "regulatory_requirements", ["act_id"])

    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulatory_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("act_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulatory_acts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("official_source_title", sa.Text(), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("quoted_excerpt", sa.Text(), nullable=False),
        sa.Column("text_anchor_offset", sa.Integer(), nullable=True),
        sa.Column("source_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_citations_requirement", "citations", ["requirement_id"])

    op.create_table(
        "applicability_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulatory_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sector", sa.String(64), nullable=False),
        sa.Column("hs_code_prefix", sa.String(16), nullable=False),
        sa.Column("origin_country", sa.String(2), nullable=False),
        sa.Column("destination_market", sa.String(8), nullable=False),
        sa.Column("condition_expression", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expert_reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rules_lookup", "applicability_rules", ["sector", "hs_code_prefix", "origin_country", "destination_market"])

    # 2. Tenants & Users
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("commercial_registry_number", sa.String(64), nullable=True),
        sa.Column("tax_id", sa.String(64), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="EG"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("professional_title", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tenant_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_user"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tenant_users_tenant_id"),
    )
    op.create_index("idx_tenant_users_tenant", "tenant_users", ["tenant_id"])
    op.create_index("idx_tenant_users_user", "tenant_users", ["user_id"])

    # 3. Multi-Sector Products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(64), nullable=False),
        sa.Column("hs_code", sa.String(16), nullable=False),
        sa.Column("origin_country", sa.String(2), nullable=False, server_default="EG"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_products_tenant_id"),
    )
    op.create_index("idx_products_tenant", "products", ["tenant_id"])
    op.create_index("idx_products_sector", "products", ["tenant_id", "sector"])
    op.create_index("idx_products_hs_code", "products", ["tenant_id", "hs_code"])

    # 4. Consignments (Composite FK to products)
    op.create_table(
        "consignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consignment_reference", sa.String(128), nullable=False),
        sa.Column("origin_country", sa.String(2), nullable=False, server_default="EG"),
        sa.Column("destination_market", sa.String(8), nullable=False, server_default="EU"),
        sa.Column("planned_shipping_date", sa.Date(), nullable=True),
        sa.Column("discharge_port", sa.String(128), nullable=True),
        sa.Column("total_quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("quantity_unit", sa.String(32), nullable=False, server_default="KG"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consignments_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_consignments_product",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("idx_consignments_tenant", "consignments", ["tenant_id"])

    # 5. Documents (Composite FK to consignments)
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("antivirus_status", sa.String(32), nullable=False, server_default="NOT_SCANNED"),
        sa.Column("parsing_status", sa.String(32), nullable=False, server_default="UPLOADED"),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_documents_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consignment_id"],
            ["consignments.tenant_id", "consignments.id"],
            name="fk_documents_consignment",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_documents_tenant", "documents", ["tenant_id"])
    op.create_index("idx_documents_consignment", "documents", ["tenant_id", "consignment_id"])

    # 6. Evidence Items (Composite FK to documents)
    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_category", sa.String(64), nullable=False),
        sa.Column("field_or_substance_name", sa.String(255), nullable=False),
        sa.Column("numeric_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("text_value", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quoted_excerpt", sa.Text(), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="EXTRACTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_evidence_items_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["documents.tenant_id", "documents.id"],
            name="fk_evidence_document",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_evidence_tenant", "evidence_items", ["tenant_id"])
    op.create_index("idx_evidence_document", "evidence_items", ["tenant_id", "document_id"])

    # 7. Gap Analyses & Items (Composite FKs)
    op.create_table(
        "gap_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_status", sa.String(64), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_gap_analyses_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consignment_id"],
            ["consignments.tenant_id", "consignments.id"],
            name="fk_gap_analyses_consignment",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_gap_analyses_tenant", "gap_analyses", ["tenant_id"])

    op.create_table(
        "gap_analysis_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gap_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulatory_requirements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("matched_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_status", sa.String(64), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("findings_description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_gap_analysis_items_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "gap_analysis_id"],
            ["gap_analyses.tenant_id", "gap_analyses.id"],
            name="fk_gap_items_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "matched_document_id"],
            ["documents.tenant_id", "documents.id"],
            name="fk_gap_items_document",
            ondelete="SET NULL",
        ),
    )
    op.create_index("idx_gap_items_tenant", "gap_analysis_items", ["tenant_id"])
    op.create_index("idx_gap_items_analysis", "gap_analysis_items", ["tenant_id", "gap_analysis_id"])

    # 8. Human Reviews (Composite FK to gap_analysis_items)
    op.create_table(
        "human_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gap_analysis_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewer_credentials", sa.String(255), nullable=False),
        sa.Column("verdict", sa.String(64), nullable=False),
        sa.Column("human_notes", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_human_reviews_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "gap_analysis_item_id"],
            ["gap_analysis_items.tenant_id", "gap_analysis_items.id"],
            name="fk_human_reviews_item",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_human_reviews_tenant", "human_reviews", ["tenant_id"])
    op.create_index("idx_human_reviews_item", "human_reviews", ["tenant_id", "gap_analysis_item_id"])

    # 9. Export Reports (Composite FK to consignments)
    op.create_table(
        "export_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("mandatory_disclaimer_included", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_export_reports_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consignment_id"],
            ["consignments.tenant_id", "consignments.id"],
            name="fk_export_reports_consignment",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("idx_reports_tenant", "export_reports", ["tenant_id"])

    # 10. Background Jobs
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_background_jobs_tenant_id"),
    )
    op.create_index("idx_jobs_poll", "background_jobs", ["status", "run_at"])
    op.create_index("idx_jobs_tenant", "background_jobs", ["tenant_id"])

    # 11. Audit Logs (Immutable)
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_audit_logs_tenant_id"),
    )
    op.create_index("idx_audit_tenant_created", "audit_logs", ["tenant_id", "created_at"])

    # 12. ROW LEVEL SECURITY (RLS) POLICIES
    tables_with_rls = [
        "tenant_users", "products", "consignments", "documents", 
        "evidence_items", "gap_analyses", "gap_analysis_items", 
        "human_reviews", "export_reports", "background_jobs"
    ]

    # tenants table RLS (SELECT based on id)
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_tenants ON tenants
            FOR SELECT
            USING (id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    # 10 standard tenant tables RLS
    for table in tables_with_rls:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY rls_{table} ON {table}
                FOR ALL
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
        """)

    # audit_logs table RLS (Append-only: SELECT and INSERT only)
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_audit_logs_select ON audit_logs
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY rls_audit_logs_insert ON audit_logs
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)

    # 13. Audit Log Privilege Hardening (SQL Engine Permission Layer)
    # Explicitly revoke UPDATE, DELETE, and TRUNCATE from the runtime application role (regulens_app).
    # This overrides ALTER DEFAULT PRIVILEGES, ensuring audit_logs is append-only at both
    # the SQL privilege layer and the RLS policy layer.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'regulens_app') THEN
                REVOKE UPDATE, DELETE, TRUNCATE ON TABLE public.audit_logs FROM regulens_app;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Drop all in reverse order
    tables = [
        "audit_logs", "background_jobs", "export_reports", "human_reviews",
        "gap_analysis_items", "gap_analyses", "evidence_items", "documents",
        "consignments", "products", "tenant_users", "users", "tenants",
        "applicability_rules", "citations", "regulatory_requirements", "regulatory_acts"
    ]
    for table in tables:
        op.drop_table(table)
