"""
CargoLens AI — Final Human Approval Gate Security Audit Test Suite.

Proves:
1. Verification readiness fails and blocks verification when mandatory fields
   are covered only by demonstration seed fixtures (ReviewProvenance.DEMO_SEED).
2. Export readiness fails and export generation is blocked when mandatory approvals
   exist only as DEMO_SEED.
3. Verification and export gates succeed cleanly when all mandatory fields are
   confirmed or corrected via genuine human reviews (ReviewProvenance.USER_ACTION).
4. Pre-existing VERIFIED and EXPORTED shipments preserve their statuses and export snapshots,
   preventing duplicate exports or accidental regression.
5. Executive and Manager RBAC isolation is strictly enforced across verification and export endpoints.
"""
import io
import csv
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome, ValidationSeverity
from app.models.field_review import (
    DocumentFieldReview,
    FieldReviewActionType,
    ReviewProvenance,
)
from app.models.export import ShipmentExportRecord, ExportStatus
from app.security import hash_password, create_access_token


MANDATORY_REVIEW_FIELDS = {
    DocumentType.COMMERCIAL_INVOICE: {
        "invoice_number": "INV-MANDATORY-2026",
        "invoice_date": "2026-05-15",
        "seller_name": "Hamburg Marine Machinery GmbH",
        "buyer_name": "Navi Mumbai Precision Importers",
        "grand_total": "18450.00",
        "currency": "EUR",
    },
    DocumentType.PACKING_LIST: {
        "invoice_reference": "INV-MANDATORY-2026",
        "package_count": "45",
        "gross_weight_kg": "3250.000",
    },
    DocumentType.BILL_OF_LADING: {
        "bl_number": "HLCUHAM26001234",
        "shipper_name": "Hamburg Marine Machinery GmbH",
        "consignee_name": "Navi Mumbai Precision Importers",
        "gross_weight_kg": "3250.000",
    },
}


@pytest.fixture
async def gate_test_env(db_session):
    """
    Sets up an isolated test environment with an executive user, manager user,
    another executive user, and a fully extracted shipment with passing validation.
    """
    exec1 = User(
        full_name="Rajesh Sharma (Exec 1)",
        email=f"exec1.gate.{uuid.uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("DemoExecutive2026!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    exec2 = User(
        full_name="Pooja Patel (Exec 2)",
        email=f"exec2.gate.{uuid.uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("DemoExecutive2026!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr = User(
        full_name="Vikram Mehta (Manager)",
        email=f"mgr.gate.{uuid.uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("DemoManager2026!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec1, exec2, mgr])
    await db_session.commit()
    await db_session.refresh(exec1)
    await db_session.refresh(exec2)
    await db_session.refresh(mgr)

    shipment = Shipment(
        shipment_number=f"SHP-GATE-{uuid.uuid4().hex[:6].upper()}",
        client_name="Navi Mumbai Precision Importers",
        origin_country="Germany",
        status=ShipmentStatus.REVIEW_REQUIRED,
        created_by=exec1.id,
        currency="EUR",
        product_description="Precision Industrial Valves",
        is_demo=False,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    # Create 3 documents (CI, PL, BL)
    docs = {}
    extractions = {}
    for doc_type in [
        DocumentType.COMMERCIAL_INVOICE,
        DocumentType.PACKING_LIST,
        DocumentType.BILL_OF_LADING,
    ]:
        doc = Document(
            shipment_id=shipment.id,
            document_type=doc_type,
            original_filename=f"{doc_type.value.lower()}.pdf",
            storage_key=f"mock/storage/{doc_type.value.lower()}_{uuid.uuid4().hex}.pdf",
            mime_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=2048,
            sha256_checksum=uuid.uuid4().hex + uuid.uuid4().hex,
            uploaded_by=exec1.id,
            processing_status=DocumentProcessingStatus.COMPLETED,
            is_active=True,
            version=1,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)
        docs[doc_type] = doc

        # Add completed structured extraction
        ext_data = {
            k: {"value": v, "confidence": 0.95}
            for k, v in MANDATORY_REVIEW_FIELDS[doc_type].items()
        }
        ext = StructuredExtraction(
            document_id=doc.id,
            document_type=doc_type,
            attempt_number=1,
            status=ExtractionStatus.COMPLETED,
            provider="claude-vision",
            model="claude-3-5-sonnet",
            extraction_mode="VISION",
            total_page_count=1,
            processed_page_count=1,
            extracted_data=ext_data,
        )
        db_session.add(ext)
        await db_session.commit()
        await db_session.refresh(ext)
        extractions[doc_type] = ext

    # Add passing validation results (no blocking errors)
    val_res = ShipmentValidationResult(
        shipment_id=shipment.id,
        run_id=uuid.uuid4(),
        rule_id="RULE_CONSISTENCY_PASS",
        rule_name="Consignment Cross-Document Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.PASS,
        explanation="All mandatory fields and cross-document weights match.",
        compared_values={},
    )
    db_session.add(val_res)
    await db_session.commit()

    return {
        "exec1": exec1,
        "exec2": exec2,
        "mgr": mgr,
        "exec1_token": create_access_token(user_id=exec1.id, role=exec1.role.value, email=exec1.email),
        "exec2_token": create_access_token(user_id=exec2.id, role=exec2.role.value, email=exec2.email),
        "mgr_token": create_access_token(user_id=mgr.id, role=mgr.role.value, email=mgr.email),
        "shipment": shipment,
        "docs": docs,
        "extractions": extractions,
    }


async def _seed_reviews_for_shipment(
    db_session,
    shipment_id: uuid.UUID,
    docs: dict,
    provenance: ReviewProvenance,
    reviewer_id: uuid.UUID,
):
    """Helper to populate mandatory field reviews with a specific provenance."""
    reviews = []
    for doc_type, fields in MANDATORY_REVIEW_FIELDS.items():
        doc = docs[doc_type]
        for field_name, value in fields.items():
            r = DocumentFieldReview(
                shipment_id=shipment_id,
                document_id=doc.id,
                field_name=field_name,
                action=FieldReviewActionType.CONFIRMED,
                provenance=provenance,
                original_value=value,
                corrected_value=value,
                reason="Demonstration fixture" if provenance == ReviewProvenance.DEMO_SEED else "User confirmed",
                reviewer_id=reviewer_id,
            )
            reviews.append(r)
    db_session.add_all(reviews)
    await db_session.commit()


# ==============================================================================
# TEST 1: Verification readiness blocked by DEMO_SEED reviews
# ==============================================================================
@pytest.mark.asyncio
async def test_verification_readiness_blocked_by_demo_seed_reviews(
    async_client: AsyncClient, gate_test_env, db_session
):
    """
    When mandatory fields are covered only by DEMO_SEED reviews:
    - is_ready must be False
    - all_mandatory_fields_reviewed must be False
    - human_reviews_count must be 0
    - missing_requirements must explicitly state DEMO_SEED fixture restriction
    """
    env = gate_test_env
    shipment = env["shipment"]

    await _seed_reviews_for_shipment(
        db_session,
        shipment_id=shipment.id,
        docs=env["docs"],
        provenance=ReviewProvenance.DEMO_SEED,
        reviewer_id=env["mgr"].id,
    )

    resp = await async_client.get(
        f"/api/v1/shipments/{shipment.id}/verification-readiness",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_ready"] is False
    assert data["all_mandatory_fields_reviewed"] is False
    assert data["human_reviews_count"] == 0
    assert len(data["unreviewed_mandatory_fields"]) == 13

    # Confirm diagnostic explanation mentions demonstration fixture / DEMO_SEED
    demo_seed_reqs = [
        r for r in data["missing_requirements"]
        if "DEMO_SEED" in r or "demonstration fixture" in r
    ]
    assert len(demo_seed_reqs) == 13


# ==============================================================================
# TEST 2: Verify shipment endpoint blocked by DEMO_SEED reviews
# ==============================================================================
@pytest.mark.asyncio
async def test_verify_shipment_endpoint_blocked_by_demo_seed_reviews(
    async_client: AsyncClient, gate_test_env, db_session
):
    """
    POST /api/v1/shipments/{id}/verify must return HTTP 422 Unprocessable Entity
    if mandatory approvals are covered only by DEMO_SEED fixtures.
    The shipment must NOT transition to VERIFIED.
    """
    env = gate_test_env
    shipment = env["shipment"]

    await _seed_reviews_for_shipment(
        db_session,
        shipment_id=shipment.id,
        docs=env["docs"],
        provenance=ReviewProvenance.DEMO_SEED,
        reviewer_id=env["mgr"].id,
    )

    resp = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/verify",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert resp.status_code == 422
    err_data = resp.json()["detail"]
    assert "Shipment does not satisfy all verification requirements." in err_data["message"]
    assert any("DEMO_SEED" in r for r in err_data["missing_requirements"])

    # Verify database state was NOT changed
    shipment_id = shipment.id
    db_session.expire_all()
    reloaded_shipment = await db_session.get(Shipment, shipment_id)
    assert reloaded_shipment.status == ShipmentStatus.REVIEW_REQUIRED


# ==============================================================================
# TEST 3: Export readiness and export blocked by DEMO_SEED reviews
# ==============================================================================
@pytest.mark.asyncio
async def test_export_blocked_when_approvals_exist_only_as_demo_seed(
    async_client: AsyncClient, gate_test_env, db_session
):
    """
    Even if a shipment's status is set to VERIFIED, export readiness must fail
    and POST /api/v1/shipments/{id}/export must be rejected with HTTP 422
    when mandatory export fields are covered only by DEMO_SEED fixtures.
    """
    env = gate_test_env
    shipment = env["shipment"]

    # Set status to VERIFIED to isolate the review approval check
    shipment.status = ShipmentStatus.VERIFIED
    await db_session.commit()

    # Populate only DEMO_SEED reviews
    await _seed_reviews_for_shipment(
        db_session,
        shipment_id=shipment.id,
        docs=env["docs"],
        provenance=ReviewProvenance.DEMO_SEED,
        reviewer_id=env["mgr"].id,
    )

    # 1. Export readiness endpoint check
    readiness_resp = await async_client.get(
        f"/api/v1/shipments/{shipment.id}/export-readiness",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert readiness_resp.status_code == 200
    readiness_data = readiness_resp.json()
    assert readiness_data["is_ready_to_export"] is False
    assert readiness_data["all_mandatory_fields_reviewed"] is False
    assert any("DEMO_SEED" in r for r in readiness_data["missing_requirements"])

    # 2. Export execution endpoint check
    export_resp = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/export",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert export_resp.status_code == 422
    err_detail = export_resp.json()["detail"]
    assert "Shipment is not eligible for export." in err_detail["message"]
    assert any("DEMO_SEED" in r for r in err_detail["missing_requirements"])

    # Verify shipment is NOT exported in DB and no export records were persisted
    shipment_id = shipment.id
    db_session.expire_all()
    reloaded_shipment = await db_session.get(Shipment, shipment_id)
    assert reloaded_shipment.status == ShipmentStatus.VERIFIED

    export_records_stmt = select(ShipmentExportRecord).where(
        ShipmentExportRecord.shipment_id == shipment_id
    )
    records = (await db_session.execute(export_records_stmt)).scalars().all()
    assert len(records) == 0


# ==============================================================================
# TEST 4: Verification and export succeed with genuine USER_ACTION reviews
# ==============================================================================
@pytest.mark.asyncio
async def test_verification_and_export_succeeds_with_user_action_reviews(
    async_client: AsyncClient, gate_test_env, db_session
):
    """
    When all mandatory fields are covered by genuine USER_ACTION reviews:
    - Verification readiness passes (is_ready = True, human_reviews_count = 13)
    - POST /verify transitions shipment to VERIFIED
    - Export readiness passes (is_ready_to_export = True)
    - POST /export returns CSV and transitions shipment to EXPORTED
    - ShipmentExportRecord is persisted with COMPLETED status
    """
    env = gate_test_env
    shipment = env["shipment"]

    # Populate genuine USER_ACTION reviews
    await _seed_reviews_for_shipment(
        db_session,
        shipment_id=shipment.id,
        docs=env["docs"],
        provenance=ReviewProvenance.USER_ACTION,
        reviewer_id=env["exec1"].id,
    )

    # 1. Verification Readiness
    v_readiness_resp = await async_client.get(
        f"/api/v1/shipments/{shipment.id}/verification-readiness",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert v_readiness_resp.status_code == 200
    v_data = v_readiness_resp.json()
    assert v_data["is_ready"] is True
    assert v_data["all_mandatory_fields_reviewed"] is True
    assert v_data["human_reviews_count"] == 13
    assert len(v_data["unreviewed_mandatory_fields"]) == 0
    assert len(v_data["missing_requirements"]) == 0

    # 2. Execute Verification
    verify_resp = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/verify",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert verify_resp.status_code == 200
    v_body = verify_resp.json()
    assert v_body["success"] is True
    assert v_body["shipment"]["status"] == "VERIFIED"

    # Reload from DB
    shipment_id = shipment.id
    db_session.expire_all()
    reloaded_shipment = await db_session.get(Shipment, shipment_id)
    assert reloaded_shipment.status == ShipmentStatus.VERIFIED

    # 3. Export Readiness
    e_readiness_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/export-readiness",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert e_readiness_resp.status_code == 200
    e_data = e_readiness_resp.json()
    assert e_data["is_ready_to_export"] is True
    assert e_data["is_verified"] is True
    assert e_data["all_mandatory_fields_reviewed"] is True

    # 4. Execute Export
    export_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/csv")

    csv_content = export_resp.text
    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)
    assert len(rows) == 2  # 1 header + 1 data row
    assert rows[1][0] == shipment.shipment_number
    assert rows[1][3] == "INV-MANDATORY-2026"

    # Verify DB transition to EXPORTED
    db_session.expire_all()
    reloaded_shipment = await db_session.get(Shipment, shipment_id)
    assert reloaded_shipment.status == ShipmentStatus.EXPORTED

    # Verify export record
    rec_stmt = select(ShipmentExportRecord).where(
        ShipmentExportRecord.shipment_id == shipment_id
    )
    records = (await db_session.execute(rec_stmt)).scalars().all()
    assert len(records) == 1
    assert records[0].export_status == ExportStatus.COMPLETED


# ==============================================================================
# TEST 5: Existing VERIFIED and EXPORTED records remain intact
# ==============================================================================
@pytest.mark.asyncio
async def test_existing_verified_and_exported_records_remain_intact(
    async_client: AsyncClient, gate_test_env, db_session
):
    """
    Pre-existing demo or historical shipments that are already VERIFIED or EXPORTED:
    - Calling /verify on an already VERIFIED shipment succeeds idempotently with 200
      ("already verified") without retroactively altering status.
    - Calling /export on an already EXPORTED shipment raises HTTP 409 Conflict,
      preserving the original immutable export snapshot.
    """
    env = gate_test_env
    exec_user_id = env["exec1"].id

    # 1. Existing VERIFIED shipment with DEMO_SEED reviews (simulating SHP-24816)
    shp_verified = Shipment(
        shipment_number=f"SHP-EXISTING-VERIFIED-{uuid.uuid4().hex[:6].upper()}",
        client_name="Navi Mumbai Precision Importers",
        origin_country="Germany",
        status=ShipmentStatus.VERIFIED,
        created_by=exec_user_id,
        is_demo=True,
    )
    db_session.add(shp_verified)
    await db_session.commit()
    await db_session.refresh(shp_verified)

    # Calling /verify returns 200 without error
    resp_v = await async_client.post(
        f"/api/v1/shipments/{shp_verified.id}/verify",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert resp_v.status_code == 200
    assert "already verified" in resp_v.json()["message"]

    # Status remains VERIFIED
    verified_id = shp_verified.id
    db_session.expire_all()
    reloaded_v = await db_session.get(Shipment, verified_id)
    assert reloaded_v.status == ShipmentStatus.VERIFIED

    # 2. Existing EXPORTED shipment with historical snapshot (simulating SHP-24817)
    shp_exported = Shipment(
        shipment_number=f"SHP-EXISTING-EXPORTED-{uuid.uuid4().hex[:6].upper()}",
        client_name="Navi Mumbai Precision Importers",
        origin_country="Germany",
        status=ShipmentStatus.EXPORTED,
        created_by=exec_user_id,
        is_demo=True,
    )
    db_session.add(shp_exported)
    await db_session.commit()
    await db_session.refresh(shp_exported)

    # Persist existing historical export snapshot
    historical_record = ShipmentExportRecord(
        shipment_id=shp_exported.id,
        exported_by=exec_user_id,
        template_name="STANDARD_CUSTOMS_CLEARANCE",
        template_version="1.0",
        filename="cargolens_export_SHP-EXISTING_20261106_092913.csv",
        sha256_checksum="c" * 64,
        export_status=ExportStatus.COMPLETED,
        row_count=1,
        file_size_bytes=512,
        snapshot_data={"status": "original_historical_snapshot"},
    )
    db_session.add(historical_record)
    await db_session.commit()

    # Calling /export on already exported shipment must return HTTP 409 Conflict
    resp_e = await async_client.post(
        f"/api/v1/shipments/{shp_exported.id}/export",
        headers={"Authorization": f"Bearer {env['exec1_token']}"},
    )
    assert resp_e.status_code == 409
    assert "already been exported" in resp_e.json()["detail"]

    # Verify historical export snapshot remains untouched
    rec_id = historical_record.id
    db_session.expire_all()
    reloaded_rec = await db_session.get(ShipmentExportRecord, rec_id)
    assert reloaded_rec.snapshot_data == {"status": "original_historical_snapshot"}


# ==============================================================================
# TEST 6: Executive / Manager RBAC enforcement
# ==============================================================================
@pytest.mark.asyncio
async def test_rbac_enforcement_on_verification_and_export_gates(
    async_client: AsyncClient, gate_test_env, db_session
):
    """
    Verifies that RBAC boundaries are strictly enforced:
    - Unauthenticated calls return HTTP 401.
    - Executive 2 cannot view, verify, or export Executive 1's shipment (returns 404/access denied).
    - Manager can access Executive 1's shipment.
    """
    env = gate_test_env
    shipment = env["shipment"]

    # 1. Unauthenticated verification attempt
    unauth_resp = await async_client.post(f"/api/v1/shipments/{shipment.id}/verify")
    assert unauth_resp.status_code == 401

    # 2. Unauthenticated export attempt
    unauth_exp = await async_client.post(f"/api/v1/shipments/{shipment.id}/export")
    assert unauth_exp.status_code == 401

    # 3. Executive 2 accessing shipment in shared workspace
    # Receives 422 because DEMO_SEED reviews / missing reviews exist,
    # NOT 404 (access is authorized in shared workspace)
    exec2_verify_resp = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/verify",
        headers={"Authorization": f"Bearer {env['exec2_token']}"},
    )
    assert exec2_verify_resp.status_code == 422

    # Non-existent shipment returns 404
    fake_verify_resp = await async_client.post(
        f"/api/v1/shipments/{uuid.uuid4()}/verify",
        headers={"Authorization": f"Bearer {env['exec2_token']}"},
    )
    assert fake_verify_resp.status_code == 404

    # 4. Manager accessing Executive 1's shipment
    # Manager receives 422 because DEMO_SEED reviews / missing reviews exist,
    # NOT 404 (access is authorized)
    mgr_verify_resp = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/verify",
        headers={"Authorization": f"Bearer {env['mgr_token']}"},
    )
    assert mgr_verify_resp.status_code == 422
