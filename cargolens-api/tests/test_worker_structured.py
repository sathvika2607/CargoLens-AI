import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, update

import pymupdf
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.services.job_worker import JobWorkerService, JobLeaseLostError
from app.services.ai.base import RawProviderResult
from app.services.ai.service import StructuredExtractionService
from app.security import hash_password
from app.storage import get_storage_service


def make_valid_pdf(text: str = "Worker Test Document") -> bytes:
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 72), text, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


async def _to_stream(data: bytes):
    yield data


@pytest.fixture
async def worker_test_env(db_session):
    """Sets up a user, shipment, document, and pending STRUCTURED_EXTRACTION job."""
    user = User(
        full_name="Worker Executive",
        email="worker.exec@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    shipment = Shipment(
        shipment_number="SHP-WORKER-01",
        client_name="Worker Logistics",
        origin_country="IN",
        status=ShipmentStatus.CREATED,
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    storage = get_storage_service()
    doc_key = storage.get_safe_storage_key("pdf")
    pdf_bytes = make_valid_pdf("Worker Invoice Sample")
    await storage.save_file(_to_stream(pdf_bytes), doc_key)

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="invoice_worker.pdf",
        storage_key=doc_key,
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum="worker_checksum_123",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.PENDING,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    job = ProcessingJob(
        document_id=doc.id,
        job_type="STRUCTURED_EXTRACTION",
        status=JobStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    return {
        "user": user,
        "shipment": shipment,
        "doc": doc,
        "job": job,
    }


@pytest.mark.asyncio
async def test_worker_processes_structured_extraction_job(db_session, worker_test_env):
    """Verifies that the worker successfully claims and processes a STRUCTURED_EXTRACTION job."""
    job_id = worker_test_env["job"].id
    doc_id = worker_test_env["doc"].id

    mock_raw_result = RawProviderResult(
        data={
            "invoice_number": {"value": "INV-WORKER-1", "confidence": 0.98},
            "currency": {"value": "USD", "confidence": 0.99},
            "grand_total": {"value": "10000.00", "confidence": 0.95},
        },
        provider="anthropic",
        model="claude-sonnet-5-5",
        extraction_mode="TEXT_FIRST",
    )

    with patch("app.services.ai.service.ClaudeVisionExtractionProvider.extract_pages_batch", new=AsyncMock(return_value=mock_raw_result)):
        processed_job = await JobWorkerService.process_single_job(
            session=db_session,
        )

        assert processed_job is not None
        assert processed_job.id == job_id
        assert processed_job.status == JobStatus.COMPLETED
        assert processed_job.lease_token is None

        # Verify structured extraction row was persisted
        ext_res = await db_session.execute(
            select(StructuredExtraction).where(StructuredExtraction.document_id == doc_id)
        )
        ext = ext_res.scalar_one_or_none()
        assert ext is not None
        assert ext.status == ExtractionStatus.COMPLETED
        assert ext.extracted_data["invoice_number"]["value"] == "INV-WORKER-1"


@pytest.mark.asyncio
async def test_worker_fencing_protects_reclaimed_structured_job(db_session, worker_test_env):
    """
    Verifies that if a worker's lease expires and another worker reclaims the job,
    the old worker's completion is aborted and discarded with JobLeaseLostError.
    """
    job = await JobWorkerService.claim_next_job(db_session, lease_duration_seconds=1)
    assert job is not None
    original_token = job.lease_token

    # Simulate another worker reclaiming the job after expiration
    job.lease_token = uuid4()
    job.attempt_count = 2
    await db_session.commit()

    # Old worker tries to complete job using original_token
    with pytest.raises(JobLeaseLostError) as exc_info:
        await JobWorkerService.complete_job(
            session=db_session,
            job_id=job.id,
            lease_token=original_token,
            doc_status=DocumentProcessingStatus.COMPLETED,
        )
    assert "lease token mismatch" in str(exc_info.value)
