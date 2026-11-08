import io
from uuid import uuid4
from decimal import Decimal
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

import pymupdf
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.models.validation import ValidationOutcome
from app.security import hash_password, create_access_token
from app.services.ai.base import RawProviderResult
from app.storage import get_storage_service


def make_valid_pdf(text: str = "Sample Customs Document") -> bytes:
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 72), text, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


async def _to_stream(data: bytes):
    yield data


@pytest.fixture
async def api_env(db_session):
    """Sets up Executive 1, Executive 2, Manager, and a shipment with a Commercial Invoice."""
    exec1 = User(
        full_name="Executive One",
        email="exec1@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    exec2 = User(
        full_name="Executive Two",
        email="exec2@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr = User(
        full_name="Manager",
        email="mgr@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec1, exec2, mgr])
    await db_session.commit()
    await db_session.refresh(exec1)
    await db_session.refresh(exec2)
    await db_session.refresh(mgr)

    # Executive 1 owns shipment 1
    shipment1 = Shipment(
        shipment_number="SHP-2026-001",
        client_name="Acme Imports",
        origin_country="AE",
        status=ShipmentStatus.CREATED,
        created_by=exec1.id,
    )
    db_session.add(shipment1)
    await db_session.commit()
    await db_session.refresh(shipment1)

    # Save document in storage
    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_valid_pdf("Commercial Invoice Content")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc1 = Document(
        shipment_id=shipment1.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="commercial_invoice.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum="dummy_checksum_12345",
        version=1,
        uploaded_by=exec1.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(doc1)
    await db_session.commit()
    await db_session.refresh(doc1)

    return {
        "exec1": exec1,
        "exec2": exec2,
        "mgr": mgr,
        "token_exec1": create_access_token(exec1.id, exec1.role.value, exec1.email),
        "token_exec2": create_access_token(exec2.id, exec2.role.value, exec2.email),
        "token_mgr": create_access_token(mgr.id, mgr.role.value, mgr.email),
        "shipment1": shipment1,
        "doc1": doc1,
    }


@pytest.mark.asyncio
async def test_trigger_and_retrieve_structured_extraction(async_client: AsyncClient, api_env):
    """Verifies triggering structured extraction with mocked Claude and retrieving latest result."""
    shipment_id = api_env["shipment1"].id
    doc_id = api_env["doc1"].id
    token = api_env["token_exec1"]

    mock_raw_result = RawProviderResult(
        data={
            "invoice_number": {
                "value": "INV-2026-881",
                "confidence": 0.98,
                "evidence_text": "INVOICE NUMBER: INV-2026-881",
                "source_page_number": 1,
            },
            "currency": {"value": "USD", "confidence": 0.99},
            "grand_total": {"value": "25000.00", "confidence": 0.96},
            "gross_weight_kg": {"value": "5000.00", "confidence": 0.92},
        },
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        token_usage={"input_tokens": 400, "output_tokens": 120},
        latency_seconds=1.25,
    )

    with patch("app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch", new=AsyncMock(return_value=mock_raw_result)):
        # 1. Trigger extraction
        resp = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["document_type"] == "COMMERCIAL_INVOICE"
        assert data["attempt_number"] == 1
        assert data["extracted_data"]["invoice_number"]["value"] == "INV-2026-881"
        assert data["field_confidence_summary"]["average_confidence"] is not None

        # 2. Retrieve latest extraction
        get_resp = await async_client.get(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["id"] == data["id"]
        assert get_data["extracted_data"]["grand_total"]["value"] == "25000.00"


@pytest.mark.asyncio
async def test_executive_shared_workspace_access_on_structured_api(async_client: AsyncClient, api_env):
    """Verifies that an executive can access structured extractions on shared workspace shipments, while unauth is 401."""
    shipment_id = api_env["shipment1"].id
    doc_id = api_env["doc1"].id
    token_exec2 = api_env["token_exec2"]
    token_mgr = api_env["token_mgr"]

    # Unauthenticated -> 401
    unauth_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction"
    )
    assert unauth_resp.status_code == 401

    # Executive 2 accesses extraction in shared workspace -> permitted (404 only because not run yet, not unowned)
    resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert resp.status_code == 404
    assert "No structured extraction found" in resp.json()["detail"]

    # Manager attempts to get extraction -> works (returns 404 only if extraction hasn't run yet)
    mgr_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert mgr_resp.status_code == 404
    assert "No structured extraction found" in mgr_resp.json()["detail"]


@pytest.mark.asyncio
async def test_extraction_history_preservation(async_client: AsyncClient, api_env):
    """Verifies that re-running extractions creates new sequential attempts and preserves history."""
    shipment_id = api_env["shipment1"].id
    doc_id = api_env["doc1"].id
    token = api_env["token_exec1"]

    mock_result_1 = RawProviderResult(
        data={"invoice_number": {"value": "INV-100", "confidence": 0.90}},
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
    )
    mock_result_2 = RawProviderResult(
        data={"invoice_number": {"value": "INV-100-AMENDED", "confidence": 0.95}},
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
    )

    with patch("app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch", side_effect=[mock_result_1, mock_result_2]):
        # Run attempt 1
        r1 = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200
        assert r1.json()["attempt_number"] == 1

        # Run attempt 2
        r2 = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["attempt_number"] == 2

        # Verify history endpoint contains both attempts
        hist_resp = await async_client.get(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["total_attempts"] == 2
        attempts = [item["attempt_number"] for item in hist_data["history"]]
        assert attempts == [2, 1]


@pytest.mark.asyncio
async def test_get_field_evidence_endpoint(async_client: AsyncClient, api_env):
    """Verifies retrieving field-level evidence and provenance."""
    shipment_id = api_env["shipment1"].id
    doc_id = api_env["doc1"].id
    token = api_env["token_exec1"]

    mock_raw_result = RawProviderResult(
        data={
            "invoice_number": {
                "value": "INV-EVID-007",
                "normalized_value": "INV-EVID-007",
                "confidence": 0.98,
                "evidence_text": "Commercial Invoice Reference: INV-EVID-007",
                "source_page_number": 1,
            }
        },
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
    )

    with patch("app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch", new=AsyncMock(return_value=mock_raw_result)):
        post_resp = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction",
            headers={"Authorization": f"Bearer {token}"},
        )
        extraction_id = post_resp.json()["id"]

        # Fetch field evidence
        evid_resp = await async_client.get(
            f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/structured-extraction/{extraction_id}/fields/invoice_number/evidence",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert evid_resp.status_code == 200
        evid_data = evid_resp.json()
        assert evid_data["field_name"] == "invoice_number"
        assert evid_data["value"] == "INV-EVID-007"
        assert evid_data["evidence_text"] == "Commercial Invoice Reference: INV-EVID-007"
        assert evid_data["source_page_number"] == 1
        assert evid_data["confidence"] == 0.98


@pytest.mark.asyncio
async def test_validation_api_run_and_retrieve_shp_24811(async_client: AsyncClient, api_env, db_session):
    """
    Verifies running validations via API and detecting SHP-24811's 45 kg discrepancy:
    - Commercial Invoice gross weight: 3,120 kg
    - Packing list gross weight: 3,165 kg
    - Validator reports 45 kg discrepancy
    """
    shipment_id = api_env["shipment1"].id
    exec1_id = api_env["exec1"].id
    token = api_env["token_exec1"]

    # 1. Create Packing List document in same shipment
    storage = get_storage_service()
    pkg_key = storage.get_safe_storage_key("pdf")
    pkg_bytes = make_valid_pdf("Packing List Content")
    await storage.save_file(_to_stream(pkg_bytes), pkg_key)

    pkg_doc = Document(
        shipment_id=shipment_id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="packing_list.pdf",
        storage_key=pkg_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pkg_bytes),
        sha256_checksum="dummy_checksum_packing_1",
        version=1,
        uploaded_by=exec1_id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(pkg_doc)
    await db_session.commit()
    await db_session.refresh(pkg_doc)

    # 2. Add structured extractions directly for SHP-24811
    # Commercial Invoice: 3,120 kg
    inv_ext = StructuredExtraction(
        document_id=api_env["doc1"].id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        extracted_data={
            "invoice_number": {"value": "INV-24811", "confidence": 0.99},
            "gross_weight_kg": {"value": "3120.00", "confidence": 0.95},
            "currency": {"value": "USD", "confidence": 0.98},
        },
    )
    # Packing List: 3,165 kg
    pkg_ext = StructuredExtraction(
        document_id=pkg_doc.id,
        document_type=DocumentType.PACKING_LIST,
        attempt_number=1,
        status=ExtractionStatus.COMPLETED,
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        extracted_data={
            "invoice_reference": {"value": "INV-24811", "confidence": 0.98},
            "gross_weight_kg": {"value": "3165.00", "confidence": 0.95},
        },
    )
    db_session.add_all([inv_ext, pkg_ext])
    await db_session.commit()

    # 3. Run validation through API
    val_run_resp = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/validations/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert val_run_resp.status_code == 200
    val_data = val_run_resp.json()
    assert val_data["total_rules"] == 11
    assert val_data["failed_count"] >= 1
    assert val_data["has_blocking_failures"] is True

    # Find gross weight rule result
    gross_rule = next(r for r in val_data["results"] if r["rule_id"] == "RULE_GROSS_WEIGHT_CONSISTENCY")
    assert gross_rule["outcome"] == "FAIL"
    assert "45.00 kg" in gross_rule["explanation"]

    # 4. Retrieve validations via GET
    get_val_resp = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/validations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_val_resp.status_code == 200
    assert get_val_resp.json()["run_id"] == val_data["run_id"]
