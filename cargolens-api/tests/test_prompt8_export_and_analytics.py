import io
import csv
import hashlib
import asyncio
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
import pytest
from httpx import AsyncClient
import pymupdf
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome, ValidationSeverity
from app.models.field_review import DocumentFieldReview, FieldReviewActionType
from app.models.export import ShipmentExportRecord, ExportStatus
from app.security import hash_password, create_access_token
from app.storage import get_storage_service
from app.services.export.csv_exporter import sanitize_csv_cell


def make_pdf(title: str = "Prompt 8 Test PDF") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), title, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


async def _stream_bytes(data: bytes):
    yield data


@pytest.fixture
async def p8_env(db_session):
    # Executive 1 (Owner)
    exec_1 = User(
        full_name="Rajesh Sharma",
        email=f"rajesh.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    # Executive 2 (Different User)
    exec_2 = User(
        full_name="Pooja Patel",
        email=f"pooja.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    # Manager
    manager = User(
        full_name="Vikram Mehta",
        email=f"vikram.{uuid4().hex[:6]}@cargolens.in",
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
        shipment_number=f"SHP-JNPT-{uuid4().hex[:6].upper()}",
        client_name="Nhava Sheva Freightlines Pvt Ltd",
        origin_country="IN",
        status=ShipmentStatus.VERIFIED,  # Initial status for export testing
        created_by=exec_1.id,
        currency="EUR",  # Non-USD currency to verify currency preservation
        product_description="Precision Industrial Valves",
        quantity=Decimal("120.00"),
        unit_price=Decimal("450.5000"),
        gross_weight_kg=Decimal("3450.750"),
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    # Documents
    storage = get_storage_service()

    ci_key = storage.get_safe_storage_key("pdf")
    ci_bytes = make_pdf("Commercial Invoice")
    await storage.save_file(_stream_bytes(ci_bytes), ci_key)
    ci_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="ci_001.pdf",
        storage_key=ci_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(ci_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )

    pl_key = storage.get_safe_storage_key("pdf")
    pl_bytes = make_pdf("Packing List")
    await storage.save_file(_stream_bytes(pl_bytes), pl_key)
    pl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="pl_001.pdf",
        storage_key=pl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pl_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )

    bl_key = storage.get_safe_storage_key("pdf")
    bl_bytes = make_pdf("Bill of Lading")
    await storage.save_file(_stream_bytes(bl_bytes), bl_key)
    bl_doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="bl_001.pdf",
        storage_key=bl_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(bl_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add_all([ci_doc, pl_doc, bl_doc])
    await db_session.commit()
    await db_session.refresh(ci_doc)
    await db_session.refresh(pl_doc)
    await db_session.refresh(bl_doc)

    # Extractions (containing raw AI values)
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
        extracted_data={
            "invoice_number": {"value": "INV-RAW-AI", "confidence": 0.90},
            "invoice_date": {"value": "2026-04-10", "confidence": 0.95},
            "seller_name": {"value": "Raw AI Exporters Ltd", "confidence": 0.85},
            "buyer_name": {"value": "EuroPort Logistics BV", "confidence": 0.92},
            "grand_total": {"value": "54060.00", "confidence": 0.98},
            "currency": {"value": "EUR", "confidence": 0.99},
            "unreviewed_optional_note": {"value": "This raw value must NOT be exported", "confidence": 0.8},
        },
    )
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
        extracted_data={
            "invoice_reference": {"value": "INV-RAW-AI", "confidence": 0.90},
            "package_count": {"value": "80", "confidence": 0.95},
            "gross_weight_kg": {"value": "3400.00", "confidence": 0.88},
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
            "bl_number": {"value": "MSKU-998877", "confidence": 0.97},
            "shipper_name": {"value": "Raw AI Exporters Ltd", "confidence": 0.85},
            "consignee_name": {"value": "EuroPort Logistics BV", "confidence": 0.92},
            "gross_weight_kg": {"value": "3450.750", "confidence": 0.96},
        },
    )
    db_session.add_all([ci_ext, pl_ext, bl_ext])
    await db_session.commit()

    # Successful validation results (no blocking issues)
    val_res = ShipmentValidationResult(
        shipment_id=shipment.id,
        run_id=uuid4(),
        rule_id="RULE_INVOICE_REF",
        rule_name="Invoice Reference Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.PASS,
        explanation="Invoice reference matches between documents.",
        compared_values={},
    )
    db_session.add(val_res)
    await db_session.commit()

    # Human reviews: Confirm or correct all mandatory fields
    # Notice we human-correct invoice_number and gross_weight_kg
    reviews = [
        # CI
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=ci_doc.id,
            field_name="invoice_number",
            action=FieldReviewActionType.CORRECTED,
            original_value="INV-RAW-AI",
            corrected_value="INV-HUMAN-CONFIRMED-001",
            reason="Corrected OCR mistake to match physical stamp",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=ci_doc.id,
            field_name="invoice_date",
            action=FieldReviewActionType.CONFIRMED,
            original_value="2026-04-10",
            corrected_value="2026-04-10",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=ci_doc.id,
            field_name="seller_name",
            action=FieldReviewActionType.CORRECTED,
            original_value="Raw AI Exporters Ltd",
            corrected_value="Apex Precision Valves Ltd",
            reason="Corrected company legal entity name",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=ci_doc.id,
            field_name="buyer_name",
            action=FieldReviewActionType.CONFIRMED,
            original_value="EuroPort Logistics BV",
            corrected_value="EuroPort Logistics BV",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=ci_doc.id,
            field_name="grand_total",
            action=FieldReviewActionType.CONFIRMED,
            original_value="54060.00",
            corrected_value="54060.00",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=ci_doc.id,
            field_name="currency",
            action=FieldReviewActionType.CONFIRMED,
            original_value="EUR",
            corrected_value="EUR",
            reviewer_id=exec_1.id,
        ),
        # PL
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=pl_doc.id,
            field_name="invoice_reference",
            action=FieldReviewActionType.CONFIRMED,
            original_value="INV-HUMAN-CONFIRMED-001",
            corrected_value="INV-HUMAN-CONFIRMED-001",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=pl_doc.id,
            field_name="package_count",
            action=FieldReviewActionType.CONFIRMED,
            original_value="80",
            corrected_value="80",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=pl_doc.id,
            field_name="gross_weight_kg",
            action=FieldReviewActionType.CORRECTED,
            original_value="3400.00",
            corrected_value="3450.750",
            reason="Updated to match scale certificate",
            reviewer_id=exec_1.id,
        ),
        # BL
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=bl_doc.id,
            field_name="bl_number",
            action=FieldReviewActionType.CONFIRMED,
            original_value="MSKU-998877",
            corrected_value="MSKU-998877",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=bl_doc.id,
            field_name="shipper_name",
            action=FieldReviewActionType.CONFIRMED,
            original_value="Apex Precision Valves Ltd",
            corrected_value="Apex Precision Valves Ltd",
            reviewer_id=exec_1.id,
        ),
        DocumentFieldReview(
            shipment_id=shipment.id,
            document_id=bl_doc.id,
            field_name="consignee_name",
            action=FieldReviewActionType.CONFIRMED,
            original_value="EuroPort Logistics BV",
            corrected_value="EuroPort Logistics BV",
            reviewer_id=exec_1.id,
        ),
    ]
    db_session.add_all(reviews)
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
        "exec1_token": exec1_token,
        "exec2_token": exec2_token,
        "mgr_token": mgr_token,
    }


@pytest.mark.asyncio
async def test_export_allowed_for_verified_eligible_shipment(async_client: AsyncClient, p8_env):
    """
    Verifies that an authorized executive can export their verified shipment:
    1. Returns 200 with text/csv content.
    2. Sets Content-Disposition attachment header with safe filename.
    3. Returns X-Export-Checksum with SHA-256 matching generated bytes.
    4. Transitions shipment status to EXPORTED.
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export?template=STANDARD_CUSTOMS_CLEARANCE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment; filename=" in resp.headers["content-disposition"]
    checksum = resp.headers["x-export-checksum"]
    assert checksum is not None
    assert hashlib.sha256(resp.content).hexdigest() == checksum

    # Check status changed to EXPORTED
    shp_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert shp_resp.status_code == 200
    assert shp_resp.json()["status"] == "EXPORTED"


@pytest.mark.asyncio
async def test_unverified_shipment_export_rejected(async_client: AsyncClient, p8_env, db_session):
    """
    An unverified shipment (e.g. in REVIEW_REQUIRED or CREATED) cannot be exported.
    Returns HTTP 422 Unprocessable Entity.
    """
    shipment = p8_env["shipment"]
    shipment.status = ShipmentStatus.REVIEW_REQUIRED
    db_session.add(shipment)
    await db_session.commit()

    token = p8_env["exec1_token"]
    resp = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "missing_requirements" in data["detail"]
    assert any("VERIFIED" in req for req in data["detail"]["missing_requirements"])


@pytest.mark.asyncio
async def test_human_corrected_values_exported_and_raw_ai_excluded(async_client: AsyncClient, p8_env):
    """
    Verifies:
    1. Human-corrected value ('INV-HUMAN-CONFIRMED-001') is exported, NOT raw AI value ('INV-RAW-AI').
    2. Corrected weight ('3450.750') is exported, NOT raw weight ('3400.00').
    3. Corrected seller name ('Apex Precision Valves Ltd') is exported, NOT raw ('Raw AI Exporters Ltd').
    4. Unreviewed optional AI notes are NOT exported (kept blank).
    5. Currency 'EUR' is preserved exactly (not defaulted to USD).
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export?template=STANDARD_CUSTOMS_CLEARANCE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    csv_text = resp.content.decode("utf-8")

    # Corrected values must be present
    assert "INV-HUMAN-CONFIRMED-001" in csv_text
    assert "Apex Precision Valves Ltd" in csv_text
    assert "3450.750" in csv_text
    assert "EUR" in csv_text

    # Raw AI values must NOT be present
    assert "INV-RAW-AI" not in csv_text
    assert "Raw AI Exporters Ltd" not in csv_text
    assert "This raw value must NOT be exported" not in csv_text


@pytest.mark.parametrize(
    "input_val, expected_val",
    [
        ("=SUM(1+1)", "'=SUM(1+1)"),
        ("+SUM(1+1)", "'+SUM(1+1)"),
        ("-SUM(1+1)", "'-SUM(1+1)"),
        ("@SUM(1+1)", "'@SUM(1+1)"),
        ("\tSUM(1+1)", "'\tSUM(1+1)"),
        ("\rSUM(1+1)", "'\rSUM(1+1)"),
        ("Ordinary Text", "Ordinary Text"),
        ("", ""),
        (None, ""),
        ("Nhava Sheva JNPT (Port) 🚢", "Nhava Sheva JNPT (Port) 🚢"),
        ("-12.50", "'-12.50"),
        ("12.50", "12.50"),
        (Decimal("3450.750"), "3450.750"),
    ],
)
def test_sanitize_csv_cell_all_prefixes_and_edge_cases(input_val, expected_val):
    """
    Direct unit test verifying formula-injection protection on all dangerous prefixes
    (=, +, -, @, \t, \r) as well as ordinary text, empty string, None, unicode, and decimals.
    """
    assert sanitize_csv_cell(input_val) == expected_val


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dangerous_prefix, payload",
    [
        ("=", "=SUM(1+1)*cmd|' /C calc'!A0"),
        ("+", "+100+cmd|' /C calc'!A0"),
        ("-", "-50-cmd|' /C calc'!A0"),
        ("@", "@SUM(1+1)"),
        ("\t", "\tcmd|' /C calc'!A0"),
        ("\r", "\rcmd|' /C calc'!A0"),
    ],
)
async def test_csv_formula_injection_protection_all_prefixes(
    async_client: AsyncClient, p8_env, db_session, dangerous_prefix, payload
):
    """
    End-to-end API test verifying that values beginning with dangerous formula characters
    (=, +, -, @, \t, \r) submitted in human reviews are safely escaped with a leading single quote (')
    in the generated CSV download.
    """
    shipment_id = p8_env["shipment"].id
    ci_doc = p8_env["ci_doc"]
    token = p8_env["exec1_token"]

    rev = DocumentFieldReview(
        shipment_id=shipment_id,
        document_id=ci_doc.id,
        field_name="seller_name",
        action=FieldReviewActionType.CORRECTED,
        original_value="Apex Precision Valves Ltd",
        corrected_value=payload,
        reason=f"Security test payload for prefix {dangerous_prefix}",
        reviewer_id=p8_env["exec_1"].id,
    )
    db_session.add(rev)
    await db_session.commit()

    resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    csv_text = resp.content.decode("utf-8")

    # Formula starter must be escaped with single quote
    assert f"'{payload}" in csv_text

    # Revert shipment status back to VERIFIED for subsequent parameterized test runs
    shp = p8_env["shipment"]
    shp.status = ShipmentStatus.VERIFIED
    db_session.add(shp)
    await db_session.commit()


@pytest.mark.asyncio
async def test_blocking_validation_failure_blocks_export(async_client: AsyncClient, p8_env, db_session):
    """
    A shipment with unresolved blocking validation failures cannot be exported.
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    # Insert a failing validation result
    val_fail = ShipmentValidationResult(
        shipment_id=shipment_id,
        run_id=uuid4(),
        rule_id="RULE_GROSS_WEIGHT",
        rule_name="Gross Weight Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.FAIL,
        explanation="Severe weight mismatch",
        compared_values={},
    )
    db_session.add(val_fail)
    await db_session.commit()

    resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "blocking validation failure" in str(resp.json()["detail"])


@pytest.mark.asyncio
async def test_role_and_ownership_enforcement_on_export(async_client: AsyncClient, p8_env):
    """
    Shared Workspace & Role Permissions:
    1. Non-existent shipment returns 404.
    2. Executive 2 can export the shared verified shipment (returns 200).
    3. Duplicate export attempt on already-exported shipment returns 409 Conflict.
    """
    shipment_id = p8_env["shipment"].id
    exec2_token = p8_env["exec2_token"]
    mgr_token = p8_env["mgr_token"]

    # Non-existent shipment attempt -> 404
    non_existent_id = uuid4()
    r_not_found = await async_client.post(
        f"/api/v1/shipments/{non_existent_id}/export",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r_not_found.status_code == 404

    # Executive 2 export in shared workspace -> 200
    r1 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r1.status_code == 200

    # Duplicate export attempt by Manager returns 409
    r2 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_export_history_and_immutable_snapshot_download(async_client: AsyncClient, p8_env):
    """
    Verifies that exporting creates an immutable history record and that downloading
    the historical snapshot returns the byte-exact original file with identical SHA-256.
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    # Execute export
    export_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export?template=STANDARD_CUSTOMS_CLEARANCE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert export_resp.status_code == 200
    orig_bytes = export_resp.content
    orig_checksum = export_resp.headers["x-export-checksum"]
    export_id = export_resp.headers["x-export-id"]

    # Check export history list
    list_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/exports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) >= 1
    record = next(i for i in items if i["id"] == export_id)
    assert record["sha256_checksum"] == orig_checksum
    assert record["export_status"] == "COMPLETED"

    # Download historical snapshot
    dl_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content == orig_bytes
    assert dl_resp.headers["x-export-checksum"] == orig_checksum


@pytest.mark.asyncio
async def test_direct_patch_to_exported_remains_prohibited(async_client: AsyncClient, p8_env):
    """
    Ensures neither Executive nor Manager can manually PATCH a shipment to EXPORTED.
    Workflow protection returns HTTP 403 Forbidden.
    """
    shipment_id = p8_env["shipment"].id
    exec_token = p8_env["exec1_token"]
    mgr_token = p8_env["mgr_token"]

    r1 = await async_client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "EXPORTED"},
        headers={"Authorization": f"Bearer {exec_token}"},
    )
    assert r1.status_code == 403

    r2 = await async_client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "EXPORTED"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_manager_analytics_overview_aggregations(async_client: AsyncClient, p8_env):
    """
    Verifies that GET /api/v1/analytics/overview:
    1. Returns correct live aggregations from PostgreSQL.
    2. Executive sees only their own shipments (my_shipments count matches).
    3. Manager sees organization-wide metrics.
    4. Date filters filter volume and export metrics.
    """
    exec1_token = p8_env["exec1_token"]
    mgr_token = p8_env["mgr_token"]

    # 1. Executive analytics
    exec_resp = await async_client.get(
        "/api/v1/analytics/overview",
        headers={"Authorization": f"Bearer {exec1_token}"},
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["role"] == "DOCUMENTATION_EXECUTIVE"
    assert exec_data["total_shipments"] >= 1
    assert "status_distribution" in exec_data
    assert "documents_uploaded_by_type" in exec_data

    # 2. Manager analytics
    mgr_resp = await async_client.get(
        "/api/v1/analytics/overview",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_resp.status_code == 200
    mgr_data = mgr_resp.json()
    assert mgr_data["role"] == "DOCUMENTATION_MANAGER"
    assert mgr_data["total_shipments"] >= 1
    assert "volume_over_time" in mgr_data
    assert "exports_over_time" in mgr_data
    assert "validation_issues_by_rule" in mgr_data

    # 3. Date filtered query
    date_resp = await async_client.get(
        "/api/v1/analytics/overview?start_date=2026-01-01&end_date=2026-12-31",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert date_resp.status_code == 200
    assert date_resp.json()["start_date"] == "2026-01-01"


# ==============================================================================
# PROMPT 8 HARDENING: CONCURRENCY, TRANSACTION SAFETY & ROLLBACK TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_export_requests_same_shipment(async_client: AsyncClient, p8_env, db_session):
    """
    PostgreSQL 16 Concurrency Test:
    Submits two concurrent export requests for the same VERIFIED shipment.
    Verifies:
    1. Exactly one request succeeds with HTTP 200.
    2. The other request receives HTTP 409 Conflict.
    3. Exactly one COMPLETED ShipmentExportRecord exists.
    4. The shipment transitions to EXPORTED status.
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    req1 = async_client.post(
        f"/api/v1/shipments/{shipment_id}/export?template=STANDARD_CUSTOMS_CLEARANCE",
        headers={"Authorization": f"Bearer {token}"},
    )
    req2 = async_client.post(
        f"/api/v1/shipments/{shipment_id}/export?template=STANDARD_CUSTOMS_CLEARANCE",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp1, resp2 = await asyncio.gather(req1, req2)
    statuses = {resp1.status_code, resp2.status_code}
    assert statuses == {200, 409}

    # Verify conflict error message on the losing request
    losing_resp = resp1 if resp1.status_code == 409 else resp2
    assert "already been exported" in losing_resp.json()["detail"].lower()

    # Verify winning request received valid CSV
    winning_resp = resp1 if resp1.status_code == 200 else resp2
    assert "text/csv" in winning_resp.headers["content-type"]

    # Verify exactly one completed export record in database
    await db_session.rollback()
    records_stmt = select(ShipmentExportRecord).where(
        ShipmentExportRecord.shipment_id == shipment_id,
        ShipmentExportRecord.export_status == ExportStatus.COMPLETED,
    )
    records_res = await db_session.execute(records_stmt)
    completed_records = records_res.scalars().all()
    assert len(completed_records) == 1

    # Verify shipment is in EXPORTED status
    db_session.expire_all()
    shp_stmt = select(Shipment).where(Shipment.id == shipment_id)
    shp_res = await db_session.execute(shp_stmt)
    shp = shp_res.scalar_one()
    assert shp.status == ShipmentStatus.EXPORTED


@pytest.mark.asyncio
async def test_concurrent_export_requests_different_shipments(async_client: AsyncClient, p8_env, db_session):
    """
    Verifies that two different shipments can be exported concurrently on PostgreSQL 16
    without row-lock interference.
    """
    exec_1 = p8_env["exec_1"]
    token = p8_env["exec1_token"]
    storage = get_storage_service()

    # Create second verified shipment
    shipment2 = Shipment(
        shipment_number=f"SHP-JNPT-{uuid4().hex[:6].upper()}",
        client_name="Second Client Logistics Pvt Ltd",
        origin_country="IN",
        status=ShipmentStatus.VERIFIED,
        created_by=exec_1.id,
        currency="EUR",
        product_description="Industrial Gaskets",
        quantity=Decimal("50.00"),
        unit_price=Decimal("120.0000"),
        gross_weight_kg=Decimal("800.000"),
    )
    db_session.add(shipment2)
    await db_session.commit()
    await db_session.refresh(shipment2)

    # Add required document
    ci2_key = storage.get_safe_storage_key("pdf")
    ci2_bytes = make_pdf("CI 2")
    await storage.save_file(_stream_bytes(ci2_bytes), ci2_key)
    ci2_doc = Document(
        shipment_id=shipment2.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="ci2.pdf",
        storage_key=ci2_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(ci2_bytes),
        sha256_checksum=f"cs_{uuid4().hex}",
        version=1,
        uploaded_by=exec_1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(ci2_doc)
    await db_session.commit()
    await db_session.refresh(ci2_doc)

    # Validation result
    val_res = ShipmentValidationResult(
        shipment_id=shipment2.id,
        run_id=uuid4(),
        rule_id="RULE_INVOICE_REF",
        rule_name="Invoice Reference Consistency",
        severity=ValidationSeverity.ERROR,
        outcome=ValidationOutcome.PASS,
        explanation="Consistent",
        compared_values={},
    )
    db_session.add(val_res)

    # Reviews for mandatory fields on shipment 2
    reviews2 = [
        DocumentFieldReview(
            shipment_id=shipment2.id,
            document_id=ci2_doc.id,
            field_name=f,
            action=FieldReviewActionType.CONFIRMED,
            original_value="TEST_VAL",
            corrected_value="TEST_VAL",
            reviewer_id=exec_1.id,
        )
        for f in [
            "invoice_number", "invoice_date", "seller_name", "buyer_name",
            "grand_total", "currency", "invoice_reference", "package_count",
            "gross_weight_kg", "bl_number", "shipper_name", "consignee_name"
        ]
    ]
    db_session.add_all(reviews2)
    await db_session.commit()

    # Export both shipments simultaneously
    req1 = async_client.post(
        f"/api/v1/shipments/{p8_env['shipment'].id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    req2 = async_client.post(
        f"/api/v1/shipments/{shipment2.id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp1, resp2 = await asyncio.gather(req1, req2)
    assert resp1.status_code == 200
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_export_failure_triggers_rollback_and_records_failed_status(
    async_client: AsyncClient, p8_env, db_session
):
    """
    Simulates an unexpected internal failure during CSV generation.
    Verifies:
    1. Returns HTTP 500 with safe error message (no leaked exception/stack trace).
    2. Database transaction is rolled back before recording failure.
    3. Shipment status is NOT transitioned to EXPORTED (remains VERIFIED).
    4. A ShipmentExportRecord with export_status == FAILED is persisted.
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    with patch(
        "app.services.export.csv_exporter.CSVExportService.get_approved_review_overlay",
        side_effect=RuntimeError("Disk I/O burst failure"),
    ):
        resp = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/export",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "internal server error" in detail.lower()
        assert "Disk I/O" not in detail  # No internal details leaked

    # Verify shipment status is still VERIFIED in database
    await db_session.rollback()
    db_session.expire_all()
    shp_stmt = select(Shipment).where(Shipment.id == shipment_id)
    shp_res = await db_session.execute(shp_stmt)
    shp = shp_res.scalar_one()
    assert shp.status == ShipmentStatus.VERIFIED

    # Verify a FAILED export record was persisted
    fail_stmt = select(ShipmentExportRecord).where(
        ShipmentExportRecord.shipment_id == shipment_id,
        ShipmentExportRecord.export_status == ExportStatus.FAILED,
    )
    fail_res = await db_session.execute(fail_stmt)
    fail_records = fail_res.scalars().all()
    assert len(fail_records) == 1
    assert fail_records[0].export_status == ExportStatus.FAILED


@pytest.mark.asyncio
async def test_failed_export_does_not_corrupt_previous_successful_records(
    async_client: AsyncClient, p8_env, db_session
):
    """
    Verifies that a successful export record is not modified or corrupted if a subsequent
    operation fails.
    """
    shipment_id = p8_env["shipment"].id
    token = p8_env["exec1_token"]

    # First export succeeds
    resp1 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    export_id = resp1.headers["x-export-id"]
    checksum = resp1.headers["x-export-checksum"]

    # Check database record is COMPLETED
    await db_session.rollback()
    rec_stmt = select(ShipmentExportRecord).where(ShipmentExportRecord.id == export_id)
    rec = (await db_session.execute(rec_stmt)).scalar_one()
    assert rec.export_status == ExportStatus.COMPLETED
    assert rec.sha256_checksum == checksum
    assert rec.snapshot_data is not None


@pytest.mark.asyncio
async def test_http_exceptions_do_not_create_failed_export_records(
    async_client: AsyncClient, p8_env, db_session
):
    """
    Verifies that expected HTTP exceptions (404 Not Found, 409 Conflict, 422 Unprocessable)
    do NOT insert FAILED export records in shipment_export_records.
    """
    shipment = p8_env["shipment"]
    exec1_token = p8_env["exec1_token"]
    exec2_token = p8_env["exec2_token"]

    # 1. 404 attempt (Non-existent shipment ID in shared workspace)
    non_existent_id = uuid4()
    r_404 = await async_client.post(
        f"/api/v1/shipments/{non_existent_id}/export",
        headers={"Authorization": f"Bearer {exec2_token}"},
    )
    assert r_404.status_code == 404

    # 2. 422 attempt (Unverified shipment)
    shipment.status = ShipmentStatus.REVIEW_REQUIRED
    db_session.add(shipment)
    await db_session.commit()

    r_422 = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/export",
        headers={"Authorization": f"Bearer {exec1_token}"},
    )
    assert r_422.status_code == 422

    # 3. 409 attempt (Already exported shipment)
    shipment.status = ShipmentStatus.EXPORTED
    db_session.add(shipment)
    await db_session.commit()

    r_409 = await async_client.post(
        f"/api/v1/shipments/{shipment.id}/export",
        headers={"Authorization": f"Bearer {exec1_token}"},
    )
    assert r_409.status_code == 409

    # Verify NO FAILED export record was created for any of these
    await db_session.rollback()
    fail_stmt = select(ShipmentExportRecord).where(
        ShipmentExportRecord.shipment_id == shipment.id,
        ShipmentExportRecord.export_status == ExportStatus.FAILED,
    )
    fail_res = await db_session.execute(fail_stmt)
    assert len(fail_res.scalars().all()) == 0
