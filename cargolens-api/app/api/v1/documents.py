import io
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse, Response
import pymupdf
from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.schemas.processing_job import ProcessingJobResponse, ProcessingJobListResponse
from app.services.document_validation import (
    validate_document_type,
    process_and_validate_upload_stream,
    sanitize_filename,
)
from app.storage import get_storage_service, StorageService

router = APIRouter(tags=["Document Management"])


async def _get_authorized_shipment(
    shipment_id: UUID,
    current_user: User,
    session: AsyncSession,
    for_update: bool = False,
) -> Shipment:
    """
    Verifies that the shipment exists and that current_user has access in the shared workspace.
    When for_update=True, acquires an exclusive row lock (FOR UPDATE) to serialize
    concurrent upload operations on this specific shipment.
    """
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    if for_update:
        stmt = stmt.with_for_update()

    res = await session.execute(stmt)
    shipment = res.scalar_one_or_none()

    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID '{shipment_id}' not found",
        )
    return shipment


def _annotate_latest_versions(docs: List[Document]) -> List[DocumentResponse]:
    """
    Determines is_latest flag for each document per document_type.
    The highest version of each active document_type in the list receives is_latest=True.
    """
    latest_version_by_type = {}
    for d in docs:
        if d.is_active:
            current_max = latest_version_by_type.get(d.document_type, 0)
            if d.version > current_max:
                latest_version_by_type[d.document_type] = d.version

    result = []
    for d in docs:
        resp = DocumentResponse.model_validate(d)
        resp.is_latest = d.version == latest_version_by_type.get(d.document_type)
        result.append(resp)
    return result


@router.post(
    "/shipments/{shipment_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Consignment Document",
    description="Uploads a Commercial Invoice, Packing List, or Bill of Lading with magic bytes and checksum validation.",
)
async def upload_document(
    shipment_id: UUID,
    document_type: str = Form(..., description="Document type: COMMERCIAL_INVOICE, PACKING_LIST, BILL_OF_LADING"),
    file: UploadFile = File(..., description="Document file (.pdf, .jpg, .jpeg, .png up to 25 MB)"),
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    # 1. Authorize shipment access and acquire row lock to serialize concurrent uploads for this shipment
    shipment = await _get_authorized_shipment(shipment_id, current_user, session, for_update=True)

    # 2. Validate document type
    validated_doc_type = validate_document_type(document_type)

    # 3. Stream, validate signature, enforce 25 MB, compute SHA-256
    file_bytes, clean_filename, extension, mime_type, file_size, sha256_checksum = (
        await process_and_validate_upload_stream(file)
    )

    # 4. Check for duplicate within the same shipment
    dup_stmt = select(Document).where(
        and_(
            Document.shipment_id == shipment_id,
            Document.sha256_checksum == sha256_checksum,
            Document.is_active == True,
        )
    )
    dup_res = await session.execute(dup_stmt)
    existing_dup = dup_res.scalar_one_or_none()
    if existing_dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An identical document with SHA-256 checksum '{sha256_checksum[:12]}...' "
                f"already exists in this shipment ({existing_dup.document_type.value} v{existing_dup.version})."
            ),
        )

    # 5. Determine next version safely within transaction
    version_stmt = select(func.coalesce(func.max(Document.version), 0)).where(
        and_(
            Document.shipment_id == shipment_id,
            Document.document_type == validated_doc_type,
        )
    )
    version_res = await session.execute(version_stmt)
    current_max_version = version_res.scalar() or 0
    next_version = current_max_version + 1

    # 6. Store file via provider-neutral storage service
    storage = get_storage_service()
    storage_key = storage.get_safe_storage_key(extension)

    async def _bytes_generator():
        yield file_bytes

    try:
        await storage.save_file(_bytes_generator(), storage_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write document to storage: {str(e)}",
        )

    # 7. Persist Document and ProcessingJob records in database
    try:
        new_doc = Document(
            shipment_id=shipment.id,
            document_type=validated_doc_type,
            original_filename=clean_filename,
            storage_key=storage_key,
            mime_type=mime_type,
            file_extension=extension,
            file_size_bytes=file_size,
            sha256_checksum=sha256_checksum,
            version=next_version,
            uploaded_by=current_user.id,
            processing_status=DocumentProcessingStatus.PENDING,
            is_active=True,
        )
        session.add(new_doc)
        await session.flush()  # Obtain new_doc.id

        # Queue initial background processing job
        initial_job = ProcessingJob(
            document_id=new_doc.id,
            job_type="DOCUMENT_INGESTION",
            status=JobStatus.PENDING,
            attempt_count=0,
            max_attempts=3,
        )
        session.add(initial_job)

        # Update shipment lifecycle status if in initial CREATED state
        if shipment.status == ShipmentStatus.CREATED:
            shipment.status = ShipmentStatus.DOCUMENTS_PENDING

        await session.commit()
        await session.refresh(new_doc)

        doc_response = DocumentResponse.model_validate(new_doc)
        doc_response.is_latest = True
        return doc_response
    except IntegrityError as exc:
        # Atomic rollback and file cleanup when database constraint is violated
        await storage.delete_file(storage_key)
        await session.rollback()
        err_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        if "uq_documents_shipment_checksum" in err_msg or "sha256_checksum" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"An identical document with SHA-256 checksum '{sha256_checksum[:12]}...' "
                    f"already exists in this shipment."
                ),
            )
        elif "uq_documents_shipment_type_version" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A document of type '{validated_doc_type.value}' with version {next_version} "
                    f"was concurrently created in this shipment. Please retry."
                ),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Database constraint violation: {err_msg}",
            )
    except Exception:
        # Atomic rollback: clean up orphaned file from storage
        await storage.delete_file(storage_key)
        await session.rollback()
        raise


@router.get(
    "/shipments/{shipment_id}/documents",
    response_model=DocumentListResponse,
    summary="List Shipment Documents",
    description="Lists all uploaded documents and versions associated with a shipment.",
)
async def list_shipment_documents(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    await _get_authorized_shipment(shipment_id, current_user, session)

    stmt = (
        select(Document)
        .where(Document.shipment_id == shipment_id, Document.is_active == True)
        .order_by(Document.document_type.asc(), Document.version.desc())
    )
    res = await session.execute(stmt)
    docs = res.scalars().all()

    annotated = _annotate_latest_versions(list(docs))
    return DocumentListResponse(items=annotated, total=len(annotated))


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Metadata",
    description="Retrieves metadata for a specific document.",
)
async def get_document(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    await _get_authorized_shipment(shipment_id, current_user, session)

    stmt = select(Document).where(
        Document.id == document_id,
        Document.shipment_id == shipment_id,
        Document.is_active == True,
    )
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    # Check if latest version
    max_ver_stmt = select(func.max(Document.version)).where(
        Document.shipment_id == shipment_id,
        Document.document_type == doc.document_type,
        Document.is_active == True,
    )
    max_ver = (await session.execute(max_ver_stmt)).scalar() or 1

    resp = DocumentResponse.model_validate(doc)
    resp.is_latest = doc.version == max_ver
    return resp


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/download",
    summary="Download Document File",
    description="Streams the original document file securely with sanitized headers.",
)
async def download_document(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
):
    await _get_authorized_shipment(shipment_id, current_user, session)

    stmt = select(Document).where(
        Document.id == document_id,
        Document.shipment_id == shipment_id,
        Document.is_active == True,
    )
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    storage = get_storage_service()
    if not await storage.file_exists(doc.storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file payload not found in storage.",
        )

    safe_name = sanitize_filename(doc.original_filename)

    return StreamingResponse(
        storage.get_file_stream(doc.storage_key),
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(doc.file_size_bytes),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/versions",
    response_model=DocumentListResponse,
    summary="List Document Versions",
    description="Retrieves the full version history for this document's type within the shipment.",
)
async def list_document_versions(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    await _get_authorized_shipment(shipment_id, current_user, session)

    target_stmt = select(Document).where(
        Document.id == document_id,
        Document.shipment_id == shipment_id,
    )
    target_res = await session.execute(target_stmt)
    target_doc = target_res.scalar_one_or_none()

    if not target_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    versions_stmt = (
        select(Document)
        .where(
            Document.shipment_id == shipment_id,
            Document.document_type == target_doc.document_type,
            Document.is_active == True,
        )
        .order_by(Document.version.desc())
    )
    versions_res = await session.execute(versions_stmt)
    version_docs = versions_res.scalars().all()

    annotated = _annotate_latest_versions(list(version_docs))
    return DocumentListResponse(items=annotated, total=len(annotated))


@router.get(
    "/documents/{document_id}/jobs",
    response_model=ProcessingJobListResponse,
    summary="List Document Processing Jobs",
    description="Retrieves the background processing jobs associated with a document.",
)
async def list_document_jobs(
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobListResponse:
    # 1. Fetch document
    doc_stmt = select(Document).where(Document.id == document_id)
    doc_res = await session.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    # 2. Check authorization for parent shipment
    await _get_authorized_shipment(doc.shipment_id, current_user, session)

    # 3. Fetch jobs
    jobs_stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    jobs_res = await session.execute(jobs_stmt)
    jobs = jobs_res.scalars().all()

    return ProcessingJobListResponse(
        items=[ProcessingJobResponse.model_validate(j) for j in jobs],
        total=len(jobs),
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/pages/{page_number}/image",
    summary="Get Document Page Rendered as Image",
    description="Renders a specific page of a PDF, or returns an image file, for side-by-side human review.",
)
async def get_document_page_image(
    shipment_id: UUID,
    document_id: UUID,
    page_number: int,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
):
    await _get_authorized_shipment(shipment_id, current_user, session)

    stmt = select(Document).where(
        Document.id == document_id,
        Document.shipment_id == shipment_id,
        Document.is_active == True,
    )
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    storage = get_storage_service()
    if not await storage.file_exists(doc.storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file payload not found in storage.",
        )

    chunks = []
    async for chunk in storage.get_file_stream(doc.storage_key):
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    if "pdf" in doc.mime_type.lower():
        try:
            pdf_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            total_pages = len(pdf_doc)
            if page_number < 1 or page_number > total_pages:
                pdf_doc.close()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Page {page_number} does not exist (document has {total_pages} page(s)).",
                )
            page = pdf_doc.load_page(page_number - 1)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")
            pdf_doc.close()
            return Response(
                content=img_bytes,
                media_type="image/jpeg",
                headers={
                    "X-Total-Pages": str(total_pages),
                    "X-Current-Page": str(page_number),
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "ETag": f'"{doc.sha256_checksum}-{page_number}"',
                },
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to render PDF page {page_number}: {e}",
            )
    else:
        # Non-PDF (JPG, PNG) single-page document
        if page_number != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image documents only have page 1.",
            )
        return Response(
            content=file_bytes,
            media_type=doc.mime_type,
            headers={
                "X-Total-Pages": "1",
                "X-Current-Page": "1",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "ETag": f'"{doc.sha256_checksum}-1"',
            },
        )
