import io
from decimal import Decimal
from uuid import uuid4
import pytest
from httpx import AsyncClient
import pymupdf

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome, ValidationSeverity
from app.models.field_review import DocumentFieldReview, FieldReviewActionType
from app.security import hash_password, create_access_token
from app.storage import get_storage_service


def make_pdf_bytes(title: str = "Test Doc") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), title, fontsize=14)
    b = doc.tobytes()
    doc.close()
    return b


async def _stream_bytes(data: bytes):
    yield data


@pytest.fixture
async def workflow_fixture(db_session):
    # Executive 1 (Owner)
    exec_1 = User(
        full_name="Executive One",
        email=f"exec1.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    # Executive 2 (Different User)
    exec_2 = User(
        full_name="Executive Two",
        email=f"exec2.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    # Manager
    manager = User(
        full_name="Operations Manager",
        email=f"mgr.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec_1, exec_2, manager])
    await db_session.commit()
    await db_session.refresh(exec_1)
    await db_session.refresh(exec_2)
    await db_session.refresh(manager)

    # Shipment owned by Executive 1
    shipment = Shipment(
        shipment_number=f"SHP-WF-{uuid4().hex[:6].upper()}",
        client_name="Nhava Sheva Freight Consolidators",
        origin_country="IN",
        status=ShipmentStatus.CREATED,
        created_by=exec_1.id,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    # Documents for CI, PL, BL
    storage = get_storage_service()

    ci_key = storage.get_safe_storage_key("pdf")
    ci_bytes = make_pdf_bytes("Commercial Invoice")
    await storage.save_file(_stream_bytes(ci_bytes), ci_key)
    ci_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="ci.pdf",
        storage_key=ci_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(ci_bytes),
        sha256_checksum=f"cs_ci_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )

    pl_key = storage.get_safe_storage_key("pdf")
    pl_bytes = make_pdf_bytes("Packing List")
    await storage.save_file(_stream_bytes(pl_bytes), pl_key)
    pl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="pl.pdf",
        storage_key=pl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pl_bytes),
        sha256_checksum=f"cs_pl_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )

    bl_key = storage.get_safe_storage_key("pdf")
    bl_bytes = make_pdf_bytes("Bill of Lading")
    await storage.save_file(_stream_bytes(bl_bytes), bl_key)
    bl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="bl.pdf",
        storage_key=bl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(bl_bytes),
        sha256_checksum=f"cs_bl_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )

    db_session.add_all([ci_doc, pl_doc, bl_doc])
    await db_session.commit()
    await db_session.refresh(ci_doc)
    await db_session.refresh(pl_doc)
    await db_session.refresh(bl_doc)

    # Extractions with valid values
    ci_data = {
        "invoice_number": {"value": "INV-2026-001", "confidence": 0.99},
        "invoice_date": {"value": "2026-03-20", "confidence": 0.98},
        "seller_name": {"value": "Apex Exports Pvt Ltd", "confidence": 0.97},
        "buyer_name": {"value": "Global Logistics NV", "confidence": 0.97},
        "grand_total": {"value": "50000.00", "confidence": 0.99},
        "currency": {"value": "USD", "confidence": 0.99},
        "subtotal": {"value": "50000.00", "confidence": 0.99},  # optional
    }
    ci_ext = StructuredExtraction(
        document_id=ci_doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=ci_data,
    )

    pl_data = {
        "invoice_reference": {"value": "INV-2026-001", "confidence": 0.98},
        "package_count": {"value": "150", "confidence": 0.95},
        "gross_weight_kg": {"value": "4500.00", "confidence": 0.96},
    }
    pl_ext = StructuredExtraction(
        document_id=pl_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=pl_data,
    )

    bl_data = {
        "bl_number": {"value": "BL-MAERSK-9001", "confidence": 0.98},
        "shipper_name": {"value": "Apex Exports Pvt Ltd", "confidence": 0.97},
        "consignee_name": {"value": "Global Logistics NV", "confidence": 0.97},
        "gross_weight_kg": {"value": "4500.00", "confidence": 0.96},
    }
    bl_ext = StructuredExtraction(
        document_id=bl_doc.id,
        document_type=DocumentType.BILL_OF_LADING,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data=bl_data,
    )

    db_session.add_all([ci_ext, pl_ext, bl_ext])
    await db_session.commit()
    await db_session.refresh(ci_ext)
    await db_session.refresh(pl_ext)
    await db_session.refresh(bl_ext)

    # Initial successful validation results
    val_run_id = uuid4()
    val_result = ShipmentValidationResult(
        shipment_id=shipment.id,
        run_id=val_run_id,
        rule_id="RULE_INVOICE_REF",
        rule_name="Invoice Reference Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.PASS,
        explanation="Invoice reference matches between CI and PL.",
        compared_values={"ci_number": "INV-2026-001", "pl_ref": "INV-2026-001"},
    )
    db_session.add(val_result)
    await db_session.commit()

    exec1_token = create_access_token(exec_1.id, exec_1.role.value, exec_1.email)
    exec2_token = create_access_token(exec_2.id, exec_2.role.value, exec_2.email)
    mgr_token = create_access_token(manager.id, manager.role.value, manager.email)

    return {
        "exec_1": exec_1,
        "exec_2": exec_2,
        "manager": manager,
        "shipment": shipment,
        "ci_doc": ci_doc,
        "pl_doc": pl_doc,
        "bl_doc": bl_doc,
        "ci_ext": ci_ext,
        "pl_ext": pl_ext,
        "bl_ext": bl_ext,
        "exec1_token": exec1_token,
        "exec2_token": exec2_token,
        "mgr_token": mgr_token,
    }


@pytest.mark.asyncio
async def test_ai_extraction_alone_never_allows_verification(async_client: AsyncClient, workflow_fixture):
    """
    AI extraction completed alone must NEVER satisfy verification readiness.
    Without human reviews for each mandatory field, verification readiness is False
    and POST /verify returns HTTP 422.
    """
    shipment_id = workflow_fixture["shipment"].id
    token = workflow_fixture["exec1_token"]

    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ready_resp.status_code == 200
    data = ready_resp.json()
    assert data["all_documents_present"] is True
    assert data["all_extractions_completed"] is True
    assert data["all_mandatory_fields_reviewed"] is False
    assert data["is_ready"] is False
    assert len(data["unreviewed_mandatory_fields"]) == 13  # 6 CI + 3 PL + 4 BL

    # Verify attempt returns 422
    v_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v_resp.status_code == 422
    assert "missing_requirements" in v_resp.json()["detail"]


@pytest.mark.asyncio
async def test_partial_mandatory_reviews_blocks_verification(async_client: AsyncClient, workflow_fixture):
    """
    Reviewing only a subset of mandatory fields (e.g. only CI fields) blocks verification.
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    token = workflow_fixture["exec1_token"]

    # Confirm all 6 mandatory CI fields
    for field in ["invoice_number", "invoice_date", "seller_name", "buyer_name", "grand_total", "currency"]:
        resp = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
            json={"field_name": field, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

    # Check readiness: PL and BL fields are still unreviewed!
    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ready_resp.json()
    assert data["all_mandatory_fields_reviewed"] is False
    assert data["is_ready"] is False
    # Unreviewed fields should be the 3 PL + 4 BL = 7 fields
    assert len(data["unreviewed_mandatory_fields"]) == 7

    v_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v_resp.status_code == 422


@pytest.mark.asyncio
async def test_all_mandatory_fields_reviewed_allows_verification(async_client: AsyncClient, workflow_fixture):
    """
    Confirming/correcting all mandatory fields across CI, PL, BL allows verification.
    Optional fields do NOT need to be reviewed.
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    pl_doc = workflow_fixture["pl_doc"]
    bl_doc = workflow_fixture["bl_doc"]
    token = workflow_fixture["exec1_token"]

    # CI mandatory fields
    for f in ["invoice_number", "invoice_date", "seller_name", "buyer_name", "grand_total", "currency"]:
        await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
            json={"field_name": f, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # PL mandatory fields
    for f in ["invoice_reference", "package_count", "gross_weight_kg"]:
        await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{pl_doc.id}/reviews",
            json={"field_name": f, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # BL mandatory fields
    for f in ["bl_number", "shipper_name", "consignee_name", "gross_weight_kg"]:
        await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{bl_doc.id}/reviews",
            json={"field_name": f, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Readiness should now be True (notice optional subtotal was NOT reviewed)
    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ready_resp.status_code == 200
    data = ready_resp.json()
    assert data["all_mandatory_fields_reviewed"] is True
    assert len(data["unreviewed_mandatory_fields"]) == 0
    assert data["is_ready"] is True

    # Verification workflow succeeds
    v_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v_resp.status_code == 200
    assert v_resp.json()["success"] is True
    assert v_resp.json()["shipment"]["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_mandatory_reason_required_for_corrections(async_client: AsyncClient, workflow_fixture):
    """
    Submitting action CORRECTED without a reason or with empty whitespace
    must fail validation (HTTP 422). Submitting with reason succeeds.
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    token = workflow_fixture["exec1_token"]

    # 1. Missing reason field
    r1 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CORRECTED",
            "corrected_value": "INV-CORRECTED-123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 422

    # 2. Empty whitespace reason
    r2 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CORRECTED",
            "corrected_value": "INV-CORRECTED-123",
            "reason": "   ",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 422

    # 3. Valid reason succeeds
    r3 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CORRECTED",
            "corrected_value": "INV-CORRECTED-123",
            "reason": "Corrected typo from OCR scan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 201
    assert r3.json()["reason"] == "Corrected typo from OCR scan"
    assert r3.json()["corrected_value"] == "INV-CORRECTED-123"


@pytest.mark.asyncio
async def test_confirmed_field_with_missing_value_blocks_verification(
    async_client: AsyncClient, workflow_fixture, db_session
):
    """
    If AI extracted empty/null for a mandatory field, confirming it without a value
    blocks verification. It must be provided via human correction.
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    ci_ext = workflow_fixture["ci_ext"]
    token = workflow_fixture["exec1_token"]

    from sqlalchemy.orm.attributes import flag_modified

    # Remove buyer_name value from extraction data
    updated_data = dict(ci_ext.extracted_data)
    updated_data["buyer_name"] = {"value": None, "confidence": 0.0}
    ci_ext.extracted_data = updated_data
    flag_modified(ci_ext, "extracted_data")
    db_session.add(ci_ext)
    await db_session.commit()

    # Human confirms buyer_name without value
    conf_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        json={"field_name": "buyer_name", "action": "CONFIRMED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert conf_resp.status_code == 201

    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ready_resp.json()
    assert data["is_ready"] is False
    assert any("buyer_name" in req for req in data["missing_requirements"])


@pytest.mark.asyncio
async def test_blocking_validation_failure_blocks_verification(
    async_client: AsyncClient, workflow_fixture, db_session
):
    """
    Unresolved blocking validation failure (outcome=FAIL) blocks verification.
    """
    shipment_id = workflow_fixture["shipment"].id
    token = workflow_fixture["exec1_token"]

    # Insert a failing validation result
    val_fail = ShipmentValidationResult(
        shipment_id=shipment_id,
        run_id=uuid4(),
        rule_id="RULE_GROSS_WEIGHT",
        rule_name="Gross Weight Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.FAIL,
        explanation="Weight mismatch across CI and PL",
        compared_values={"ci_weight": "4500", "pl_weight": "5000"},
    )
    db_session.add(val_fail)
    await db_session.commit()

    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ready_resp.json()
    assert data["has_blocking_failures"] is True
    assert data["blocking_validation_failures_count"] >= 1
    assert data["is_ready"] is False


@pytest.mark.asyncio
async def test_missing_required_document_blocks_verification(
    async_client: AsyncClient, workflow_fixture, db_session
):
    """
    Missing any of the 3 required documents (e.g. deactivating BL) blocks verification.
    """
    shipment_id = workflow_fixture["shipment"].id
    bl_doc = workflow_fixture["bl_doc"]
    token = workflow_fixture["exec1_token"]

    bl_doc.is_active = False
    db_session.add(bl_doc)
    await db_session.commit()

    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ready_resp.json()
    assert data["all_documents_present"] is False
    assert "BILL_OF_LADING" in data["documents_missing"]
    assert data["is_ready"] is False


@pytest.mark.asyncio
async def test_executive_rbac_isolation(async_client: AsyncClient, workflow_fixture):
    """
    Documentation Executive 2 cannot access Executive 1's shipments,
    documents, images, or reviews (returns 404 to avoid disclosure).
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    exec2_token = workflow_fixture["exec2_token"]

    # 1. Get shipment
    r1 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r1.status_code == 404

    # 2. Get document reviews
    r2 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r2.status_code == 404

    # 3. Post review
    r3 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        json={"field_name": "invoice_number", "action": "CONFIRMED"},
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r3.status_code == 404

    # 4. Get page image
    r4 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/pages/1/image",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r4.status_code == 404

    # 5. Verify workflow
    r5 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r5.status_code == 404


@pytest.mark.asyncio
async def test_manager_has_org_wide_access(async_client: AsyncClient, workflow_fixture):
    """
    Documentation Manager can access all shipments, documents, images, and reviews.
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    mgr_token = workflow_fixture["mgr_token"]

    r1 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r1.status_code == 200

    r2 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r2.status_code == 200

    r3 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/pages/1/image",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_manual_patch_verified_or_exported_prohibited(async_client: AsyncClient, workflow_fixture):
    """
    Both Executive and Manager are forbidden (HTTP 403) from setting status
    to VERIFIED or EXPORTED via standard PATCH /shipments/{id}.
    """
    shipment_id = workflow_fixture["shipment"].id
    exec_token = workflow_fixture["exec1_token"]
    mgr_token = workflow_fixture["mgr_token"]

    # Executive attempts VERIFIED
    r1 = await async_client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "VERIFIED"},
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert r1.status_code == 403

    # Executive attempts EXPORTED
    r2 = await async_client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "EXPORTED"},
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert r2.status_code == 403

    # Manager attempts VERIFIED
    r3 = await async_client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "VERIFIED"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r3.status_code == 403

    # Manager attempts EXPORTED
    r4 = await async_client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "EXPORTED"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r4.status_code == 403


@pytest.mark.asyncio
async def test_raw_ai_extractions_preserved_after_corrections(
    async_client: AsyncClient, workflow_fixture, db_session
):
    """
    Ensures human corrections do NOT mutate the raw StructuredExtraction database row.
    Original AI-extracted values remain untouched in extracted_data.
    """
    shipment_id = workflow_fixture["shipment"].id
    ci_doc = workflow_fixture["ci_doc"]
    ci_ext = workflow_fixture["ci_ext"]
    token = workflow_fixture["exec1_token"]

    original_invoice_num = ci_ext.extracted_data["invoice_number"]["value"]

    # Submit correction
    corr_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CORRECTED",
            "corrected_value": "INV-NEW-OVERRIDE",
            "reason": "Corrected manually by executive",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert corr_resp.status_code == 201

    # Reload StructuredExtraction from database
    await db_session.refresh(ci_ext)
    assert ci_ext.extracted_data["invoice_number"]["value"] == original_invoice_num
