import asyncio
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

import pymupdf
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import (
    DocumentExtraction,
    DocumentExtractionPage,
    ExtractionStatus,
    PageExtractionMethod,
)
from app.services.ai.base import RawProviderResult, ProviderAPIError, ExtractionProviderError
from app.services.ai.service import StructuredExtractionService
from app.security import hash_password
from app.storage import get_storage_service


def make_multipage_pdf(page_count: int, prefix: str = "Page") -> bytes:
    """Creates a valid multi-page PDF with pymupdf."""
    doc = pymupdf.open()
    for i in range(1, page_count + 1):
        p = doc.new_page(width=595, height=842)
        p.insert_text((50, 72), f"{prefix} {i}: Content for customs extraction testing", fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


async def _to_stream(data: bytes):
    yield data


@pytest.fixture
async def batch_test_env(db_session):
    """Sets up a user, shipment, and storage for batch extraction testing."""
    user = User(
        full_name="Batch Test Executive",
        email=f"batch.{uuid4().hex[:6]}@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    shipment = Shipment(
        shipment_number=f"SHP-BATCH-{uuid4().hex[:6].upper()}",
        client_name="Batch Logistics Ltd",
        origin_country="IN",
        status=ShipmentStatus.CREATED,
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    return {
        "user": user,
        "shipment": shipment,
    }


@pytest.mark.asyncio
async def test_extraction_multipage_exceeding_five_pages_batches_correctly(db_session, batch_test_env):
    """
    Verifies that documents longer than 5 pages:
    1. Are split into bounded batches (e.g. 7 pages -> batch of 5, batch of 2).
    2. Results are merged without losing provenance or line items.
    3. total_page_count and processed_page_count are both 7.
    4. Status is COMPLETED.
    """
    user = batch_test_env["user"]
    shipment = batch_test_env["shipment"]

    # 1. Create a 7-page PDF
    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_multipage_pdf(7, prefix="Invoice Multi")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="multipage_invoice_7p.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum=f"checksum_7p_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # 2. Mock provider responses for 2 batches
    batch1_result = RawProviderResult(
        data={
            "invoice_number": {
                "value": "INV-7P-BATCH",
                "confidence": 0.98,
                "source_page_number": 1,
                "evidence_text": "Invoice Number: INV-7P-BATCH",
            },
            "currency": {
                "value": "USD",
                "confidence": 0.99,
                "source_page_number": 1,
            },
            "line_items": [
                {
                    "description": {"value": "Item 1 from page 2", "confidence": 0.95, "source_page_number": 2},
                    "line_total": {"value": "500.00", "confidence": 0.95, "source_page_number": 2},
                },
                {
                    "description": {"value": "Item 2 from page 4", "confidence": 0.95, "source_page_number": 4},
                    "line_total": {"value": "1500.00", "confidence": 0.95, "source_page_number": 4},
                },
            ],
        },
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        token_usage={"input_tokens": 1200, "output_tokens": 300},
        latency_seconds=1.5,
    )

    batch2_result = RawProviderResult(
        data={
            "grand_total": {
                "value": "2000.00",
                "confidence": 0.97,
                "source_page_number": 7,
                "evidence_text": "Grand Total: USD 2000.00",
            },
            "line_items": [
                {
                    "description": {"value": "Item 3 from page 6", "confidence": 0.92, "source_page_number": 6},
                    "line_total": {"value": "0.00", "confidence": 0.92, "source_page_number": 6},
                },
            ],
        },
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        token_usage={"input_tokens": 600, "output_tokens": 150},
        latency_seconds=0.8,
    )

    with patch(
        "app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch",
        side_effect=[batch1_result, batch2_result],
    ) as mock_batch:
        service = StructuredExtractionService()
        extraction = await service.execute_extraction(session=db_session, document=doc)

        # Provider must have been called exactly twice
        assert mock_batch.call_count == 2
        batch1_pages = mock_batch.call_args_list[0][1]["pages"]
        batch2_pages = mock_batch.call_args_list[1][1]["pages"]
        assert len(batch1_pages) == 5
        assert [p.page_number for p in batch1_pages] == [1, 2, 3, 4, 5]
        assert len(batch2_pages) == 2
        assert [p.page_number for p in batch2_pages] == [6, 7]

        # Verify database record
        assert extraction.status == ExtractionStatus.COMPLETED
        assert extraction.total_page_count == 7
        assert extraction.processed_page_count == 7
        assert extraction.error_summary is None

        # Verify data merged across batches
        ext_data = extraction.extracted_data
        assert ext_data["invoice_number"]["value"] == "INV-7P-BATCH"
        assert ext_data["grand_total"]["value"] == "2000.00"
        assert len(ext_data["line_items"]) == 3
        assert ext_data["line_items"][0]["description"]["source_page_number"] == 2
        assert ext_data["line_items"][2]["description"]["source_page_number"] == 6


@pytest.mark.asyncio
async def test_extraction_partial_failure_marks_status_partial_never_completed(db_session, batch_test_env):
    """
    Verifies that when a document exceeds 5 pages and a subsequent batch fails:
    1. Status is marked PARTIAL (never COMPLETED).
    2. processed_page_count reflects pages processed (e.g. 5 of 8).
    3. total_page_count is 8.
    4. Error summary explains the partial failure.
    5. Partial extraction data from batch 1 is preserved and validated.
    """
    user = batch_test_env["user"]
    shipment = batch_test_env["shipment"]

    # 1. Create an 8-page PDF
    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_multipage_pdf(8, prefix="Packing Multi")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.PACKING_LIST,
        original_filename="multipage_packing_8p.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum=f"checksum_8p_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # 2. Mock batch 1 success, batch 2 failure
    batch1_result = RawProviderResult(
        data={
            "invoice_reference": {
                "value": "INV-REF-8P",
                "confidence": 0.95,
                "source_page_number": 1,
            },
            "gross_weight_kg": {
                "value": "12500.00",
                "confidence": 0.94,
                "source_page_number": 3,
            },
        },
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
        token_usage={"input_tokens": 1500, "output_tokens": 250},
        latency_seconds=1.8,
    )

    with patch(
        "app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch",
        side_effect=[batch1_result, ProviderAPIError("Anthropic upstream connection timeout on batch 2")],
    ):
        service = StructuredExtractionService()
        extraction = await service.execute_extraction(session=db_session, document=doc)

        # STRICT ASSERTION: Never marked COMPLETED
        assert extraction.status == ExtractionStatus.PARTIAL
        assert extraction.status != ExtractionStatus.COMPLETED
        assert extraction.total_page_count == 8
        assert extraction.processed_page_count == 5
        assert extraction.error_summary is not None
        assert "5 of 8 pages processed" in extraction.error_summary
        assert "Anthropic upstream connection timeout on batch 2" in extraction.error_summary

        # Check preserved partial extracted data
        ext_data = extraction.extracted_data
        assert ext_data["invoice_reference"]["value"] == "INV-REF-8P"
        assert ext_data["gross_weight_kg"]["value"] == "12500.00"


@pytest.mark.asyncio
async def test_extraction_first_batch_failure_marks_status_failed(db_session, batch_test_env):
    """
    Verifies that if the first batch fails completely:
    1. ExtractionProviderError is raised.
    2. Extraction record is marked FAILED (not PARTIAL, not COMPLETED).
    3. processed_page_count is 0.
    """
    user = batch_test_env["user"]
    shipment = batch_test_env["shipment"]

    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_multipage_pdf(6, prefix="BL Multi")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.BILL_OF_LADING,
        original_filename="multipage_bl_6p.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum=f"checksum_6p_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    with patch(
        "app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch",
        side_effect=ProviderAPIError("Immediate Anthropic network unreachable"),
    ):
        service = StructuredExtractionService()
        extraction = await service.execute_extraction(session=db_session, document=doc)

        assert extraction.status == ExtractionStatus.FAILED
        assert extraction.status != ExtractionStatus.PARTIAL
        assert extraction.status != ExtractionStatus.COMPLETED
        assert extraction.processed_page_count == 0
        assert extraction.total_page_count == 6
        assert "Immediate Anthropic network unreachable" in extraction.error_summary


@pytest.mark.asyncio
async def test_mixed_digital_and_scanned_pdf_pages_from_ocr_page_records(db_session, batch_test_env):
    """
    Verifies that when Prompt 5 DocumentExtractionPage records exist:
    - Pages classified as DIGITAL_TEXT are assigned is_digital_text=True with digital text.
    - Pages classified as SCANNED_IMAGE are assigned is_digital_text=False with rendered image bytes.
    - No scanned page is skipped.
    """
    user = batch_test_env["user"]
    shipment = batch_test_env["shipment"]

    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_multipage_pdf(2, prefix="HybridDoc")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="hybrid_doc_2p.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum=f"checksum_hybrid_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.COMPLETED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Add Prompt 5 OCR extraction records:
    # Page 1: DIGITAL_TEXT
    # Page 2: SCANNED_IMAGE
    doc_ocr = DocumentExtraction(
        document_id=doc.id,
        status=ExtractionStatus.COMPLETED,
        raw_text="Extracted text full document",
        avg_confidence=0.92,
        page_count=2,
    )
    db_session.add(doc_ocr)
    await db_session.commit()
    await db_session.refresh(doc_ocr)

    page1_ocr = DocumentExtractionPage(
        extraction_id=doc_ocr.id,
        page_number=1,
        raw_text="Digital text for page 1 that easily exceeds thirty characters in length.",
        ocr_confidence=0.98,
        extraction_method=PageExtractionMethod.DIGITAL_TEXT,
    )
    page2_ocr = DocumentExtractionPage(
        extraction_id=doc_ocr.id,
        page_number=2,
        raw_text="",
        ocr_confidence=0.75,
        extraction_method=PageExtractionMethod.OCR,
    )
    db_session.add_all([page1_ocr, page2_ocr])
    await db_session.commit()

    mock_result = RawProviderResult(
        data={"invoice_number": {"value": "INV-HYB-1", "confidence": 0.95}},
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="HYBRID",
    )

    with patch(
        "app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch",
        new=AsyncMock(return_value=mock_result),
    ) as mock_call:
        service = StructuredExtractionService()
        extraction = await service.execute_extraction(session=db_session, document=doc)

        assert mock_call.call_count == 1
        pages_input = mock_call.call_args[1]["pages"]
        assert len(pages_input) == 2

        # Page 1 must be DIGITAL_TEXT
        assert pages_input[0].page_number == 1
        assert pages_input[0].is_digital_text is True
        assert "Digital text for page 1" in pages_input[0].text_content

        # Page 2 must be SCANNED_IMAGE with rendered image bytes, NOT skipped
        assert pages_input[1].page_number == 2
        assert pages_input[1].is_digital_text is False
        assert pages_input[1].image_bytes is not None
        assert len(pages_input[1].image_bytes) > 0

        assert extraction.status == ExtractionStatus.COMPLETED
