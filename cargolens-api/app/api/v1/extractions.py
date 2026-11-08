from typing import Optional, Tuple
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment
from app.models.document import Document, DocumentProcessingStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.extraction import (
    DocumentExtraction,
    DocumentExtractionPage,
    ExtractionStatus,
)
from app.schemas.processing_job import ProcessingJobResponse
from app.schemas.extraction import (
    DocumentExtractionResponse,
    DocumentExtractionPageResponse,
    DocumentExtractionPagesListResponse,
    DocumentExtractionHistoryItem,
    DocumentExtractionHistoryResponse,
    DocumentProcessingStatusResponse,
)

router = APIRouter(tags=["Document Text Intelligence & Extraction"])


async def _get_authorized_document(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> Tuple[Shipment, Document]:
    """
    Verifies that the shipment and document exist and that current_user has access in the shared workspace.
    Returns 404 for non-existent shipments or non-existent documents.
    """
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    res = await session.execute(stmt)
    shipment = res.scalar_one_or_none()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID '{shipment_id}' not found",
        )

    doc_stmt = select(Document).where(
        and_(
            Document.id == document_id,
            Document.shipment_id == shipment_id,
            Document.is_active == True,
        )
    )
    doc_res = await session.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found in this shipment",
        )

    return shipment, doc


@router.post(
    "/shipments/{shipment_id}/documents/{document_id}/process",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Document OCR Processing",
    description="Queues a document for OCR and text extraction processing or retries a failed attempt.",
)
async def process_document(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    _, doc = await _get_authorized_document(shipment_id, document_id, current_user, session)

    # Check for duplicate active processing job
    active_job_stmt = select(ProcessingJob).where(
        and_(
            ProcessingJob.document_id == document_id,
            ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
        )
    )
    active_job_res = await session.execute(active_job_stmt)
    active_job = active_job_res.scalar_one_or_none()
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An active processing job ({active_job.id}) is already {active_job.status.value} "
                f"for this document."
            ),
        )

    # Queue new ingestion job
    new_job = ProcessingJob(
        document_id=doc.id,
        job_type="DOCUMENT_INGESTION",
        status=JobStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
    )
    session.add(new_job)

    doc.processing_status = DocumentProcessingStatus.PENDING
    await session.commit()
    await session.refresh(new_job)

    return ProcessingJobResponse.model_validate(new_job)


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/extraction",
    response_model=DocumentExtractionResponse,
    summary="Get Latest Document Extraction",
    description="Returns the latest extracted text, quality metrics, and metadata for a document.",
)
async def get_document_extraction(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentExtractionResponse:
    await _get_authorized_document(shipment_id, document_id, current_user, session)

    ext_stmt = (
        select(DocumentExtraction)
        .where(DocumentExtraction.document_id == document_id)
        .order_by(DocumentExtraction.attempt_number.desc())
        .limit(1)
    )
    ext_res = await session.execute(ext_stmt)
    ext = ext_res.scalar_one_or_none()

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No extraction records found for document '{document_id}'.",
        )

    return DocumentExtractionResponse.model_validate(ext)


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/extraction/pages",
    response_model=DocumentExtractionPagesListResponse,
    summary="Get Paginated Extracted Pages",
    description="Returns page-by-page extracted text, extraction method (DIGITAL vs OCR), and confidence scores.",
)
async def get_document_extraction_pages(
    shipment_id: UUID,
    document_id: UUID,
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    attempt_number: Optional[int] = Query(None, ge=1, description="Specific extraction attempt (default: latest)"),
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentExtractionPagesListResponse:
    await _get_authorized_document(shipment_id, document_id, current_user, session)

    # 1. Resolve target extraction attempt
    if attempt_number is not None:
        ext_stmt = select(DocumentExtraction).where(
            and_(
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.attempt_number == attempt_number,
            )
        )
    else:
        ext_stmt = (
            select(DocumentExtraction)
            .where(DocumentExtraction.document_id == document_id)
            .order_by(DocumentExtraction.attempt_number.desc())
            .limit(1)
        )

    ext_res = await session.execute(ext_stmt)
    ext = ext_res.scalar_one_or_none()

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No extraction attempt found for document '{document_id}'.",
        )

    # 2. Count total pages
    count_stmt = select(func.count(DocumentExtractionPage.id)).where(
        DocumentExtractionPage.extraction_id == ext.id
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    # 3. Retrieve paginated pages
    offset = (page - 1) * page_size
    pages_stmt = (
        select(DocumentExtractionPage)
        .where(DocumentExtractionPage.extraction_id == ext.id)
        .order_by(DocumentExtractionPage.page_number.asc())
        .offset(offset)
        .limit(page_size)
    )
    pages_res = await session.execute(pages_stmt)
    rows = pages_res.scalars().all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return DocumentExtractionPagesListResponse(
        items=[DocumentExtractionPageResponse.model_validate(p) for p in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/extraction/history",
    response_model=DocumentExtractionHistoryResponse,
    summary="Get Document Extraction History",
    description="Returns all historical extraction attempts for a document.",
)
async def get_document_extraction_history(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentExtractionHistoryResponse:
    await _get_authorized_document(shipment_id, document_id, current_user, session)

    hist_stmt = (
        select(DocumentExtraction)
        .where(DocumentExtraction.document_id == document_id)
        .order_by(DocumentExtraction.attempt_number.desc())
    )
    res = await session.execute(hist_stmt)
    extractions = res.scalars().all()

    items = [DocumentExtractionHistoryItem.model_validate(e) for e in extractions]
    return DocumentExtractionHistoryResponse(items=items, total=len(items))


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/processing-status",
    response_model=DocumentProcessingStatusResponse,
    summary="Get Document Processing & Job Status",
    description="Returns current document processing status, background job progress, and latest extraction metrics.",
)
async def get_document_processing_status(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentProcessingStatusResponse:
    _, doc = await _get_authorized_document(shipment_id, document_id, current_user, session)

    # 1. Fetch latest processing job
    job_stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    job_res = await session.execute(job_stmt)
    latest_job = job_res.scalar_one_or_none()

    # 2. Fetch latest extraction attempt
    ext_stmt = (
        select(DocumentExtraction)
        .where(DocumentExtraction.document_id == document_id)
        .order_by(DocumentExtraction.attempt_number.desc())
        .limit(1)
    )
    ext_res = await session.execute(ext_stmt)
    latest_ext = ext_res.scalar_one_or_none()

    return DocumentProcessingStatusResponse(
        document_id=doc.id,
        document_processing_status=doc.processing_status,
        active_job_id=latest_job.id if latest_job else None,
        job_status=latest_job.status if latest_job else None,
        attempt_count=latest_job.attempt_count if latest_job else 0,
        max_attempts=latest_job.max_attempts if latest_job else 3,
        started_at=latest_job.started_at if latest_job else None,
        completed_at=latest_job.completed_at if latest_job else None,
        error_message=latest_job.error_message if latest_job else None,
        latest_extraction=DocumentExtractionResponse.model_validate(latest_ext) if latest_ext else None,
    )
