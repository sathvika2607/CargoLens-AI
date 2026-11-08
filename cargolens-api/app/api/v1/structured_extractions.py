from typing import Optional, Tuple, Dict, Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.schemas.structured_extraction import (
    StructuredExtractionResponse,
    StructuredExtractionHistoryResponse,
    StructuredExtractionHistoryItem,
    FieldEvidenceResponse,
    BoundingBox,
)
from app.services.ai.service import StructuredExtractionService

router = APIRouter(tags=["AI Structured Document Extraction"])


async def _get_authorized_document_context(
    document_id: UUID,
    current_user: User,
    session: AsyncSession,
    shipment_id: Optional[UUID] = None,
) -> Tuple[Shipment, Document]:
    """
    Verifies that the document and parent shipment exist, and enforces RBAC ownership.
    If the user is Documentation Executive, the shipment must belong to them.
    Returns HTTP 404 for missing or unowned shipments/documents.
    """
    doc_stmt = select(Document).where(and_(Document.id == document_id, Document.is_active == True))
    if shipment_id:
        doc_stmt = doc_stmt.where(Document.shipment_id == shipment_id)

    doc_res = await session.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    shipment_stmt = select(Shipment).where(Shipment.id == doc.shipment_id)
    shipment_res = await session.execute(shipment_stmt)
    shipment = shipment_res.scalar_one_or_none()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment for document '{document_id}' not found.",
        )

    return shipment, doc


def _find_field_in_dict(data: Dict[str, Any], field_name: str) -> Optional[Dict[str, Any]]:
    """Traverses data dictionary to find the target field dictionary."""
    if field_name in data and isinstance(data[field_name], dict):
        return data[field_name]

    # Check dot-notation (e.g. line_items[0].description)
    parts = field_name.split(".")
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
            curr = curr[int(part)]
        else:
            return None
    if isinstance(curr, dict):
        return curr
    return None


@router.post(
    "/shipments/{shipment_id}/documents/{document_id}/structured-extraction",
    response_model=StructuredExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI Structured Document Extraction",
    description="Extracts structured fields from the document using the provider-neutral AI engine.",
)
async def trigger_structured_extraction(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> StructuredExtractionResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
        shipment_id=shipment_id,
    )

    ai_service = StructuredExtractionService()
    extraction = await ai_service.execute_extraction(session, doc)

    return StructuredExtractionResponse(
        id=extraction.id,
        document_id=extraction.document_id,
        document_type=extraction.document_type,
        attempt_number=extraction.attempt_number,
        status=extraction.status.value,
        provider=extraction.provider,
        model=extraction.model,
        extraction_mode=extraction.extraction_mode,
        total_page_count=extraction.total_page_count,
        processed_page_count=extraction.processed_page_count,
        extracted_data=extraction.extracted_data,
        field_confidence_summary=extraction.field_confidence_summary,
        error_summary=extraction.error_summary,
        started_at=extraction.started_at.isoformat() if extraction.started_at else None,
        completed_at=extraction.completed_at.isoformat() if extraction.completed_at else None,
        created_at=extraction.created_at.isoformat(),
    )


@router.post(
    "/documents/{document_id}/structured-extraction",
    response_model=StructuredExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI Structured Document Extraction (Direct)",
)
async def trigger_structured_extraction_direct(
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> StructuredExtractionResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
    )

    ai_service = StructuredExtractionService()
    extraction = await ai_service.execute_extraction(session, doc)

    return StructuredExtractionResponse(
        id=extraction.id,
        document_id=extraction.document_id,
        document_type=extraction.document_type,
        attempt_number=extraction.attempt_number,
        status=extraction.status.value,
        provider=extraction.provider,
        model=extraction.model,
        extraction_mode=extraction.extraction_mode,
        total_page_count=extraction.total_page_count,
        processed_page_count=extraction.processed_page_count,
        extracted_data=extraction.extracted_data,
        field_confidence_summary=extraction.field_confidence_summary,
        error_summary=extraction.error_summary,
        started_at=extraction.started_at.isoformat() if extraction.started_at else None,
        completed_at=extraction.completed_at.isoformat() if extraction.completed_at else None,
        created_at=extraction.created_at.isoformat(),
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/structured-extraction",
    response_model=StructuredExtractionResponse,
    summary="Get Latest Structured Extraction",
)
async def get_latest_structured_extraction(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> StructuredExtractionResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
        shipment_id=shipment_id,
    )

    stmt = (
        select(StructuredExtraction)
        .where(StructuredExtraction.document_id == doc.id)
        .order_by(StructuredExtraction.attempt_number.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    ext = res.scalar_one_or_none()

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No structured extraction found for document '{document_id}'.",
        )

    return StructuredExtractionResponse(
        id=ext.id,
        document_id=ext.document_id,
        document_type=ext.document_type,
        attempt_number=ext.attempt_number,
        status=ext.status.value,
        provider=ext.provider,
        model=ext.model,
        extraction_mode=ext.extraction_mode,
        total_page_count=ext.total_page_count,
        processed_page_count=ext.processed_page_count,
        extracted_data=ext.extracted_data,
        field_confidence_summary=ext.field_confidence_summary,
        error_summary=ext.error_summary,
        started_at=ext.started_at.isoformat() if ext.started_at else None,
        completed_at=ext.completed_at.isoformat() if ext.completed_at else None,
        created_at=ext.created_at.isoformat(),
    )


@router.get(
    "/documents/{document_id}/structured-extraction",
    response_model=StructuredExtractionResponse,
    summary="Get Latest Structured Extraction (Direct)",
)
async def get_latest_structured_extraction_direct(
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> StructuredExtractionResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
    )

    stmt = (
        select(StructuredExtraction)
        .where(StructuredExtraction.document_id == doc.id)
        .order_by(StructuredExtraction.attempt_number.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    ext = res.scalar_one_or_none()

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No structured extraction found for document '{document_id}'.",
        )

    return StructuredExtractionResponse(
        id=ext.id,
        document_id=ext.document_id,
        document_type=ext.document_type,
        attempt_number=ext.attempt_number,
        status=ext.status.value,
        provider=ext.provider,
        model=ext.model,
        extraction_mode=ext.extraction_mode,
        total_page_count=ext.total_page_count,
        processed_page_count=ext.processed_page_count,
        extracted_data=ext.extracted_data,
        field_confidence_summary=ext.field_confidence_summary,
        error_summary=ext.error_summary,
        started_at=ext.started_at.isoformat() if ext.started_at else None,
        completed_at=ext.completed_at.isoformat() if ext.completed_at else None,
        created_at=ext.created_at.isoformat(),
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/structured-extraction/history",
    response_model=StructuredExtractionHistoryResponse,
    summary="Get Structured Extraction History",
)
async def get_structured_extraction_history(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> StructuredExtractionHistoryResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
        shipment_id=shipment_id,
    )

    stmt = (
        select(StructuredExtraction)
        .where(StructuredExtraction.document_id == doc.id)
        .order_by(StructuredExtraction.attempt_number.desc())
    )
    res = await session.execute(stmt)
    items = res.scalars().all()

    history = [
        StructuredExtractionHistoryItem(
            id=item.id,
            attempt_number=item.attempt_number,
            status=item.status.value,
            provider=item.provider,
            model=item.model,
            extraction_mode=item.extraction_mode,
            total_page_count=item.total_page_count,
            processed_page_count=item.processed_page_count,
            error_summary=item.error_summary,
            completed_at=item.completed_at.isoformat() if item.completed_at else None,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]

    return StructuredExtractionHistoryResponse(
        document_id=doc.id,
        total_attempts=len(history),
        history=history,
    )


@router.get(
    "/documents/{document_id}/structured-extraction/history",
    response_model=StructuredExtractionHistoryResponse,
    summary="Get Structured Extraction History (Direct)",
)
async def get_structured_extraction_history_direct(
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> StructuredExtractionHistoryResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
    )

    stmt = (
        select(StructuredExtraction)
        .where(StructuredExtraction.document_id == doc.id)
        .order_by(StructuredExtraction.attempt_number.desc())
    )
    res = await session.execute(stmt)
    items = res.scalars().all()

    history = [
        StructuredExtractionHistoryItem(
            id=item.id,
            attempt_number=item.attempt_number,
            status=item.status.value,
            provider=item.provider,
            model=item.model,
            extraction_mode=item.extraction_mode,
            total_page_count=item.total_page_count,
            processed_page_count=item.processed_page_count,
            error_summary=item.error_summary,
            completed_at=item.completed_at.isoformat() if item.completed_at else None,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]

    return StructuredExtractionHistoryResponse(
        document_id=doc.id,
        total_attempts=len(history),
        history=history,
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/structured-extraction/{extraction_id}/fields/{field_name}/evidence",
    response_model=FieldEvidenceResponse,
    summary="Get Field Evidence and Source Provenance",
)
async def get_field_evidence(
    shipment_id: UUID,
    document_id: UUID,
    extraction_id: UUID,
    field_name: str,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> FieldEvidenceResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
        shipment_id=shipment_id,
    )

    stmt = select(StructuredExtraction).where(
        and_(
            StructuredExtraction.id == extraction_id,
            StructuredExtraction.document_id == doc.id,
        )
    )
    res = await session.execute(stmt)
    ext = res.scalar_one_or_none()
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction '{extraction_id}' not found for document '{document_id}'.",
        )

    if not ext.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction '{extraction_id}' has no extracted data.",
        )

    field_obj = _find_field_in_dict(ext.extracted_data, field_name)
    if not field_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_name}' not found in extraction '{extraction_id}'.",
        )

    bbox_data = field_obj.get("bounding_box")
    bbox = BoundingBox(**bbox_data) if bbox_data else None

    return FieldEvidenceResponse(
        field_name=field_name,
        value=field_obj.get("value"),
        normalized_value=field_obj.get("normalized_value"),
        confidence=field_obj.get("confidence"),
        source_document_id=doc.id,
        source_page_number=field_obj.get("source_page_number"),
        evidence_text=field_obj.get("evidence_text"),
        bounding_box=bbox,
        extraction_method=field_obj.get("extraction_method") or ext.extraction_mode,
    )


@router.get(
    "/documents/{document_id}/structured-extraction/{extraction_id}/fields/{field_name}/evidence",
    response_model=FieldEvidenceResponse,
    summary="Get Field Evidence and Source Provenance (Direct)",
)
async def get_field_evidence_direct(
    document_id: UUID,
    extraction_id: UUID,
    field_name: str,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> FieldEvidenceResponse:
    _, doc = await _get_authorized_document_context(
        document_id=document_id,
        current_user=current_user,
        session=session,
    )

    stmt = select(StructuredExtraction).where(
        and_(
            StructuredExtraction.id == extraction_id,
            StructuredExtraction.document_id == doc.id,
        )
    )
    res = await session.execute(stmt)
    ext = res.scalar_one_or_none()
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction '{extraction_id}' not found for document '{document_id}'.",
        )

    if not ext.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction '{extraction_id}' has no extracted data.",
        )

    field_obj = _find_field_in_dict(ext.extracted_data, field_name)
    if not field_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_name}' not found in extraction '{extraction_id}'.",
        )

    bbox_data = field_obj.get("bounding_box")
    bbox = BoundingBox(**bbox_data) if bbox_data else None

    return FieldEvidenceResponse(
        field_name=field_name,
        value=field_obj.get("value"),
        normalized_value=field_obj.get("normalized_value"),
        confidence=field_obj.get("confidence"),
        source_document_id=doc.id,
        source_page_number=field_obj.get("source_page_number"),
        evidence_text=field_obj.get("evidence_text"),
        bounding_box=bbox,
        extraction_method=field_obj.get("extraction_method") or ext.extraction_mode,
    )
