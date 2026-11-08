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


def make_valid_pdf(text: str = "Prompt 7 Test Doc") -> bytes:
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 72), text, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


async def _to_stream(data: bytes):
    yield data


@pytest.fixture
async def p7_env(db_session):
    exec_user = User(
        full_name="P7 Executive",
        email=f"exec.p7.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    other_exec = User(
        full_name="Other Executive",
        email=f"other.exec.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr_user = User(
        full_name="P7 Manager",
        email=f"mgr.p7.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec_user, other_exec, mgr_user])
    await db_session.commit()
    await db_session.refresh(exec_user)
    await db_session.refresh(other_exec)
    await db_session.refresh(mgr_user)

    shipment = Shipment(
        shipment_number=f"SHP-P7-{uuid4().hex[:6].upper()}",
        client_name="Nhava Sheva Freightlines",
        origin_country="IN",
        status=ShipmentStatus.CREATED,
        created_by=exec_user.id,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_valid_pdf("Commercial Invoice Sample Content")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="ci_p7.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=exec_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    ext = StructuredExtraction(
        document_id=doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data={
            "invoice_number": {"value": "INV-P7-001", "confidence": 0.98},
            "invoice_date": {"value": "2026-03-15", "confidence": 0.98},
            "seller_name": {"value": "Nhava Sheva Freightlines", "confidence": 0.98},
            "buyer_name": {"value": "JNPT Importers Ltd", "confidence": 0.98},
            "gross_weight_kg": {"value": "3120.00", "confidence": 0.95},
            "grand_total": {"value": "15000.00", "confidence": 0.96},
            "currency": {"value": "USD", "confidence": 0.99},
            "line_items": [
                {
                    "description": {"value": "Consignment Machinery Components", "confidence": 0.95},
                    "quantity": {"value": "100.00", "confidence": 0.95},
                    "unit_price": {"value": "150.00", "confidence": 0.95},
                    "line_total": {"value": "15000.00", "confidence": 0.95},
                }
            ],
        },
    )
    db_session.add(ext)
    await db_session.commit()
    await db_session.refresh(ext)

    exec_token = create_access_token(exec_user.id, exec_user.role.value, exec_user.email)
    other_token = create_access_token(other_exec.id, other_exec.role.value, other_exec.email)
    mgr_token = create_access_token(mgr_user.id, mgr_user.role.value, mgr_user.email)

    return {
        "exec_user": exec_user,
        "other_exec": other_exec,
        "mgr_user": mgr_user,
        "shipment": shipment,
        "doc": doc,
        "ext": ext,
        "exec_token": exec_token,
        "other_token": other_token,
        "mgr_token": mgr_token,
    }


@pytest.mark.asyncio
async def test_field_confirmation_and_correction_flow(async_client: AsyncClient, p7_env):
    """
    Verifies human field review actions:
    1. Confirming a field sets action=CONFIRMED and preserves original extracted value.
    2. Correcting a field sets action=CORRECTED and saves corrected_value and reason.
    3. Type validation rejects negative or invalid decimal numbers.
    4. Unowned executive cannot review another executive's shipment.
    """
    shipment_id = p7_env["shipment"].id
    doc_id = p7_env["doc"].id
    exec_token = p7_env["exec_token"]
    other_token = p7_env["other_token"]

    # 1. Human confirms invoice_number
    conf_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CONFIRMED",
        },
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert conf_resp.status_code == 201
    conf_data = conf_resp.json()
    assert conf_data["field_name"] == "invoice_number"
    assert conf_data["action"] == "CONFIRMED"
    assert conf_data["original_value"] == "INV-P7-001"
    assert conf_data["corrected_value"] == "INV-P7-001"

    # 2. Human corrects gross_weight_kg from 3120 to 3165
    corr_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/reviews",
        json={
            "field_name": "gross_weight_kg",
            "action": "CORRECTED",
            "corrected_value": "3165.00",
            "reason": "Matches Packing List scale ticket",
        },
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert corr_resp.status_code == 201
    corr_data = corr_resp.json()
    assert corr_data["field_name"] == "gross_weight_kg"
    assert corr_data["action"] == "CORRECTED"
    assert corr_data["original_value"] == "3120.00"
    assert corr_data["corrected_value"] == "3165.00"
    assert corr_data["reason"] == "Matches Packing List scale ticket"

    # 3. Invalid numeric value rejected by schema
    bad_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/reviews",
        json={
            "field_name": "gross_weight_kg",
            "action": "CORRECTED",
            "corrected_value": "not-a-number",
            "reason": "Invalid number test",
        },
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert bad_resp.status_code == 422

    # 4. Another authorized executive can review in shared workspace -> 201 Created
    shared_exec_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CONFIRMED",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert shared_exec_resp.status_code == 201

    # Unauthenticated rejected -> 401
    unauth_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/reviews",
        json={
            "field_name": "invoice_number",
            "action": "CONFIRMED",
        },
    )
    assert unauth_resp.status_code == 401

    # 5. List document reviews (now 3 reviews in shared workspace)
    list_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/reviews",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 3

    # 6. Global audit history
    hist_resp = await async_client.get(
        "/api/v1/review/audit-history",
        headers={"Authorization": f"Bearer {p7_env['mgr_token']}"},
    )
    assert hist_resp.status_code == 200
    assert hist_resp.json()["total"] >= 2


@pytest.mark.asyncio
async def test_dashboard_stats_endpoint(async_client: AsyncClient, p7_env):
    """Verifies that the dashboard stats endpoint returns role-aware real live metrics."""
    # Executive dashboard
    exec_resp = await async_client.get(
        "/api/v1/dashboard/stats",
        headers={"Authorization": f"Bearer {p7_env['exec_token']}"},
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["role"] == "DOCUMENTATION_EXECUTIVE"
    assert exec_data["executive"] is not None
    assert exec_data["executive"]["my_shipments_count"] >= 1
    assert exec_data["executive"]["documents_uploaded_count"] >= 1

    # Manager dashboard
    mgr_resp = await async_client.get(
        "/api/v1/dashboard/stats",
        headers={"Authorization": f"Bearer {p7_env['mgr_token']}"},
    )
    assert mgr_resp.status_code == 200
    mgr_data = mgr_resp.json()
    assert mgr_data["role"] == "DOCUMENTATION_MANAGER"
    assert mgr_data["manager"] is not None
    assert mgr_data["manager"]["total_shipments_count"] >= 1
    assert "CREATED" in mgr_data["manager"]["shipments_by_status"]


@pytest.mark.asyncio
async def test_verification_readiness_and_workflow_verification(async_client: AsyncClient, p7_env, db_session):
    """
    Verifies that a shipment cannot be verified until all criteria are satisfied:
    - Initially missing Packing List & Bill of Lading -> verify returns 422.
    - Adding required documents and passing validations -> verify succeeds.
    """
    shipment_id = p7_env["shipment"].id
    exec_token = p7_env["exec_token"]

    # 1. Readiness check reports missing documents
    ready_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert ready_resp.status_code == 200
    ready_data = ready_resp.json()
    assert ready_data["is_ready"] is False
    assert len(ready_data["missing_requirements"]) > 0

    # 2. Workflow verify attempt fails with 422
    verify_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert verify_resp.status_code == 422
    detail = verify_resp.json()["detail"]
    assert "missing_requirements" in detail

    # 3. Add Packing List and Bill of Lading
    storage = get_storage_service()
    pkg_key = storage.get_safe_storage_key("pdf")
    pkg_bytes = make_valid_pdf("Packing List Content")
    await storage.save_file(_to_stream(pkg_bytes), pkg_key)
    pkg_doc = Document(
        shipment_id=shipment_id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="pl.pdf",
        storage_key=pkg_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pkg_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=p7_env["exec_user"].id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )

    bl_key = storage.get_safe_storage_key("pdf")
    bl_bytes = make_valid_pdf("Bill of Lading Content")
    await storage.save_file(_to_stream(bl_bytes), bl_key)
    bl_doc = Document(
        shipment_id=shipment_id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="bl.pdf",
        storage_key=bl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(bl_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=p7_env["exec_user"].id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add_all([pkg_doc, bl_doc])
    await db_session.commit()
    await db_session.refresh(pkg_doc)
    await db_session.refresh(bl_doc)

    # Add completed extractions for both
    pkg_ext = StructuredExtraction(
        document_id=pkg_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        total_page_count=1,
        processed_page_count=1,
        extracted_data={
            "invoice_reference": {"value": "INV-P7-001", "confidence": 0.98},
            "package_count": {"value": "100", "confidence": 0.95},
            "gross_weight_kg": {"value": "3120.00", "confidence": 0.95},
        },
    )
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
        extracted_data={
            "bl_number": {"value": "BL-P7-888", "confidence": 0.97},
            "shipper_name": {"value": "Nhava Sheva Freightlines", "confidence": 0.95},
            "consignee_name": {"value": "JNPT Importers Ltd", "confidence": 0.95},
            "gross_weight_kg": {"value": "3120.00", "confidence": 0.95},
        },
    )
    db_session.add_all([pkg_ext, bl_ext])
    await db_session.commit()

    # Run validations
    val_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/validations/run",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert val_resp.status_code == 200

    # Re-check readiness before human reviews: should still NOT be ready because mandatory fields need review
    ready_resp_pre = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert ready_resp_pre.status_code == 200
    ready_pre_data = ready_resp_pre.json()
    assert ready_pre_data["all_documents_present"] is True
    assert ready_pre_data["all_extractions_completed"] is True
    assert ready_pre_data["has_blocking_failures"] is False
    assert ready_pre_data["all_mandatory_fields_reviewed"] is False
    assert ready_pre_data["is_ready"] is False
    assert len(ready_pre_data["unreviewed_mandatory_fields"]) > 0

    # Workflow verify attempt still fails with 422 due to unreviewed mandatory fields
    blocked_verify = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert blocked_verify.status_code == 422

    # Human confirms all mandatory fields
    # 1. Commercial Invoice mandatory fields
    ci_doc = p7_env["doc"]
    for field in ["invoice_number", "invoice_date", "seller_name", "buyer_name", "grand_total", "currency"]:
        await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{ci_doc.id}/reviews",
            json={"field_name": field, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {exec_token}"},
        )

    # 2. Packing List mandatory fields
    for field in ["invoice_reference", "package_count", "gross_weight_kg"]:
        await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{pkg_doc.id}/reviews",
            json={"field_name": field, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {exec_token}"},
        )

    # 3. Bill of Lading mandatory fields
    for field in ["bl_number", "shipper_name", "consignee_name", "gross_weight_kg"]:
        await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{bl_doc.id}/reviews",
            json={"field_name": field, "action": "CONFIRMED"},
            headers={"Authorization": f"Bearer {exec_token}"},
        )

    # Re-check readiness after human review
    ready_resp2 = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/verification-readiness",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert ready_resp2.status_code == 200
    ready2_data = ready_resp2.json()
    assert ready2_data["all_documents_present"] is True
    assert ready2_data["all_extractions_completed"] is True
    assert ready2_data["has_blocking_failures"] is False
    assert ready2_data["all_mandatory_fields_reviewed"] is True
    assert ready2_data["is_ready"] is True

    # Now verify succeeds through workflow
    verify_resp2 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/verify",
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert verify_resp2.status_code == 200
    assert verify_resp2.json()["success"] is True
    assert verify_resp2.json()["shipment"]["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_document_page_image_rendering(async_client: AsyncClient, p7_env):
    """Verifies rendering a PDF page as JPEG image for the side-by-side review workspace."""
    shipment_id = p7_env["shipment"].id
    doc_id = p7_env["doc"].id
    token = p7_env["exec_token"]

    img_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/pages/1/image",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"] == "image/jpeg"
    assert "x-total-pages" in img_resp.headers
    assert img_resp.headers["x-total-pages"] == "1"
    assert len(img_resp.content) > 100

    # Non-existent page 99 returns 404
    bad_page = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/pages/99/image",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_page.status_code == 404


@pytest.mark.asyncio
async def test_validation_issues_across_shipments(async_client: AsyncClient, p7_env, db_session):
    """Verifies querying validation issues across shipments."""
    shipment_id = p7_env["shipment"].id
    token = p7_env["exec_token"]

    # Insert a dummy failed validation result
    val_res = ShipmentValidationResult(
        shipment_id=shipment_id,
        run_id=uuid4(),
        rule_id="RULE_GROSS_WEIGHT_CONSISTENCY",
        rule_name="Gross Weight Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.FAIL,
        explanation="45 kg discrepancy between Invoice and Packing List",
        compared_values={"invoice_weight": "3120", "packing_weight": "3165"},
    )
    db_session.add(val_res)
    await db_session.commit()

    issues_resp = await async_client.get(
        "/api/v1/validations/issues",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert issues_resp.status_code == 200
    data = issues_resp.json()
    assert data["total"] >= 1
    found = any(i["rule_id"] == "RULE_GROSS_WEIGHT_CONSISTENCY" for i in data["items"])
    assert found is True
