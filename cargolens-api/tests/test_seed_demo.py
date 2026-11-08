import pytest
from sqlalchemy import select

from app.cli.seed_demo import run_seed
from app.models.shipment import Shipment, ShipmentStatus
from app.models.user import User, UserRole
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.models.export import ShipmentExportRecord
from app.api.v1.workflow import evaluate_readiness
from app.services.export.csv_exporter import CSVExportService


@pytest.mark.asyncio
async def test_seed_demo_idempotency_and_data_integrity(db_session):
    """
    Verifies that run_seed():
    1. Executes cleanly and idempotently.
    2. Populates demo users (executive@cargolens.in and manager@cargolens.in).
    3. Populates SHP-24811 demonstrating the exact 45.00 kg Gross Weight discrepancy.
    4. Populates SHP-24812 demonstrating InvoiceArithmeticRule protection on unstated total.
    5. Populates SHP-24816 in VERIFIED status.
    6. Populates SHP-24817 in non-exported status with DEMO_SEED reviews; proves DEMO_SEED
       reviews cannot satisfy human approval gates, and no automatic export is fabricated.
    7. Runs idempotently without duplicate records or errors on repeated execution.
    """
    # 1. Run seed routine initial execution
    await run_seed(force=True)

    # Verify users
    exec_res = await db_session.execute(select(User).where(User.email == "executive@cargolens.in"))
    exec_user = exec_res.scalar_one_or_none()
    assert exec_user is not None
    assert exec_user.role == UserRole.DOCUMENTATION_EXECUTIVE

    mgr_res = await db_session.execute(select(User).where(User.email == "manager@cargolens.in"))
    mgr_user = mgr_res.scalar_one_or_none()
    assert mgr_user is not None
    assert mgr_user.role == UserRole.DOCUMENTATION_MANAGER

    # 2. Verify SHP-24811 (45 kg Gross Weight Discrepancy)
    s24811_res = await db_session.execute(
        select(Shipment).where(Shipment.shipment_number == "SHP-24811")
    )
    s24811 = s24811_res.scalar_one_or_none()
    assert s24811 is not None
    assert s24811.status == ShipmentStatus.REVIEW_REQUIRED

    val_res = await db_session.execute(
        select(ShipmentValidationResult).where(
            ShipmentValidationResult.shipment_id == s24811.id,
            ShipmentValidationResult.rule_id == "RULE_GROSS_WEIGHT_CONSISTENCY",
        )
    )
    gw_rule = val_res.scalars().first()
    assert gw_rule is not None
    assert gw_rule.outcome == ValidationOutcome.FAIL
    assert "45.00 kg" in gw_rule.explanation

    # 3. Verify SHP-24812 (Unstated Grand Total Arithmetic Protection)
    s24812_res = await db_session.execute(
        select(Shipment).where(Shipment.shipment_number == "SHP-24812")
    )
    s24812 = s24812_res.scalar_one_or_none()
    assert s24812 is not None

    arith_res = await db_session.execute(
        select(ShipmentValidationResult).where(
            ShipmentValidationResult.shipment_id == s24812.id,
            ShipmentValidationResult.rule_id == "RULE_INVOICE_ARITHMETIC",
        )
    )
    arith_rule = arith_res.scalars().first()
    assert arith_rule is not None
    assert arith_rule.outcome == ValidationOutcome.MISSING_DATA
    assert "cannot be treated as a confirmed or extracted invoice total" in arith_rule.explanation

    # 4. Verify SHP-24816 (VERIFIED)
    s24816_res = await db_session.execute(
        select(Shipment).where(Shipment.shipment_number == "SHP-24816")
    )
    s24816 = s24816_res.scalar_one_or_none()
    assert s24816 is not None
    assert s24816.status == ShipmentStatus.VERIFIED

    # 5. Verify SHP-24817 (Non-exported status; DEMO_SEED reviews present; no automatic export)
    s24817_res = await db_session.execute(
        select(Shipment).where(Shipment.shipment_number == "SHP-24817")
    )
    s24817 = s24817_res.scalar_one_or_none()
    assert s24817 is not None
    assert s24817.status != ShipmentStatus.EXPORTED
    assert s24817.status == ShipmentStatus.REVIEW_REQUIRED

    # Confirm no automatic export record was fabricated
    exp_res = await db_session.execute(
        select(ShipmentExportRecord).where(ShipmentExportRecord.shipment_id == s24817.id)
    )
    exp_records = exp_res.scalars().all()
    assert len(exp_records) == 0

    # 6. Prove DEMO_SEED reviews cannot satisfy human approval gates
    v_readiness = await evaluate_readiness(s24817, db_session)
    assert v_readiness.is_ready is False
    assert v_readiness.all_mandatory_fields_reviewed is False
    assert v_readiness.human_reviews_count == 0
    assert any("DEMO_SEED" in req for req in v_readiness.missing_requirements)

    is_exp_ready, exp_reqs = await CSVExportService.evaluate_export_readiness(db_session, s24817)
    assert is_exp_ready is False
    assert any("DEMO_SEED" in req or "status" in req.lower() for req in exp_reqs)

    # 7. Verify Idempotency of run_seed() on repeated execution
    await run_seed(force=True)

    all_users = (await db_session.execute(select(User))).scalars().all()
    assert len(all_users) == 2  # No duplicate demo accounts

    all_shipments = (await db_session.execute(select(Shipment))).scalars().all()
    assert len(all_shipments) == 8  # 8 demo shipments

    all_exports = (await db_session.execute(select(ShipmentExportRecord))).scalars().all()
    assert len(all_exports) == 0  # Still zero fabricated exports
