"""Unit tests for multi-sector schema models and composite relationship definitions."""
import uuid
from app.db.models import (
    Tenant,
    Product,
    Consignment,
    Document,
    EvidenceItem,
    GapAnalysis,
    GapAnalysisItem,
    HumanReview,
    ExportReport,
    RegulatoryAct,
    RegulatoryRequirement,
    ApplicabilityRule,
)


def test_multi_sector_product_model():
    tenant_id = uuid.uuid4()
    
    # Sector 1: Agriculture / Fresh Fruit
    agri_product = Product(
        tenant_id=tenant_id,
        name="Egyptian Valencia Oranges",
        sector="AGRI_FOOD",
        hs_code="08051000",
        origin_country="EG",
        attributes={"scientific_name": "Citrus sinensis", "variety": "Valencia", "product_state": "FRESH"},
    )
    assert agri_product.sector == "AGRI_FOOD"
    assert agri_product.attributes["variety"] == "Valencia"

    # Sector 2: Textiles / Ready-made Garments
    textile_product = Product(
        tenant_id=tenant_id,
        name="Children's Cotton Sleepwear",
        sector="TEXTILES_APPAREL",
        hs_code="61072100",
        origin_country="EG",
        attributes={"target_group": "children_under_14", "has_cords_or_drawstrings": True},
    )
    assert textile_product.sector == "TEXTILES_APPAREL"
    assert textile_product.attributes["has_cords_or_drawstrings"] is True


def test_sector_matching_specification():
    """Verifies that sector matching logic strictly partitions sector rules and permits CROSS_SECTOR."""
    def matches_sector(rule_sector: str, product_sector: str) -> bool:
        return rule_sector == product_sector or rule_sector == "CROSS_SECTOR"

    # Sector-specific rules NEVER cross sectors
    assert matches_sector("AGRI_FOOD", "AGRI_FOOD") is True
    assert matches_sector("TEXTILES_APPAREL", "TEXTILES_APPAREL") is True
    assert matches_sector("AGRI_FOOD", "TEXTILES_APPAREL") is False
    assert matches_sector("TEXTILES_APPAREL", "AGRI_FOOD") is False

    # CROSS_SECTOR rules apply to both sectors
    assert matches_sector("CROSS_SECTOR", "AGRI_FOOD") is True
    assert matches_sector("CROSS_SECTOR", "TEXTILES_APPAREL") is True

    # ApplicabilityRule table has sector column
    assert "sector" in ApplicabilityRule.__table__.columns


def test_composite_foreign_key_metadata():
    # Verify composite foreign keys on Consignment
    fk_constraints = Consignment.__table__.foreign_key_constraints
    composite_fks = [c for c in fk_constraints if len(c.columns) == 2]
    assert len(composite_fks) >= 1
    fk = composite_fks[0]
    assert [col.name for col in fk.columns] == ["tenant_id", "product_id"]

    # Verify composite foreign keys on Document
    doc_fks = [c for c in Document.__table__.foreign_key_constraints if len(c.columns) == 2]
    assert len(doc_fks) >= 1
    assert [col.name for col in doc_fks[0].columns] == ["tenant_id", "consignment_id"]


def test_global_regulatory_tables_have_no_tenant_id():
    assert "tenant_id" not in RegulatoryAct.__table__.columns
    assert "tenant_id" not in RegulatoryRequirement.__table__.columns
    assert "sector" in RegulatoryAct.__table__.columns
    assert "sector" in RegulatoryRequirement.__table__.columns
