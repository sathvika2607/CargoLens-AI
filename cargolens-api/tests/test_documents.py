import io
import hashlib
import asyncio
from uuid import uuid4
import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select, func

from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.security import hash_password, create_access_token
from app.storage import get_storage_service
from app.services.job_worker import JobWorkerService

# Helper generators for valid file payloads
MINIMAL_PDF_1 = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
)

# Second PDF with different content for version increment testing
MINIMAL_PDF_2 = (
    b"%PDF-1.4\n"
    b"% Version 2 distinct content for hashing\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000049 00000 n\n0000000092 00000 n\n0000000141 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n218\n%%EOF\n"
)

def create_minimal_png() -> bytes:
    img = Image.new("RGBA", (20, 20), color=(0, 255, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MINIMAL_PNG = create_minimal_png()


def create_minimal_jpeg() -> bytes:
    img = Image.new("RGB", (20, 20), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


MINIMAL_JPEG = create_minimal_jpeg()


def make_distinct_pdf(identifier: str) -> bytes:
    content = (
        f"%PDF-1.4\n"
        f"% Distinct payload {identifier}\n"
        f"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        f"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        f"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
        f"xref\n0 4\n0000000000 65535 f\n0000000049 00000 n\n0000000092 00000 n\n0000000141 00000 n\n"
        f"trailer<</Size 4/Root 1 0 R>>\nstartxref\n218\n%%EOF\n"
    )
    return content.encode("latin-1")


@pytest.fixture
async def setup_users_and_shipment(db_session):
    """Creates Executive 1, Executive 2, Manager, and an owned shipment for Executive 1."""
    exec1 = User(
        full_name="Doc Exec One",
        email="exec1.docs@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    exec2 = User(
        full_name="Doc Exec Two",
        email="exec2.docs@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    mgr = User(
        full_name="Doc Manager",
        email="mgr.docs@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_MANAGER,
        is_active=True,
    )
    db_session.add_all([exec1, exec2, mgr])
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-DOC-TEST-01",
        client_name="Test Importer Corp",
        origin_country="Germany",
        status=ShipmentStatus.CREATED,
        created_by=exec1.id,
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)

    token_exec1 = create_access_token(exec1.id, exec1.role.value, exec1.email)
    token_exec2 = create_access_token(exec2.id, exec2.role.value, exec2.email)
    token_mgr = create_access_token(mgr.id, mgr.role.value, mgr.email)

    return {
        "exec1": exec1,
        "exec2": exec2,
        "mgr": mgr,
        "shipment": shipment,
        "token_exec1": token_exec1,
        "token_exec2": token_exec2,
        "token_mgr": token_mgr,
    }


@pytest.mark.asyncio
async def test_valid_document_uploads(async_client: AsyncClient, setup_users_and_shipment):
    """Tests successful uploads for PDF, JPEG, and PNG with magic bytes validation."""
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    # 1. Valid PDF Upload
    pdf_files = {"file": ("commercial_invoice.pdf", MINIMAL_PDF_1, "application/pdf")}
    pdf_data = {"document_type": "COMMERCIAL_INVOICE"}
    res_pdf = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data=pdf_data,
        files=pdf_files,
        headers=headers,
    )
    assert res_pdf.status_code == 201
    doc_pdf = res_pdf.json()
    assert doc_pdf["document_type"] == "COMMERCIAL_INVOICE"
    assert doc_pdf["original_filename"] == "commercial_invoice.pdf"
    assert doc_pdf["mime_type"] == "application/pdf"
    assert doc_pdf["version"] == 1
    assert doc_pdf["is_latest"] is True
    assert doc_pdf["sha256_checksum"] == hashlib.sha256(MINIMAL_PDF_1).hexdigest()

    # 2. Valid JPEG Upload
    jpg_files = {"file": ("packing_list.jpg", MINIMAL_JPEG, "image/jpeg")}
    jpg_data = {"document_type": "PACKING_LIST"}
    res_jpg = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data=jpg_data,
        files=jpg_files,
        headers=headers,
    )
    assert res_jpg.status_code == 201
    doc_jpg = res_jpg.json()
    assert doc_jpg["document_type"] == "PACKING_LIST"
    assert doc_jpg["file_extension"] == ".jpg"
    assert doc_jpg["version"] == 1

    # 3. Valid PNG Upload
    png_files = {"file": ("bill_of_lading.png", MINIMAL_PNG, "image/png")}
    png_data = {"document_type": "BILL_OF_LADING"}
    res_png = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data=png_data,
        files=png_files,
        headers=headers,
    )
    assert res_png.status_code == 201
    doc_png = res_png.json()
    assert doc_png["document_type"] == "BILL_OF_LADING"
    assert doc_png["version"] == 1


@pytest.mark.asyncio
async def test_upload_rejections_and_validation(async_client: AsyncClient, setup_users_and_shipment):
    """
    Tests security rejections:
    - Unsupported file extension
    - Invalid file signature (fake PDF)
    - MIME / extension mismatch
    - Empty file (0 bytes)
    - File exceeding 25 MB
    - Invalid document type
    """
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    # 1. Unsupported extension
    res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("malicious.exe", b"MZexecutable", "application/octet-stream")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Unsupported file extension" in res.json()["detail"]

    # 2. Invalid file signature (named .pdf but contains text)
    res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("fake.pdf", b"This is plain text, not a PDF", "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Magic bytes verification failed" in res.json()["detail"]

    # 3. MIME and extension mismatch (named .png, declared image/jpeg)
    res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("mismatch.png", MINIMAL_PNG, "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "does not match file extension" in res.json()["detail"]

    # 4. Empty file (0 bytes)
    res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"]

    # 5. File exceeding 25 MB limit (tested via oversized buffer)
    oversized = b"%PDF-" + b"0" * (25 * 1024 * 1024 + 100)
    res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("huge.pdf", oversized, "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 413
    assert "exceeds maximum upload limit of 25 MB" in res.json()["detail"]

    # 6. Invalid document type enum
    res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "CUSTOMS_CERTIFICATE"},
        files={"file": ("invoice.pdf", MINIMAL_PDF_1, "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Invalid document_type" in res.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_rejection_and_versioning(async_client: AsyncClient, setup_users_and_shipment):
    """
    Verifies that:
    - Exact duplicate upload (same SHA-256 within shipment) returns HTTP 409 Conflict.
    - Subsequent different upload of the same document type increments version number.
    - Previous versions are preserved and accessible.
    """
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    # 1. Upload initial version 1
    res1 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_v1.pdf", MINIMAL_PDF_1, "application/pdf")},
        headers=headers,
    )
    assert res1.status_code == 201
    doc1 = res1.json()
    assert doc1["version"] == 1
    assert doc1["is_latest"] is True

    # 2. Re-upload identical file -> 409 Conflict
    res_dup = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_copy.pdf", MINIMAL_PDF_1, "application/pdf")},
        headers=headers,
    )
    assert res_dup.status_code == 409
    assert "already exists in this shipment" in res_dup.json()["detail"]

    # 3. Upload new, distinct version (different content) -> increments to version 2
    res2 = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_v2.pdf", MINIMAL_PDF_2, "application/pdf")},
        headers=headers,
    )
    assert res2.status_code == 201
    doc2 = res2.json()
    assert doc2["version"] == 2
    assert doc2["is_latest"] is True

    # 4. List versions endpoint -> returns both v2 and v1, ordered by version desc
    res_versions = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc2['id']}/versions",
        headers=headers,
    )
    assert res_versions.status_code == 200
    versions_data = res_versions.json()
    assert versions_data["total"] == 2
    assert versions_data["items"][0]["version"] == 2
    assert versions_data["items"][0]["is_latest"] is True
    assert versions_data["items"][1]["version"] == 1
    assert versions_data["items"][1]["is_latest"] is False


@pytest.mark.asyncio
async def test_document_authorization_and_privacy(async_client: AsyncClient, setup_users_and_shipment):
    """
    Verifies authorization scoping:
    - Executive 1 uploads and accesses own shipment's document.
    - Executive 2 requesting Executive 1's shipment receives 404 Not Found (privacy rule).
    - Executive 2 attempting download receives 404 Not Found.
    - Manager can access, list, and download documents across any shipment.
    - Unauthenticated request is rejected with 401.
    """
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    token_exec1 = ctx["token_exec1"]
    token_exec2 = ctx["token_exec2"]
    token_mgr = ctx["token_mgr"]

    # 1. Executive 1 uploads document
    res_upload = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice.pdf", MINIMAL_PDF_1, "application/pdf")},
        headers={"Authorization": f"Bearer {token_exec1}"},
    )
    assert res_upload.status_code == 201
    doc_id = res_upload.json()["id"]

    # 2. Executive 2 attempts upload to Executive 1's shipment -> 404 Not Found
    res_unauth_upload = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "PACKING_LIST"},
        files={"file": ("packing.jpg", MINIMAL_JPEG, "image/jpeg")},
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert res_unauth_upload.status_code == 404

    # 3. Executive 2 attempts to get document metadata -> 404 Not Found
    res_unauth_get = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert res_unauth_get.status_code == 404

    # 4. Executive 2 attempts download -> 404 Not Found
    res_unauth_dl = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token_exec2}"},
    )
    assert res_unauth_dl.status_code == 404

    # 5. Manager views document metadata -> 200 OK
    res_mgr_get = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res_mgr_get.status_code == 200
    assert res_mgr_get.json()["id"] == doc_id

    # 6. Manager downloads document -> 200 OK with correct content and headers
    res_mgr_dl = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res_mgr_dl.status_code == 200
    assert res_mgr_dl.content == MINIMAL_PDF_1
    assert "attachment; filename=" in res_mgr_dl.headers.get("Content-Disposition", "")
    assert res_mgr_dl.headers.get("Content-Type") == "application/pdf"

    # 7. Unauthenticated download rejected -> 401 Unauthorized
    res_no_auth = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}/download",
    )
    assert res_no_auth.status_code == 401


@pytest.mark.asyncio
async def test_background_job_creation_and_worker_claiming(
    async_client: AsyncClient, setup_users_and_shipment, db_session
):
    """
    Verifies that:
    - Uploading a document automatically creates a ProcessingJob with status PENDING.
    - Jobs can be listed via /api/v1/documents/{document_id}/jobs.
    - JobWorkerService claims the pending job safely using FOR UPDATE SKIP LOCKED.
    - Successfully claimed job updates to PROCESSING and then COMPLETED.
    - Multiple concurrent workers do not claim the same job twice.
    """
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    # 1. Upload document
    upload_res = await async_client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "BILL_OF_LADING"},
        files={"file": ("bol.pdf", MINIMAL_PDF_1, "application/pdf")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Check that a ProcessingJob was queued
    jobs_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/jobs",
        headers=headers,
    )
    assert jobs_res.status_code == 200
    jobs_data = jobs_res.json()
    assert jobs_data["total"] == 1
    job = jobs_data["items"][0]
    assert job["status"] == "PENDING"
    assert job["job_type"] == "DOCUMENT_INGESTION"
    assert job["attempt_count"] == 0

    # 3. Process single job lifecycle with worker service
    processed_job = await JobWorkerService.process_single_job(db_session)
    assert processed_job is not None
    assert str(processed_job.id) == job["id"]
    assert processed_job.status == JobStatus.COMPLETED
    assert processed_job.attempt_count == 1
    assert processed_job.started_at is not None
    assert processed_job.completed_at is not None

    # 4. Check updated document processing status via API
    doc_check = await async_client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{doc_id}",
        headers=headers,
    )
    assert doc_check.status_code == 200
    assert doc_check.json()["processing_status"] == "COMPLETED"

    # 5. When no more jobs are pending, worker returns None
    no_job = await JobWorkerService.claim_next_job(db_session)
    assert no_job is None


@pytest.mark.asyncio
async def test_job_worker_failure_and_retry_handling(db_session):
    """
    Verifies that worker properly increments attempt count and marks FAILED
    when max_attempts is reached.
    """
    # 1. Manually insert a document and processing job
    user = User(
        full_name="Job User",
        email="job.user@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-FAIL-TEST",
        client_name="Failure Test Consignee",
        origin_country="Italy",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    doc = Document(
        shipment_id=shipment.id,
        document_type=DocumentType.COMMERCIAL_INVOICE,
        original_filename="fail.pdf",
        storage_key="non_existent_file.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100,
        sha256_checksum="abc1234567890",
        version=1,
        uploaded_by=user.id,
        processing_status=DocumentProcessingStatus.PENDING,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()

    job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PENDING,
        attempt_count=0,
        max_attempts=2,
    )
    db_session.add(job)
    await db_session.commit()

    # Attempt 1: Claim and fail
    claimed_1 = await JobWorkerService.claim_next_job(db_session)
    assert claimed_1.attempt_count == 1
    failed_1 = await JobWorkerService.fail_job(db_session, claimed_1.id, "Simulated transient failure")
    assert failed_1.status == JobStatus.PENDING  # Still PENDING because attempt 1 < max 2

    # Attempt 2: Claim and fail again -> reaches max_attempts
    claimed_2 = await JobWorkerService.claim_next_job(db_session)
    assert claimed_2.attempt_count == 2
    failed_2 = await JobWorkerService.fail_job(db_session, claimed_2.id, "Simulated fatal failure")
    assert failed_2.status == JobStatus.FAILED  # Reached max_attempts
    assert failed_2.completed_at is not None
    assert "Simulated fatal failure" in failed_2.error_message


@pytest.mark.asyncio
async def test_concurrent_worker_claiming(db_session):
    """
    Verifies that multiple concurrent worker tasks attempting to claim jobs
    with FOR UPDATE SKIP LOCKED do not claim the same job twice.
    """
    user = User(
        full_name="Concurrent Worker User",
        email="concurrent.worker@cargolens.in",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCUMENTATION_EXECUTIVE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    shipment = Shipment(
        shipment_number="SHP-CONC-WORKER",
        client_name="Concurrent Importer",
        origin_country="UK",
        created_by=user.id,
    )
    db_session.add(shipment)
    await db_session.commit()

    # Create 3 documents and 3 pending jobs
    jobs = []
    for i in range(3):
        d = Document(
            shipment_id=shipment.id,
            document_type=DocumentType.COMMERCIAL_INVOICE,
            original_filename=f"invoice_{i}.pdf",
            storage_key=f"key_{uuid4().hex}.pdf",
            mime_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=500,
            sha256_checksum=f"hash_{uuid4().hex}",
            version=i + 1,
            uploaded_by=user.id,
            processing_status=DocumentProcessingStatus.PENDING,
            is_active=True,
        )
        db_session.add(d)
        await db_session.flush()

        j = ProcessingJob(
            document_id=d.id,
            job_type="DOCUMENT_INGESTION",
            status=JobStatus.PENDING,
            attempt_count=0,
            max_attempts=3,
        )
        db_session.add(j)
        jobs.append(j)

    await db_session.commit()

    # Launch 5 concurrent workers claiming jobs via separate database sessions
    from app.database import AsyncSessionFactory

    async def worker_claim():
        async with AsyncSessionFactory() as s:
            return await JobWorkerService.claim_next_job(s)

    claimed_results = await asyncio.gather(*[worker_claim() for _ in range(5)])

    # Filter non-None claimed jobs
    claimed_jobs = [j for j in claimed_results if j is not None]

    # Exactly 3 jobs should have been claimed across the 5 workers
    assert len(claimed_jobs) == 3

    # All 3 claimed jobs must have unique IDs (no duplicates claimed)
    claimed_ids = {j.id for j in claimed_jobs}
    assert len(claimed_ids) == 3


@pytest.mark.asyncio
async def test_concurrent_distinct_document_uploads_versioning(
    async_client: AsyncClient,
    setup_users_and_shipment,
    db_session,
):
    """
    Verifies concurrency-safe document version assignment:
    Simultaneous uploads of 5 distinct files for the same shipment and document type
    are serialized by PostgreSQL row-level locking (FOR UPDATE) on the parent shipment.
    Each upload receives a unique, strictly sequential version number (1 through 5).
    """
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    distinct_files = [
        (f"invoice_batch_{i}.pdf", make_distinct_pdf(f"batch_item_{i}"), "application/pdf")
        for i in range(5)
    ]

    async def upload_single(filename: str, content: bytes, mime: str):
        return await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "COMMERCIAL_INVOICE"},
            files={"file": (filename, content, mime)},
            headers=headers,
        )

    responses = await asyncio.gather(
        *[upload_single(fn, cnt, mime) for fn, cnt, mime in distinct_files]
    )

    # All 5 uploads must succeed with 201 Created
    for idx, r in enumerate(responses):
        assert r.status_code == 201, f"Upload {idx} failed with {r.status_code}: {r.text}"

    # Versions must be strictly unique and sequential: 1, 2, 3, 4, 5
    assigned_versions = sorted([r.json()["version"] for r in responses])
    assert assigned_versions == [1, 2, 3, 4, 5]

    # Verify directly in database that 5 document records exist with versions 1..5
    db_docs = (
        await db_session.execute(
            select(Document)
            .where(Document.shipment_id == shipment_id)
            .order_by(Document.version.asc())
        )
    ).scalars().all()

    assert len(db_docs) == 5
    assert [d.version for d in db_docs] == [1, 2, 3, 4, 5]

    # Check that storage files all exist
    storage = get_storage_service()
    for d in db_docs:
        assert await storage.file_exists(d.storage_key) is True


@pytest.mark.asyncio
async def test_concurrent_duplicate_document_uploads(
    async_client: AsyncClient,
    setup_users_and_shipment,
    db_session,
):
    """
    Verifies concurrency-safe duplicate prevention:
    Simultaneous uploads of the EXACT SAME file to the same shipment yield
    exactly one 201 Created and all other concurrent attempts return HTTP 409 Conflict.
    No orphaned storage files remain from rejected uploads.
    """
    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    duplicate_content = make_distinct_pdf("duplicate_candidate_payload")
    duplicate_hash = hashlib.sha256(duplicate_content).hexdigest()

    async def upload_duplicate(idx: int):
        return await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "COMMERCIAL_INVOICE"},
            files={"file": (f"invoice_dup_{idx}.pdf", duplicate_content, "application/pdf")},
            headers=headers,
        )

    # Launch 3 simultaneous identical uploads
    responses = await asyncio.gather(*[upload_duplicate(i) for i in range(3)])

    successes = [r for r in responses if r.status_code == 201]
    conflicts = [r for r in responses if r.status_code == 409]

    # Exactly one succeeded
    assert len(successes) == 1
    # Exactly two were rejected with 409 Conflict
    assert len(conflicts) == 2

    for c in conflicts:
        detail = c.json()["detail"].lower()
        assert "already exists in this shipment" in detail or "sha-256" in detail or "conflict" in detail

    # Verify directly in database that only ONE document record exists with this hash
    count = await db_session.scalar(
        select(func.count(Document.id)).where(
            Document.shipment_id == shipment_id,
            Document.sha256_checksum == duplicate_hash,
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_same_file_different_shipments_allowed(
    async_client: AsyncClient,
    setup_users_and_shipment,
    db_session,
):
    """
    Verifies that identical files CAN be uploaded to different shipments.
    Uniqueness is scoped to (shipment_id, sha256_checksum).
    """
    ctx = setup_users_and_shipment
    shipment_id_1 = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    # Create a second shipment for exec1
    shipment2 = Shipment(
        shipment_number="SHP-DOC-TEST-02",
        client_name="Second Importer Corp",
        origin_country="Japan",
        status=ShipmentStatus.CREATED,
        created_by=ctx["exec1"].id,
    )
    db_session.add(shipment2)
    await db_session.commit()
    await db_session.refresh(shipment2)
    shipment_id_2 = shipment2.id

    content = make_distinct_pdf("shared_across_shipments_payload")

    # Upload to shipment 1
    res1 = await async_client.post(
        f"/api/v1/shipments/{shipment_id_1}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_shp1.pdf", content, "application/pdf")},
        headers=headers,
    )
    assert res1.status_code == 201

    # Upload identical file to shipment 2 -> must succeed
    res2 = await async_client.post(
        f"/api/v1/shipments/{shipment_id_2}/documents",
        data={"document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_shp2.pdf", content, "application/pdf")},
        headers=headers,
    )
    assert res2.status_code == 201

    doc1 = res1.json()
    doc2 = res2.json()
    assert doc1["sha256_checksum"] == doc2["sha256_checksum"]
    assert doc1["shipment_id"] != doc2["shipment_id"]
    assert doc1["version"] == 1
    assert doc2["version"] == 1


@pytest.mark.asyncio
async def test_storage_cleanup_on_database_integrity_error(
    async_client: AsyncClient,
    setup_users_and_shipment,
    monkeypatch,
):
    """
    Verifies that when an IntegrityError occurs at database commit (e.g. uq_documents_shipment_checksum),
    the newly written storage file is cleanly deleted and HTTP 409 is returned.
    """
    from unittest.mock import patch
    from sqlalchemy.exc import IntegrityError
    from app.storage import get_storage_service

    ctx = setup_users_and_shipment
    shipment_id = ctx["shipment"].id
    headers = {"Authorization": f"Bearer {ctx['token_exec1']}"}

    storage = get_storage_service()
    saved_keys = []
    original_save = storage.save_file

    async def tracking_save(stream, key):
        saved_keys.append(key)
        return await original_save(stream, key)

    monkeypatch.setattr(storage, "save_file", tracking_save)

    # Patch session.commit in app.api.v1.documents to simulate IntegrityError
    async def mock_commit_failure(*args, **kwargs):
        raise IntegrityError(
            "statement",
            {},
            Exception('duplicate key value violates unique constraint "uq_documents_shipment_checksum"'),
        )

    with patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new=mock_commit_failure):
        res = await async_client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "COMMERCIAL_INVOICE"},
            files={"file": ("fail_cleanup.pdf", make_distinct_pdf("will_fail_integrity"), "application/pdf")},
            headers=headers,
        )
        assert res.status_code == 409
        assert "already exists in this shipment" in res.json()["detail"]

    # Verify that the storage key that was saved was cleanly deleted
    assert len(saved_keys) == 1
    assert await storage.file_exists(saved_keys[0]) is False
