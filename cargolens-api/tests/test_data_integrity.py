"""
Tests for CargoLens AI - Critical Data Integrity Verification & Hardening.

Covers:
1. SHP-24811 sample data integrity:
   - No fabricated HSN (94054090) in source PDF or extraction evidence.
   - Grand total is unextracted/None (USD 16,320 is purely derived line arithmetic).
   - Line arithmetic 2,400 x 6.80 = 16,320.00 preserved.
   - Exact 45.00 kg gross weight discrepancy (3,120 kg vs 3,165 kg) triggers validation failure.
2. SHP-24812 sample data integrity:
   - Grand total is None (unstated on physical invoice).
   - Line total EUR 7,650 is purely derived from 180 x 42.50.
   - InvoiceArithmeticRule protects derived arithmetic from being treated as a confirmed invoice total.
3. Provider provenance:
   - Seed extractions use provider='synthetic-seed' and model='seed-fixture-v1'.
   - Zero hardcoded seed records masquerade as 'anthropic' or 'claude-sonnet-5-5'.
   - Fixture provider identifies explicitly as 'development-fixture' / 'fixture-v1'.
4. Scenario A clean triad workflow:
   - All 11 validation rules evaluate to PASS (11/11).
   - Goods description on BL aligns with CI line item.
   - Quantity on PL matches CI line item.
   - Human approval gate strictly preserved: shipment halts at REVIEW_REQUIRED with 0 reviews.
"""
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.cli.seed_demo import run_seed
from app.models.document import Document, DocumentType
from app.models.shipment import Shipment, ShipmentStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.user import User, UserRole
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.services.ai.fixture_provider import DeterministicFixtureExtractionProvider
from app.services.simulation.engine import SimulationEngine
from app.storage import get_storage_service
from app.security import hash_password


@pytest.fixture
async def sim_users(db_session):
    exec_user = User(
        email="integrity_exec@cargolens.in",
        full_name="Integrity Executive",
        hashed_password=hash_password("IntegrityPass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr_user = User(
        email="integrity_mgr@cargolens.in",
        full_name="Integrity Manager",
        hashed_password=hash_password("IntegrityPass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add(exec_user)
    db_session.add(mgr_user)
    await db_session.commit()
    await db_session.refresh(exec_user)
    await db_session.refresh(mgr_user)
    return exec_user, mgr_user


@pytest.mark.asyncio
async def test_shp_24811_sample_data_integrity(db_session):
    """
    SHP-24811 Data Integrity Verification:
    - No fabricated HSN 94054090 in PDF text or extracted structured fields.
    - grand_total is None (unstated in source document).
    - Line item arithmetic (2,400 x 6.80 = 16,320.00) preserved as derived line_total.
    - Gross weight discrepancy of exactly 45.00 kg (3,120 vs 3,165 kg) triggers FAIL.
    """
    await run_seed(force=True)

    # 1. Inspect shipment record
    shipment_res = await db_session.execute(
        select(Shipment).where(Shipment.shipment_number == "SHP-24811")
    )
    shipment = shipment_res.scalar_one_or_none()
    assert shipment is not None
    assert shipment.status == ShipmentStatus.REVIEW_REQUIRED
    assert shipment.quantity == Decimal("2400.00")
    assert shipment.unit_price == Decimal("6.8000")
    assert shipment.gross_weight_kg == Decimal("3120.000")

    # 2. Inspect Commercial Invoice document & PDF bytes
    docs_res = await db_session.execute(
        select(Document).where(
            Document.shipment_id == shipment.id,
            Document.document_type == DocumentType.COMMERCIAL_INVOICE,
        )
    )
    ci_doc = docs_res.scalar_one_or_none()
    assert ci_doc is not None

    storage = get_storage_service()
    chunks = []
    async for chunk in storage.get_file_stream(ci_doc.storage_key):
        chunks.append(chunk)
    pdf_bytes = b"".join(chunks)

    # Verify HSN 94054090 is NOT in source document
    import pymupdf
    pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pdf_text = pdf_doc[0].get_text()
    pdf_doc.close()
    assert "94054090" not in pdf_text
    assert "Grand Total:" not in pdf_text
    assert "Subtotal: USD 16,320.00" in pdf_text

    # 3. Inspect Structured Extraction
    ext_res = await db_session.execute(
        select(StructuredExtraction).where(StructuredExtraction.document_id == ci_doc.id)
    )
    ci_ext = ext_res.scalar_one_or_none()
    assert ci_ext is not None

    extracted_data = ci_ext.extracted_data
    # Grand total must NOT be stored as an extracted or confirmed value
    assert extracted_data["grand_total"]["value"] is None
    assert extracted_data["grand_total"]["evidence_text"] is None

    # Line item must contain derived arithmetic, but no HSN
    line_items = extracted_data.get("line_items", [])
    assert len(line_items) == 1
    line1 = line_items[0]
    assert "94054090" not in (line1["description"]["value"] or "")
    assert line1["quantity"]["value"] == "2400" or line1["quantity"]["value"] == 2400
    assert line1["unit_price"]["value"] == "6.80" or line1["unit_price"]["value"] == 6.8
    assert line1["line_total"]["value"] == "16320.00" or line1["line_total"]["value"] == 16320

    # 4. Verify 45 kg Gross Weight discrepancy rule outcome
    val_res = await db_session.execute(
        select(ShipmentValidationResult).where(
            ShipmentValidationResult.shipment_id == shipment.id,
            ShipmentValidationResult.rule_id == "RULE_GROSS_WEIGHT_CONSISTENCY",
        )
    )
    gw_result = val_res.scalars().first()
    assert gw_result is not None
    assert gw_result.outcome == ValidationOutcome.FAIL
    assert "45.00 kg" in gw_result.explanation


@pytest.mark.asyncio
async def test_shp_24812_sample_data_integrity(db_session):
    """
    SHP-24812 Data Integrity Verification:
    - grand_total is None (unstated in source document).
    - EUR 7,650 is preserved purely as line-item arithmetic (180 x EUR 42.50).
    - InvoiceArithmeticRule protects derived arithmetic from being treated as confirmed invoice total.
    """
    await run_seed(force=True)

    shipment_res = await db_session.execute(
        select(Shipment).where(Shipment.shipment_number == "SHP-24812")
    )
    shipment = shipment_res.scalar_one_or_none()
    assert shipment is not None

    docs_res = await db_session.execute(
        select(Document).where(
            Document.shipment_id == shipment.id,
            Document.document_type == DocumentType.COMMERCIAL_INVOICE,
        )
    )
    ci_doc = docs_res.scalar_one_or_none()
    assert ci_doc is not None

    ext_res = await db_session.execute(
        select(StructuredExtraction).where(StructuredExtraction.document_id == ci_doc.id)
    )
    ci_ext = ext_res.scalar_one_or_none()
    assert ci_ext is not None

    extracted_data = ci_ext.extracted_data
    assert extracted_data["grand_total"]["value"] is None

    line_items = extracted_data.get("line_items", [])
    assert len(line_items) == 1
    assert line_items[0]["line_total"]["value"] == "7650.00" or line_items[0]["line_total"]["value"] == 7650

    val_res = await db_session.execute(
        select(ShipmentValidationResult).where(
            ShipmentValidationResult.shipment_id == shipment.id,
            ShipmentValidationResult.rule_id == "RULE_INVOICE_ARITHMETIC",
        )
    )
    arith_result = val_res.scalars().first()
    assert arith_result is not None
    assert arith_result.outcome == ValidationOutcome.MISSING_DATA
    assert "cannot be treated as a confirmed or extracted invoice total" in arith_result.explanation


@pytest.mark.asyncio
async def test_provider_provenance_integrity(db_session):
    """
    Provider Provenance Verification:
    - All synthetic seed extractions identify as provider='synthetic-seed', model='seed-fixture-v1'.
    - Zero seed extractions masquerade as 'anthropic' or 'claude-sonnet-5-5'.
    - DeterministicFixtureExtractionProvider identifies as 'development-fixture' / 'fixture-v1'.
    """
    await run_seed(force=True)

    all_seed_exts = (await db_session.execute(select(StructuredExtraction))).scalars().all()
    assert len(all_seed_exts) > 0

    for ext in all_seed_exts:
        assert ext.provider != "anthropic", f"Seed extraction {ext.id} masquerades as anthropic"
        assert ext.model != "claude-sonnet-5-5", f"Seed extraction {ext.id} masquerades as claude-sonnet-5-5"
        assert ext.provider in ("synthetic-seed", "development-fixture")
        assert ext.model in ("seed-fixture-v1", "fixture-v1")

    # Fixture provider properties
    provider = DeterministicFixtureExtractionProvider()
    assert provider.provider_name == "development-fixture"
    assert provider.model_name == "fixture-v1"


@pytest.mark.asyncio
async def test_scenario_a_all_11_rules_pass_and_human_gate_preserved(db_session, sim_users):
    """
    Scenario A Verification:
    - All 11 cross-document validation rules evaluate to PASS (11/11).
    - Status strictly remains REVIEW_REQUIRED (no auto-confirmations).
    - Human reviews count is exactly 0.
    - Verification and export remain gated.
    """
    exec_user, mgr_user = sim_users
    res = await SimulationEngine.simulate_scenario(
        session=db_session,
        scenario_code="COMPLETE_WORKFLOW",
        creator_user=exec_user,
        manager_user=mgr_user,
        provider_type="fixture",
    )

    assert res["scenario_type"] == "COMPLETE_WORKFLOW"
    assert res["shipment_number"] == "SHP-DEMO-001"
    assert res["status"] == "REVIEW_REQUIRED"
    assert len(res["documents"]) == 3

    # All 11 rules pass!
    val = res["validation"]
    assert val["total_rules"] == 11
    assert val["passed_count"] == 11
    assert val["failed_count"] == 0
    assert val["missing_data_count"] == 0
    assert val["has_blocking_failures"] is False

    # Human gate preserved
    assert res["human_reviews_count"] == 0
    assert res["verification_ready"] is False
    assert res["export"] is None
