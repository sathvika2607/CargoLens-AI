import io
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update, func
import pymupdf

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.extraction import (
    DocumentExtraction,
    DocumentExtractionPage,
    ExtractionStatus,
    ExtractionMethod,
    ExtractionQualityStatus,
    PageExtractionMethod,
)
from app.security import hash_password, create_access_token
from app.services.job_worker import JobWorkerService, JobLeaseLostError
from app.database import AsyncSessionFactory


def make_test_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 72), text, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


@pytest.fixture
async def setup_ocr_environment(db_session):
    """Creates Executive 1, Executive 2, Manager, and an owned shipment for Executive 1."""
    exec1 = User(
        full_name="Doc Exec One",
        email="exec1.ocr@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    exec2 = User(
        full_name="Doc Exec Two",
        email="exec2.ocr@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr = User(
        full_name="Doc Manager",
        email="mgr.ocr@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec1, exec2, mgr])
    await db_session.commit()

    shipment1 = Shipment(
        shipment_number="SHP-OCR-TEST-01",
        client_name="Test Importer Corp",
        origin_country="Germany",
        status=ShipmentStatus.CREATED,
        created_by=exec1.id,
    )
    shipment2 = Shipment(
        shipment_number="SHP-OCR-TEST-02",
        client_name="Other Importer Corp",
        origin_country="France",
        status=ShipmentStatus.CREATED,
        created_by=exec2.id,
    )
    db_session.add_all([shipment1, shipment2])
    await db_session.commit()
    await db_session.refresh(shipment1)
    await db_session.refresh(shipment2)

    token_exec1 = create_access_token(exec1.id, exec1.role.value, exec1.email)
    token_exec2 = create_access_token(exec2.id, exec2.role.value, exec2.email)
    token_mgr = create_access_token(mgr.id, mgr.role.value, mgr.email)

    return {
        "exec1": exec1,
        "exec2": exec2,
        "mgr": mgr,
        "shipment1": shipment1,
        "shipment2": shipment2,
        "token_exec1": token_exec1,
        "token_exec2": token_exec2,
        "token_mgr": token_mgr,
    }


@pytest.mark.asyncio
async def test_worker_end_to_end_ocr_execution(
    async_client: AsyncClient,
    setup_ocr_environment,
    db_session,
):
    """
    Verifies that the background worker:
    1. Claims a pending document upload job.
    2. Loads the document from private storage.
    3. Runs the OCR pipeline.
    4. Persists DocumentExtraction and DocumentExtractionPage records.
    5. Updates Document.processing_status and ProcessingJob.status to COMPLETED.
    """
    ctx = setup_ocr_environment
    shipment_id = ctx["shipment1"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    pdf_content = make_test_pdf("COMMERCIAL INVOICE\nInvoice: INV-END2END-01\nTotal: $50,000.00")

    # 1. Upload document (creates document + pending job)
    upload_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_end2end.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Execute worker single job
    processed_job = await JobWorkerService.process_single_job(db_session)
    assert processed_job is not None
    assert processed_job.status == JobStatus.COMPLETED
    assert str(processed_job.document_id) == doc_id

    # 3. Check document status in database
    doc_db = (
        await db_session.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one()
    assert doc_db.processing_status == DocumentProcessingStatus.COMPLETED

    # 4. Check extraction records in database
    ext_db = (
        await db_session.execute(
            select(DocumentExtraction).where(DocumentExtraction.document_id == doc_id)
        )
    ).scalar_one()

    assert ext_db.attempt_number == 1
    assert ext_db.status == ExtractionStatus.COMPLETED
    assert ext_db.extraction_method == ExtractionMethod.DIGITAL_TEXT
    assert ext_db.quality_status == ExtractionQualityStatus.GOOD
    assert "INV-END2END-01" in ext_db.raw_text
    assert ext_db.page_count == 1
    assert ext_db.processed_page_count == 1

    # 5. Check page-level records
    page_db = (
        await db_session.execute(
            select(DocumentExtractionPage).where(
                DocumentExtractionPage.extraction_id == ext_db.id
            )
        )
    ).scalar_one()

    assert page_db.page_number == 1
    assert page_db.extraction_method == PageExtractionMethod.DIGITAL_TEXT
    assert "INV-END2END-01" in page_db.raw_text
    assert page_db.character_count > 0


@pytest.mark.asyncio
async def test_extraction_api_endpoints(
    async_client: AsyncClient,
    setup_ocr_environment,
    db_session,
):
    """
    Verifies the extraction API endpoints:
    - GET .../extraction (summary)
    - GET .../extraction/pages (paginated page text)
    - GET .../extraction/history (attempt history)
    - GET .../processing-status (status check)
    """
    ctx = setup_ocr_environment
    shipment_id = ctx["shipment1"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    pdf_content = make_test_pdf("TEST INVOICE DETAILS\nNumber: INV-API-001\nAmount: $10,000")

    # Upload document
    upload_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_api.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    doc_id = upload_res.json()["id"]

    # Before processing: GET extraction returns 404
    get_before = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction",
        headers=headers,
    )
    assert get_before.status_code == 404

    # Run worker to extract
    await JobWorkerService.process_single_job(db_session)

    # 1. GET extraction summary
    ext_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction",
        headers=headers,
    )
    assert ext_res.status_code == 200
    ext_data = ext_res.json()
    assert ext_data["document_id"] == doc_id
    assert ext_data["attempt_number"] == 1
    assert ext_data["extraction_method"] == "DIGITAL_TEXT"
    assert ext_data["quality_status"] == "GOOD"
    assert "INV-API-001" in ext_data["raw_text"]

    # 2. GET extraction pages
    pages_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction/pages?page=1&page_size=10",
        headers=headers,
    )
    assert pages_res.status_code == 200
    pages_data = pages_res.json()
    assert pages_data["total"] == 1
    assert len(pages_data["items"]) == 1
    assert pages_data["items"][0]["page_number"] == 1
    assert "INV-API-001" in pages_data["items"][0]["raw_text"]

    # 3. GET extraction history
    hist_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction/history",
        headers=headers,
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["total"] == 1
    assert hist_data["items"][0]["attempt_number"] == 1

    # 4. GET processing status
    status_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/processing-status",
        headers=headers,
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["document_processing_status"] == "COMPLETED"
    assert status_data["job_status"] == "COMPLETED"
    assert status_data["latest_extraction"] is not None


@pytest.mark.asyncio
async def test_reprocess_endpoint_and_duplicate_job_prevention(
    async_client: AsyncClient,
    setup_ocr_environment,
    db_session,
):
    """
    Verifies:
    - POST .../process triggers a new processing attempt (202 Accepted).
    - Calling POST .../process while a job is already PENDING/PROCESSING returns 409 Conflict.
    - Multiple extraction attempts are preserved in history (v1 attempt 1 -> attempt 2).
    """
    ctx = setup_ocr_environment
    shipment_id = ctx["shipment1"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    pdf_content = make_test_pdf("INITIAL TEXT FOR ATTEMPT ONE")

    upload_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_reprocess.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    doc_id = upload_res.json()["id"]

    # Document was just uploaded, initial job is PENDING:
    # Triggering another process request immediately must fail with 409 Conflict!
    conflict_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/process",
        headers=headers,
    )
    assert conflict_res.status_code == 409
    assert "already" in conflict_res.json()["detail"].lower()

    # Process first attempt
    await JobWorkerService.process_single_job(db_session)

    # Now that the first job is COMPLETED, triggering reprocess must succeed (202 Accepted)
    reprocess_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/process",
        headers=headers,
    )
    assert reprocess_res.status_code == 202
    new_job = reprocess_res.json()
    assert new_job["status"] == "PENDING"

    # Process second attempt
    await JobWorkerService.process_single_job(db_session)

    # History should now contain exactly 2 extraction attempts
    hist_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction/history",
        headers=headers,
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["total"] == 2
    attempts = [item["attempt_number"] for item in hist_data["items"]]
    assert attempts == [2, 1]


@pytest.mark.asyncio
async def test_extraction_authorization_and_privacy(
    async_client: AsyncClient,
    setup_ocr_environment,
    db_session,
):
    """
    Verifies privacy rule:
    - Executive 1 owns Shipment 1.
    - Executive 2 attempting to access Shipment 1's extraction receives 404 Not Found.
    - Manager can access all extractions.
    - Unauthenticated request receives 401.
    """
    ctx = setup_ocr_environment
    shipment_id = ctx["shipment1"].id
    headers_exec1 = {"Authorization": f"Bearer {ctx['token_exec1']}"}
    headers_exec2 = {"Authorization": f"Bearer {ctx['token_exec2']}"}
    headers_mgr = {"Authorization": f"Bearer {ctx['token_mgr']}"}

    pdf_content = make_test_pdf("PRIVACY ISOLATION TEST")

    upload_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("privacy_test.pdf", pdf_content, "application/pdf")},
        headers=headers_exec1,
    )
    doc_id = upload_res.json()["id"]
    await JobWorkerService.process_single_job(db_session)

    # 1. Unauthenticated -> 401
    unauth_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction"
    )
    assert unauth_res.status_code == 401

    # 2. Executive 2 accessing extraction in shared workspace -> 200 OK
    other_exec_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction",
        headers=headers_exec2,
    )
    assert other_exec_res.status_code == 200

    # 3. Manager accessing Executive 1's extraction -> 200 OK
    mgr_res = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/extraction",
        headers=headers_mgr,
    )
    assert mgr_res.status_code == 200


@pytest.mark.asyncio
async def test_stale_job_recovery(db_session):
    """
    Verifies that recover_stale_jobs identifies jobs whose lease has expired
    and requeues them as PENDING (or marks FAILED if max attempts reached).
    """
    user = User(
        full_name="Stale User",
        email="stale.worker@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-STALE-01",
        client_name="Stale Importer",
        origin_country="USA",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="stale.pdf",
        storage_key=f"stale_{uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100,
        sha256_checksum=f"hash_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.PROCESSING,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.flush()

    # Job 1: Attempt 1, lease expired 5 minutes ago -> should requeue to PENDING
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    job_requeue = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PROCESSING,
        attempt_count=1,
        max_attempts=3,
        started_at=stale_time,
        lease_expires_at=stale_time,
        lease_token=uuid4(),
    )

    # Job 2: Attempt 3 (reached max), lease expired 5 minutes ago -> should mark FAILED
    job_fail = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PROCESSING,
        attempt_count=3,
        max_attempts=3,
        started_at=stale_time,
        lease_expires_at=stale_time,
        lease_token=uuid4(),
    )
    db_session.add_all([job_requeue, job_fail])
    await db_session.commit()

    recovered_ids = await JobWorkerService.recover_stale_jobs(db_session)

    assert len(recovered_ids) == 2
    assert job_requeue.id in recovered_ids
    assert job_fail.id in recovered_ids

    await db_session.refresh(job_requeue)
    await db_session.refresh(job_fail)

    assert job_requeue.status == JobStatus.PENDING
    assert job_requeue.lease_token is None
    assert job_fail.status == JobStatus.FAILED
    assert "lease expired" in job_fail.error_message


@pytest.mark.asyncio
async def test_active_worker_lease_renewal(db_session):
    """
    Verifies that an active worker can periodically renew its lease,
    extending lease_expires_at into the future.
    """
    user = User(
        full_name="Lease Renew User",
        email="lease.renew@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-LEASE-RENEW",
        client_name="Renew Importer",
        origin_country="Japan",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="renew.pdf",
        storage_key=f"renew_{uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100,
        sha256_checksum=f"hash_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.flush()

    job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()

    # Claim job with 10s short lease
    claimed_job = await JobWorkerService.claim_next_job(db_session, lease_duration_seconds=10)
    assert claimed_job is not None
    assert claimed_job.lease_token is not None
    assert claimed_job.lease_expires_at is not None
    initial_expiry = claimed_job.lease_expires_at

    # Renew lease with 120s extension
    renewed = await JobWorkerService.renew_lease(
        db_session,
        claimed_job.id,
        claimed_job.lease_token,
        lease_duration_seconds=120,
    )
    assert renewed is True

    await db_session.refresh(claimed_job)
    assert claimed_job.lease_expires_at > initial_expiry


@pytest.mark.asyncio
async def test_job_not_recovered_while_lease_valid(db_session):
    """
    Verifies that a job is NOT recovered if its lease remains valid (lease_expires_at > now),
    even if the total processing duration has been long.
    """
    user = User(
        full_name="Valid Lease User",
        email="valid.lease@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-VALID-LEASE",
        client_name="Valid Lease Importer",
        origin_country="Italy",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="valid_lease.pdf",
        storage_key=f"valid_{uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100,
        sha256_checksum=f"hash_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.PROCESSING,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.flush()

    # Job started 15 minutes ago, but lease was renewed and is valid for another 5 minutes!
    job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PROCESSING,
        attempt_count=1,
        max_attempts=3,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        lease_token=uuid4(),
    )
    db_session.add(job)
    await db_session.commit()

    # Run stale recovery
    recovered_ids = await JobWorkerService.recover_stale_jobs(db_session)

    # Job MUST NOT be recovered!
    assert len(recovered_ids) == 0
    await db_session.refresh(job)
    assert job.status == JobStatus.PROCESSING
    assert job.lease_token is not None


@pytest.mark.asyncio
async def test_concurrent_recovery_workers(db_session):
    """
    Verifies that multiple concurrent recovery worker tasks using
    SELECT ... FOR UPDATE SKIP LOCKED safely partition and recover stale jobs
    without conflicts, deadlocks, or duplicate processing.
    """
    user = User(
        full_name="Concurrent Recovery User",
        email="concurrent.rec@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-CONC-REC",
        client_name="Concurrent Importer",
        origin_country="UK",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    # Create 3 stale jobs
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    stale_job_ids = []
    for i in range(3):
        doc = Document(
            shipment_id=shipment.id,
            document_type=DocumentType.COMMERCIAL_INVOICE,
            original_filename=f"stale_{i}.pdf",
            storage_key=f"key_{uuid4().hex}.pdf",
            mime_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=100,
            sha256_checksum=f"hash_{uuid4().hex}",
            version=i + 1,
            uploaded_by=user.id,
            processing_status=DocumentProcessingStatus.PROCESSING,
            is_active=True,
        )
        db_session.add(doc)
        await db_session.flush()

        job = ProcessingJob(
            document_id=doc.id,
            job_type="DOCUMENT_INGESTION",
            status=JobStatus.PROCESSING,
            attempt_count=1,
            max_attempts=3,
            started_at=stale_time,
            lease_expires_at=stale_time,
            lease_token=uuid4(),
        )
        db_session.add(job)
        await db_session.flush()
        stale_job_ids.append(job.id)

    await db_session.commit()

    # Launch 5 concurrent recovery workers via separate database sessions
    async def worker_recover():
        async with AsyncSessionFactory() as s:
            return await JobWorkerService.recover_stale_jobs(s)

    results = await asyncio.gather(*[worker_recover() for _ in range(5)])

    # Flatten results
    all_recovered = [jid for sublist in results for jid in sublist]

    # Exactly 3 jobs should have been recovered across the 5 workers
    assert len(all_recovered) == 3
    assert set(all_recovered) == set(stale_job_ids)


@pytest.mark.asyncio
async def test_old_worker_cannot_overwrite_reclaimed_job(db_session):
    """
    Verifies that if an old worker stalls and its lease expires,
    and a recovery worker reclaims the job:
    The old worker's attempt to complete or persist results is rejected with JobLeaseLostError,
    preventing stale workers from corrupting or overwriting newly assigned jobs.
    """
    from app.services.ocr.pipeline import ExtractionPipelineResult
    from app.models.extraction import ExtractionStatus, ExtractionMethod, ExtractionQualityStatus

    user = User(
        full_name="Fence User",
        email="fence.worker@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-FENCE-01",
        client_name="Fence Importer",
        origin_country="Singapore",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="fence.pdf",
        storage_key=f"fence_{uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100,
        sha256_checksum=f"hash_{uuid4().hex}",
        version=1,
        uploaded_by=user.id,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.flush()

    job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.commit()

    # 1. Worker A claims the job with a short lease
    claimed_a = await JobWorkerService.claim_next_job(db_session, lease_duration_seconds=1)
    assert claimed_a is not None
    lease_token_a = claimed_a.lease_token

    # 2. Simulate lease expiration
    claimed_a.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    await db_session.commit()

    # 3. Recovery worker recovers the expired job -> requeued as PENDING
    recovered_ids = await JobWorkerService.recover_stale_jobs(db_session)
    assert claimed_a.id in recovered_ids

    # 4. Worker B claims the job -> gets a new lease token B
    claimed_b = await JobWorkerService.claim_next_job(db_session, lease_duration_seconds=60)
    assert claimed_b is not None
    assert claimed_b.id == claimed_a.id
    assert claimed_b.lease_token != lease_token_a

    # 5. Stale Worker A finishes late and attempts to complete the job with lease_token_A
    with pytest.raises(JobLeaseLostError):
        await JobWorkerService.complete_job(db_session, claimed_a.id, lease_token=lease_token_a)

    # 6. Stale Worker A also attempts to persist extraction with lease_token_A
    dummy_result = ExtractionPipelineResult(
        document_id=doc.id,
        status=ExtractionStatus.COMPLETED,
        extraction_method=ExtractionMethod.DIGITAL_TEXT,
        raw_text="STALE RESULTS FROM WORKER A",
        page_count=1,
        processed_page_count=1,
        failed_page_count=0,
        avg_confidence=None,
        character_count=26,
        quality_status=ExtractionQualityStatus.GOOD,
    )
    with pytest.raises(JobLeaseLostError):
        await JobWorkerService.persist_extraction(
            db_session, doc.id, dummy_result, lease_token=lease_token_a
        )

    # 7. Verify Worker B's active job is preserved and no extractions were persisted by Worker A
    await db_session.refresh(claimed_b)
    assert claimed_b.status == JobStatus.PROCESSING
    assert claimed_b.lease_token != lease_token_a

    ext_count = await db_session.scalar(
        select(func.count(DocumentExtraction.id)).where(DocumentExtraction.document_id == doc.id)
    )
    assert ext_count == 0
