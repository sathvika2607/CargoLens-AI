import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.models.field_review import (
    DocumentFieldReview,
    FieldReviewActionType,
    ReviewProvenance,
)
from app.models.export import ShipmentExportRecord, ExportStatus
from app.schemas.field_review import FieldReviewResponse
from app.security import hash_password, create_access_token


@pytest.fixture
async def provenance_test_env(db_session):
    """Sets up an executive user, manager user, shipment, document, and extraction for provenance testing."""
    exec_user = User(
        full_name="P10 Executive Officer",
        email=f"exec.prov.{uuid.uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("DemoExecutive2026!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr_user = User(
        full_name="P10 Manager Officer",
        email=f"mgr.prov.{uuid.uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("DemoManager2026!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec_user, mgr_user])
    await db_session.commit()
    await db_session.refresh(exec_user)
    await db_session.refresh(mgr_user)

    shipment = Shipment(
        shipment_number=f"SHP-PROV-{uuid.uuid4().hex[:6].upper()}",
        client_name="Navi Mumbai Precision Importers",
        origin_country="Germany",
        status=ShipmentStatus.PROCESSING,
        created_by=exec_user.id,
        is_demo=False,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="commercial_invoice.pdf",
        storage_key=f"mock/storage/ci_{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256_checksum="a" * 64,
        uploaded_by=exec_user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    ext = StructuredExtraction(
        document_id=doc.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="claude-vision",
        model="claude-3-5-sonnet",
        extraction_mode="VISION",
        total_page_count=1,
        extracted_data={
            "invoice_number": {"value": "INV-PROV-100", "confidence": 0.98},
            "gross_weight_kg": {"value": "2400.00", "confidence": 0.95},
        },
    )
    db_session.add(ext)
    await db_session.commit()
    await db_session.refresh(ext)

    return {
        "exec_user": exec_user,
        "mgr_user": mgr_user,
        "exec_token": create_access_token(user_id=exec_user.id, role=exec_user.role.value, email=exec_user.email),
        "mgr_token": create_access_token(user_id=mgr_user.id, role=mgr_user.role.value, email=mgr_user.email),
        "shipment": shipment,
        "doc": doc,
        "extraction": ext,
    }


@pytest.mark.asyncio
async def test_review_provenance_model_defaults(db_session, provenance_test_env):
    """Verifies that DocumentFieldReview defaults provenance to USER_ACTION and allows DEMO_SEED."""
    env = provenance_test_env

    # 1. Default review (unspecified provenance) -> USER_ACTION
    default_review = DocumentFieldReview(
        shipment_id=env["shipment"].id,
        document_id=env["doc"].id,
        extraction_id=env["extraction"].id,
        field_name="invoice_number",
        action=FieldReviewActionType.CONFIRMED,
        original_value="INV-PROV-100",
        reviewer_id=env["exec_user"].id,
    )
    db_session.add(default_review)
    await db_session.commit()
    await db_session.refresh(default_review)

    assert default_review.provenance == ReviewProvenance.USER_ACTION

    # 2. Explicit DEMO_SEED review
    demo_review = DocumentFieldReview(
        shipment_id=env["shipment"].id,
        document_id=env["doc"].id,
        extraction_id=env["extraction"].id,
        field_name="gross_weight_kg",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.DEMO_SEED,
        original_value="2400.00",
        reviewer_id=env["mgr_user"].id,
    )
    db_session.add(demo_review)
    await db_session.commit()
    await db_session.refresh(demo_review)

    assert demo_review.provenance == ReviewProvenance.DEMO_SEED


@pytest.mark.asyncio
async def test_create_field_review_api_enforces_user_action_provenance(async_client: AsyncClient, provenance_test_env):
    """Verifies that reviews created through the application API are tagged as USER_ACTION."""
    env = provenance_test_env
    headers = {"Authorization": f"Bearer {env['exec_token']}"}

    payload = {
        "field_name": "invoice_number",
        "action": "CONFIRMED",
    }
    url = f"/api/v1/shipments/{env['shipment'].id}/documents/{env['doc'].id}/reviews"
    resp = await async_client.post(url, json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["field_name"] == "invoice_number"
    assert data["action"] == "CONFIRMED"
    assert data["provenance"] == "USER_ACTION"
    assert data["reviewer_id"] == str(env["exec_user"].id)


@pytest.mark.asyncio
async def test_list_document_reviews_exposes_provenance(async_client: AsyncClient, db_session, provenance_test_env):
    """Verifies that GET /shipments/{id}/documents/{doc_id}/reviews returns provenance for each record."""
    env = provenance_test_env
    headers = {"Authorization": f"Bearer {env['exec_token']}"}

    # Insert one USER_ACTION and one DEMO_SEED
    r1 = DocumentFieldReview(
        shipment_id=env["shipment"].id,
        document_id=env["doc"].id,
        extraction_id=env["extraction"].id,
        field_name="invoice_number",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.USER_ACTION,
        original_value="INV-PROV-100",
        reviewer_id=env["exec_user"].id,
    )
    r2 = DocumentFieldReview(
        shipment_id=env["shipment"].id,
        document_id=env["doc"].id,
        extraction_id=env["extraction"].id,
        field_name="gross_weight_kg",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.DEMO_SEED,
        original_value="2400.00",
        reviewer_id=env["mgr_user"].id,
    )
    db_session.add_all([r1, r2])
    await db_session.commit()

    url = f"/api/v1/shipments/{env['shipment'].id}/documents/{env['doc'].id}/reviews"
    resp = await async_client.get(url, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2

    prov_map = {item["field_name"]: item["provenance"] for item in items}
    assert prov_map["invoice_number"] == "USER_ACTION"
    assert prov_map["gross_weight_kg"] == "DEMO_SEED"


@pytest.mark.asyncio
async def test_shipment_review_history_exposes_provenance(async_client: AsyncClient, db_session, provenance_test_env):
    """Verifies that GET /shipments/{id}/review-history exposes provenance."""
    env = provenance_test_env
    headers = {"Authorization": f"Bearer {env['mgr_token']}"}

    demo_rev = DocumentFieldReview(
        shipment_id=env["shipment"].id,
        document_id=env["doc"].id,
        extraction_id=env["extraction"].id,
        field_name="gross_weight_kg",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.DEMO_SEED,
        original_value="2400.00",
        reviewer_id=env["mgr_user"].id,
    )
    db_session.add(demo_rev)
    await db_session.commit()

    url = f"/api/v1/shipments/{env['shipment'].id}/review-history"
    resp = await async_client.get(url, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    demo_item = next(i for i in items if i["field_name"] == "gross_weight_kg")
    assert demo_item["provenance"] == "DEMO_SEED"


@pytest.mark.asyncio
async def test_global_audit_history_exposes_provenance(async_client: AsyncClient, db_session, provenance_test_env):
    """Verifies that GET /review/audit-history returns provenance for each review."""
    env = provenance_test_env
    headers = {"Authorization": f"Bearer {env['mgr_token']}"}

    r_seed = DocumentFieldReview(
        shipment_id=env["shipment"].id,
        document_id=env["doc"].id,
        extraction_id=env["extraction"].id,
        field_name="invoice_number",
        action=FieldReviewActionType.CONFIRMED,
        provenance=ReviewProvenance.DEMO_SEED,
        original_value="INV-PROV-100",
        reviewer_id=env["mgr_user"].id,
    )
    db_session.add(r_seed)
    await db_session.commit()

    url = "/api/v1/review/audit-history"
    resp = await async_client.get(url, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["provenance"] == "DEMO_SEED" for i in items)


@pytest.mark.asyncio
async def test_human_approval_gate_unauthorized_user_cannot_bypass(async_client: AsyncClient, provenance_test_env):
    """Verifies that unauthenticated or unauthorized users cannot record reviews or bypass gates."""
    env = provenance_test_env
    url = f"/api/v1/shipments/{env['shipment'].id}/documents/{env['doc'].id}/reviews"

    # No token -> 401
    resp = await async_client.post(url, json={"field_name": "invoice_number", "action": "CONFIRMED"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_client_cannot_tamper_review_provenance(async_client: AsyncClient, provenance_test_env):
    """Verifies that client cannot forge DEMO_SEED provenance via the review creation API."""
    env = provenance_test_env
    headers = {"Authorization": f"Bearer {env['exec_token']}"}

    # Attempt to forge DEMO_SEED in body
    payload = {
        "field_name": "invoice_number",
        "action": "CONFIRMED",
        "provenance": "DEMO_SEED",
    }
    url = f"/api/v1/shipments/{env['shipment'].id}/documents/{env['doc'].id}/reviews"
    resp = await async_client.post(url, json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    # Must be forced to USER_ACTION
    assert data["provenance"] == "USER_ACTION"


@pytest.mark.asyncio
async def test_seeded_simulation_reviews_marked_as_demo_seed(db_session, provenance_test_env):
    """Verifies that seeded demonstration reviews are marked as DEMO_SEED and maintain their status."""
    env = provenance_test_env

    # Create synthetic demonstration review fixture
    demo_reviews = [
        DocumentFieldReview(
            shipment_id=env["shipment"].id,
            document_id=env["doc"].id,
            extraction_id=env["extraction"].id,
            field_name="invoice_number",
            action=FieldReviewActionType.CONFIRMED,
            provenance=ReviewProvenance.DEMO_SEED,
            original_value="INV-SIE-2026-104",
            reviewer_id=env["mgr_user"].id,
        ),
        DocumentFieldReview(
            shipment_id=env["shipment"].id,
            document_id=env["doc"].id,
            extraction_id=env["extraction"].id,
            field_name="gross_weight_kg",
            action=FieldReviewActionType.CONFIRMED,
            provenance=ReviewProvenance.DEMO_SEED,
            original_value="1120.00",
            reviewer_id=env["mgr_user"].id,
        ),
    ]
    db_session.add_all(demo_reviews)
    await db_session.commit()

    # Query back
    stmt = select(DocumentFieldReview).where(
        DocumentFieldReview.shipment_id == env["shipment"].id,
        DocumentFieldReview.provenance == ReviewProvenance.DEMO_SEED,
    )
    res = await db_session.execute(stmt)
    records = res.scalars().all()
    assert len(records) == 2
    for r in records:
        assert r.provenance == ReviewProvenance.DEMO_SEED
