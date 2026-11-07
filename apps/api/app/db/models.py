"""SQLAlchemy 2.0 relational models for ReguLens Multi-Sector SaaS.

Enforces:
1. Multi-sector product and regulatory representations (Sector 1: Agri-food, Sector 2: Textiles/Apparel).
2. Direct tenant ownership (`tenant_id`) on all customer tables.
3. Composite uniqueness `UNIQUE (tenant_id, id)` on all tenant-owned tables.
4. Composite foreign-key constraints `(tenant_id, parent_id) REFERENCES parent(tenant_id, id)`.
5. Global reference tables for public regulatory acts and citations (no tenant_id).
"""
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    Numeric,
    BigInteger,
    Integer,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


# ==============================================================================
# 1. GLOBAL REGULATORY REFERENCE TABLES (Public Data, Zero Customer Data)
# ==============================================================================

class RegulatoryAct(Base):
    __tablename__ = "regulatory_acts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    official_identifier: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    celex_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    short_title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(64), nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, default="CROSS_SECTOR")
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    in_force_date: Mapped[date] = mapped_column(Date, nullable=False)
    application_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    repeal_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_FORCE")
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    requirements: Mapped[List["RegulatoryRequirement"]] = relationship("RegulatoryRequirement", back_populates="act")
    citations: Mapped[List["Citation"]] = relationship("Citation", back_populates="act")

    __table_args__ = (
        Index("idx_regulatory_acts_celex", "celex_number"),
        Index("idx_regulatory_acts_lifecycle", "lifecycle_state"),
        Index("idx_regulatory_acts_sector", "sector"),
    )


class RegulatoryRequirement(Base):
    __tablename__ = "regulatory_requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    act_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regulatory_acts.id", ondelete="RESTRICT"), nullable=False)
    requirement_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    legal_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    verbatim_text: Mapped[str] = mapped_column(Text, nullable=False)
    arabic_translation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_frequency_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    documentary_check_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    required_document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="REQUIRES_HUMAN_VERIFICATION")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    act: Mapped["RegulatoryAct"] = relationship("RegulatoryAct", back_populates="requirements")
    citations: Mapped[List["Citation"]] = relationship("Citation", back_populates="requirement")
    applicability_rules: Mapped[List["ApplicabilityRule"]] = relationship("ApplicabilityRule", back_populates="requirement")

    __table_args__ = (
        Index("idx_reqs_sector_category", "sector", "category"),
        Index("idx_reqs_act_id", "act_id"),
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regulatory_requirements.id", ondelete="CASCADE"), nullable=False)
    act_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regulatory_acts.id", ondelete="RESTRICT"), nullable=False)
    official_source_title: Mapped[str] = mapped_column(Text, nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    quoted_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    text_anchor_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    requirement: Mapped["RegulatoryRequirement"] = relationship("RegulatoryRequirement", back_populates="citations")
    act: Mapped["RegulatoryAct"] = relationship("RegulatoryAct", back_populates="citations")

    __table_args__ = (
        Index("idx_citations_requirement", "requirement_id"),
    )


class ApplicabilityRule(Base):
    __tablename__ = "applicability_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regulatory_requirements.id", ondelete="CASCADE"), nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False)
    hs_code_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    origin_country: Mapped[str] = mapped_column(String(2), nullable=False)
    destination_market: Mapped[str] = mapped_column(String(8), nullable=False)
    condition_expression: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expert_reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    requirement: Mapped["RegulatoryRequirement"] = relationship("RegulatoryRequirement", back_populates="applicability_rules")

    __table_args__ = (
        Index("idx_rules_lookup", "sector", "hs_code_prefix", "origin_country", "destination_market"),
    )


# ==============================================================================
# 2. TENANT-OWNED TABLES (Enforced RLS & Composite Foreign Keys)
# ==============================================================================

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    commercial_registry_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="EG")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users: Mapped[List["TenantUser"]] = relationship("TenantUser", back_populates="tenant")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    professional_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant_memberships: Mapped[List["TenantUser"]] = relationship("TenantUser", back_populates="user")


class TenantUser(Base):
    __tablename__ = "tenant_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    user: Mapped["User"] = relationship("User", back_populates="tenant_memberships")

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_user"),
        UniqueConstraint("tenant_id", "id", name="uq_tenant_users_tenant_id"),
        Index("idx_tenant_users_tenant", "tenant_id"),
        Index("idx_tenant_users_user", "user_id"),
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False)
    hs_code: Mapped[str] = mapped_column(String(16), nullable=False)
    origin_country: Mapped[str] = mapped_column(String(2), nullable=False, default="EG")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="products")
    consignments: Mapped[List["Consignment"]] = relationship("Consignment", back_populates="product")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_products_tenant_id"),
        Index("idx_products_tenant", "tenant_id"),
        Index("idx_products_sector", "tenant_id", "sector"),
        Index("idx_products_hs_code", "tenant_id", "hs_code"),
    )


class Consignment(Base):
    __tablename__ = "consignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    consignment_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    origin_country: Mapped[str] = mapped_column(String(2), nullable=False, default="EG")
    destination_market: Mapped[str] = mapped_column(String(8), nullable=False, default="EU")
    planned_shipping_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    discharge_port: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    total_quantity: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    quantity_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="KG")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship("Product", back_populates="consignments")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="consignment")
    gap_analyses: Mapped[List["GapAnalysis"]] = relationship("GapAnalysis", back_populates="consignment")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_consignments_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_consignments_product",
            ondelete="RESTRICT",
        ),
        Index("idx_consignments_tenant", "tenant_id"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    consignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    antivirus_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_SCANNED")
    parsing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consignment: Mapped["Consignment"] = relationship("Consignment", back_populates="documents")
    evidence_items: Mapped[List["EvidenceItem"]] = relationship("EvidenceItem", back_populates="document")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_documents_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "consignment_id"],
            ["consignments.tenant_id", "consignments.id"],
            name="fk_documents_consignment",
            ondelete="CASCADE",
        ),
        Index("idx_documents_tenant", "tenant_id"),
        Index("idx_documents_consignment", "tenant_id", "consignment_id"),
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_category: Mapped[str] = mapped_column(String(64), nullable=False)
    field_or_substance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    numeric_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    text_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quoted_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="EXTRACTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="evidence_items")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_evidence_items_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["documents.tenant_id", "documents.id"],
            name="fk_evidence_document",
            ondelete="CASCADE",
        ),
        Index("idx_evidence_tenant", "tenant_id"),
        Index("idx_evidence_document", "tenant_id", "document_id"),
    )


class GapAnalysis(Base):
    __tablename__ = "gap_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    consignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consignment: Mapped["Consignment"] = relationship("Consignment", back_populates="gap_analyses")
    items: Mapped[List["GapAnalysisItem"]] = relationship("GapAnalysisItem", back_populates="gap_analysis")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_gap_analyses_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "consignment_id"],
            ["consignments.tenant_id", "consignments.id"],
            name="fk_gap_analyses_consignment",
            ondelete="CASCADE",
        ),
        Index("idx_gap_analyses_tenant", "tenant_id"),
    )


class GapAnalysisItem(Base):
    __tablename__ = "gap_analysis_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    gap_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regulatory_requirements.id", ondelete="RESTRICT"), nullable=False)
    matched_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    evidence_status: Mapped[str] = mapped_column(String(64), nullable=False, default="NEEDS_REVIEW")
    findings_description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gap_analysis: Mapped["GapAnalysis"] = relationship("GapAnalysis", back_populates="items")
    human_reviews: Mapped[List["HumanReview"]] = relationship("HumanReview", back_populates="gap_analysis_item")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_gap_analysis_items_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "gap_analysis_id"],
            ["gap_analyses.tenant_id", "gap_analyses.id"],
            name="fk_gap_items_analysis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "matched_document_id"],
            ["documents.tenant_id", "documents.id"],
            name="fk_gap_items_document",
            ondelete="SET NULL",
        ),
        Index("idx_gap_items_tenant", "tenant_id"),
        Index("idx_gap_items_analysis", "tenant_id", "gap_analysis_id"),
    )


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    gap_analysis_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewer_credentials: Mapped[str] = mapped_column(String(255), nullable=False)
    verdict: Mapped[str] = mapped_column(String(64), nullable=False)
    human_notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gap_analysis_item: Mapped["GapAnalysisItem"] = relationship("GapAnalysisItem", back_populates="human_reviews")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_human_reviews_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "gap_analysis_item_id"],
            ["gap_analysis_items.tenant_id", "gap_analysis_items.id"],
            name="fk_human_reviews_item",
            ondelete="CASCADE",
        ),
        Index("idx_human_reviews_tenant", "tenant_id"),
        Index("idx_human_reviews_item", "tenant_id", "gap_analysis_item_id"),
    )


class ExportReport(Base):
    __tablename__ = "export_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    consignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    mandatory_disclaimer_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    generated_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_export_reports_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "consignment_id"],
            ["consignments.tenant_id", "consignments.id"],
            name="fk_export_reports_consignment",
            ondelete="RESTRICT",
        ),
        Index("idx_reports_tenant", "tenant_id"),
    )


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_background_jobs_tenant_id"),
        Index("idx_jobs_poll", "status", "run_at"),
        Index("idx_jobs_tenant", "tenant_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_audit_logs_tenant_id"),
        Index("idx_audit_tenant_created", "tenant_id", "created_at"),
    )
