from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document
from app.models.structured_extraction import StructuredExtraction
from app.models.field_review import DocumentFieldReview, FieldReviewActionType, ReviewProvenance
from app.schemas.field_review import (
    FieldReviewCreate,
    FieldReviewResponse,
    FieldReviewListResponse,
)

router = APIRouter(tags=["Document Field Review & Corrections"])


async def _get_authorized_shipment_and_doc(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> tuple[Shipment, Document]:
    """Verifies existence in the shared workspace."""
    shipment_stmt = select(Shipment).where(Shipment.id == shipment_id)
    shipment_res = await session.execute(shipment_stmt)
    shipment = shipment_res.scalar_one_or_none()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found or access denied.",
        )

    doc_stmt = select(Document).where(
        Document.id == document_id,
        Document.shipment_id == shipment_id,
        Document.is_active == True,
    )
    doc_res = await session.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found in shipment '{shipment_id}'.",
        )

    return shipment, doc


def _find_field_value_in_extraction(extracted_data: dict, field_name: str) -> Optional[str]:
    """Extracts original value string from structured extraction dict."""
    if not extracted_data:
        return None
    if field_name in extracted_data and isinstance(extracted_data[field_name], dict):
        val = extracted_data[field_name].get("value")
        return str(val) if val is not None else None

    # Handle dotted paths (e.g. line_items[0].description)
    parts = field_name.split(".")
    curr = extracted_data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
            curr = curr[int(part)]
        else:
            return None
    if isinstance(curr, dict):
        val = curr.get("value")
        return str(val) if val is not None else None
    return str(curr) if curr is not None else None


@router.post(
    "/shipments/{shipment_id}/documents/{document_id}/reviews",
    response_model=FieldReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Human Field Confirmation or Correction",
    description="Records a human confirmation or correction of an extracted field, preserving original AI provenance.",
)
async def create_field_review(
    shipment_id: UUID,
    document_id: UUID,
    payload: FieldReviewCreate,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> FieldReviewResponse:
    shipment, doc = await _get_authorized_shipment_and_doc(shipment_id, document_id, current_user, session)

    # Fetch latest structured extraction for this document to capture original AI value
    ext_stmt = (
        select(StructuredExtraction)
        .where(StructuredExtraction.document_id == doc.id)
        .order_by(StructuredExtraction.attempt_number.desc())
        .limit(1)
    )
    ext_res = await session.execute(ext_stmt)
    latest_ext = ext_res.scalar_one_or_none()

    original_val = _find_field_value_in_extraction(latest_ext.extracted_data, payload.field_name) if latest_ext else None

    review = DocumentFieldReview(
        shipment_id=shipment.id,
        document_id=doc.id,
        extraction_id=latest_ext.id if latest_ext else None,
        field_name=payload.field_name,
        action=payload.action,
        provenance=ReviewProvenance.USER_ACTION,
        original_value=original_val,
        corrected_value=payload.corrected_value if payload.action == FieldReviewActionType.CORRECTED else original_val,
        reason=payload.reason,
        reviewer_id=current_user.id,
    )
    session.add(review)

    # Update shipment status to REVIEW_REQUIRED if currently in CREATED, DOCUMENTS_PENDING, or PROCESSING
    if shipment.status in (ShipmentStatus.CREATED, ShipmentStatus.DOCUMENTS_PENDING, ShipmentStatus.PROCESSING):
        shipment.status = ShipmentStatus.REVIEW_REQUIRED

    await session.commit()
    await session.refresh(review)

    return FieldReviewResponse(
        id=review.id,
        shipment_id=review.shipment_id,
        document_id=review.document_id,
        extraction_id=review.extraction_id,
        field_name=review.field_name,
        action=review.action,
        provenance=review.provenance,
        original_value=review.original_value,
        corrected_value=review.corrected_value,
        reason=review.reason,
        reviewer_id=review.reviewer_id,
        reviewer_name=current_user.full_name,
        reviewer_email=current_user.email,
        created_at=review.created_at.isoformat(),
    )


@router.get(
    "/shipments/{shipment_id}/documents/{document_id}/reviews",
    response_model=FieldReviewListResponse,
    summary="List Document Field Reviews",
    description="Retrieves all human confirmation and correction reviews for a specific document.",
)
async def list_document_reviews(
    shipment_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> FieldReviewListResponse:
    await _get_authorized_shipment_and_doc(shipment_id, document_id, current_user, session)

    stmt = (
        select(DocumentFieldReview)
        .options(selectinload(DocumentFieldReview.reviewer))
        .where(
            DocumentFieldReview.shipment_id == shipment_id,
            DocumentFieldReview.document_id == document_id,
        )
        .order_by(DocumentFieldReview.created_at.desc())
    )
    res = await session.execute(stmt)
    reviews = res.scalars().all()

    items = [
        FieldReviewResponse(
            id=r.id,
            shipment_id=r.shipment_id,
            document_id=r.document_id,
            extraction_id=r.extraction_id,
            field_name=r.field_name,
            action=r.action,
            provenance=r.provenance,
            original_value=r.original_value,
            corrected_value=r.corrected_value,
            reason=r.reason,
            reviewer_id=r.reviewer_id,
            reviewer_name=r.reviewer.full_name if r.reviewer else None,
            reviewer_email=r.reviewer.email if r.reviewer else None,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]
    return FieldReviewListResponse(items=items, total=len(items))


@router.get(
    "/shipments/{shipment_id}/review-history",
    response_model=FieldReviewListResponse,
    summary="Get Full Shipment Review Audit History",
    description="Retrieves all human field reviews, confirmations, and corrections across all documents in a shipment.",
)
async def get_shipment_review_history(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> FieldReviewListResponse:
    # Verify shipment exists in shared workspace
    shipment_stmt = select(Shipment).where(Shipment.id == shipment_id)
    shipment_res = await session.execute(shipment_stmt)
    shipment = shipment_res.scalar_one_or_none()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found or access denied.",
        )

    stmt = (
        select(DocumentFieldReview)
        .options(selectinload(DocumentFieldReview.reviewer))
        .where(DocumentFieldReview.shipment_id == shipment_id)
        .order_by(DocumentFieldReview.created_at.desc())
    )
    res = await session.execute(stmt)
    reviews = res.scalars().all()

    items = [
        FieldReviewResponse(
            id=r.id,
            shipment_id=r.shipment_id,
            document_id=r.document_id,
            extraction_id=r.extraction_id,
            field_name=r.field_name,
            action=r.action,
            provenance=r.provenance,
            original_value=r.original_value,
            corrected_value=r.corrected_value,
            reason=r.reason,
            reviewer_id=r.reviewer_id,
            reviewer_name=r.reviewer.full_name if r.reviewer else None,
            reviewer_email=r.reviewer.email if r.reviewer else None,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]
    return FieldReviewListResponse(items=items, total=len(items))


@router.get(
    "/review/audit-history",
    response_model=FieldReviewListResponse,
    summary="Get Global Review Audit History",
    description="Retrieves recent human review and correction actions across shipments, filtered by role.",
)
async def get_global_audit_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> FieldReviewListResponse:
    stmt = (
        select(DocumentFieldReview)
        .options(selectinload(DocumentFieldReview.reviewer))
        .join(Shipment, DocumentFieldReview.shipment_id == Shipment.id)
    )
    stmt = stmt.order_by(DocumentFieldReview.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    reviews = res.scalars().all()

    items = [
        FieldReviewResponse(
            id=r.id,
            shipment_id=r.shipment_id,
            document_id=r.document_id,
            extraction_id=r.extraction_id,
            field_name=r.field_name,
            action=r.action,
            provenance=r.provenance,
            original_value=r.original_value,
            corrected_value=r.corrected_value,
            reason=r.reason,
            reviewer_id=r.reviewer_id,
            reviewer_name=r.reviewer.full_name if r.reviewer else None,
            reviewer_email=r.reviewer.email if r.reviewer else None,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]
    return FieldReviewListResponse(items=items, total=len(items))
