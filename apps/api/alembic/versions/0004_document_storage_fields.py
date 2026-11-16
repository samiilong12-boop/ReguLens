"""Add document storage and upload validation fields to documents table.

In accordance with Package C: Secure Document Storage & Upload Pipeline:
- Makes consignment_id nullable to allow pre-consignment uploads.
- Makes sha256_hash nullable during PENDING_UPLOAD state before server verification.
- Adds status (default: 'PENDING_UPLOAD').
- Adds quarantine_key for pre-validation isolation.
- Adds uploaded_by_user_id (FK to users.id).
- Adds rejection_reason and validated_at.
- Adds index on (tenant_id, status).
- Provides complete, bidirectional upgrade and downgrade.

Revision ID: 0004_document_storage_fields
Revises: 0003_membership_rls_policies
Create Date: 2026-11-14 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_document_storage_fields"
down_revision: Union[str, None] = "0003_membership_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Relax NOT NULL constraints for upload lifecycle staging
    op.alter_column(
        "documents",
        "consignment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column(
        "documents",
        "sha256_hash",
        existing_type=sa.String(length=64),
        nullable=True,
    )

    # 2. Add Package C lifecycle and quarantine columns
    op.add_column(
        "documents",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING_UPLOAD"),
    )
    op.add_column(
        "documents",
        sa.Column("quarantine_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Create index for tenant status queries
    op.create_index("idx_documents_status", "documents", ["tenant_id", "status"])


def downgrade() -> None:
    # Pre-downgrade check: prevent silent data corruption or loss when records contain NULL values
    bind = op.get_bind()
    null_consignments = bind.execute(
        sa.text("SELECT count(*) FROM documents WHERE consignment_id IS NULL")
    ).scalar() or 0
    null_hashes = bind.execute(
        sa.text("SELECT count(*) FROM documents WHERE sha256_hash IS NULL")
    ).scalar() or 0

    if null_consignments > 0 or null_hashes > 0:
        raise RuntimeError(
            f"Cannot downgrade migration 0004_document_storage_fields to 0003_membership_rls_policies: "
            f"Table 'documents' contains {null_consignments} rows with NULL consignment_id and "
            f"{null_hashes} rows with NULL sha256_hash. "
            f"Restoring NOT NULL constraints would fail or violate data integrity. "
            f"Remediation: Associate unlinked documents with valid consignments and finalized SHA-256 hashes, "
            f"or delete invalid unfinalized uploads before re-attempting migration downgrade."
        )

    # 1. Drop index
    op.drop_index("idx_documents_status", table_name="documents")

    # 2. Drop Package C columns
    op.drop_column("documents", "validated_at")
    op.drop_column("documents", "rejection_reason")
    op.drop_column("documents", "uploaded_by_user_id")
    op.drop_column("documents", "quarantine_key")
    op.drop_column("documents", "status")

    # 3. Restore NOT NULL constraints
    op.alter_column(
        "documents",
        "sha256_hash",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "documents",
        "consignment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
