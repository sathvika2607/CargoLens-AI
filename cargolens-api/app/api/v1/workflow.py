from typing import List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.structured_extraction import StructuredExtraction
from app.models.extraction import ExtractionStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.models.field_review import DocumentFieldReview, FieldReviewActionType, ReviewProvenance
from app.schemas.shipment import ShipmentResponse
from app.schemas.workflow import VerificationReadinessResponse, VerifyShipmentResponse

router = APIRouter(tags=["Shipment Verification Workflow"])

REQUIRED_DOC_TYPES = [
    DocumentType.COMMERCIAL_INVOICE,
    DocumentType.PACKING_LIST,
    DocumentType.BILL_OF_LADING,
]

MANDATORY_FIELDS_BY_DOC_TYPE: Dict[DocumentType, List[str]] = {
    DocumentType.COMMERCIAL_INVOICE: [
        "invoice_number",
        "invoice_date",
        "seller_name",
        "buyer_name",
        "grand_total",
        "currency",
    ],
    DocumentType.PACKING_LIST: [
        "invoice_reference",
        "package_count",
        "gross_weight_kg",
    ],
    DocumentType.BILL_OF_LADING: [
        "bl_number",
        "shipper_name",
        "consignee_name",
        "gross_weight_kg",
    ],
}


async def _get_authorized_shipment(
    shipment_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> Shipment:
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    res = await session.execute(stmt)
    shipment = res.scalar_one_or_none()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found or access denied.",
        )
    return shipment


async def evaluate_readiness(
    shipment: Shipment,
    session: AsyncSession,
) -> VerificationReadinessResponse:
    # 1. Fetch active documents for shipment
    docs_stmt = (
        select(Document)
        .where(
            Document.shipment_id == shipment.id,
            Document.is_active == True,
        )
        .order_by(Document.version.desc())
    )
    docs_res = await session.execute(docs_stmt)
    docs = docs_res.scalars().all()

    # Index latest document per document type
    docs_by_type: Dict[DocumentType, Document] = {}
    for d in docs:
        if d.document_type not in docs_by_type:
            docs_by_type[d.document_type] = d

    documents_present = {
        dt.value: (dt in docs_by_type) for dt in REQUIRED_DOC_TYPES
    }
    missing_docs = [dt.value for dt in REQUIRED_DOC_TYPES if dt not in docs_by_type]
    all_docs_present = len(missing_docs) == 0

    # 2. Check structured extractions and mandatory human reviews
    all_extractions_completed = True
    unreviewed_mandatory_fields: List[str] = []
    missing_requirements: List[str] = []

    # Fetch all human reviews for this shipment ordered latest first
    all_reviews_stmt = (
        select(DocumentFieldReview)
        .where(DocumentFieldReview.shipment_id == shipment.id)
        .order_by(DocumentFieldReview.created_at.desc())
    )
    all_reviews_res = await session.execute(all_reviews_stmt)
    all_reviews = all_reviews_res.scalars().all()

    # Distinguish genuine USER_ACTION reviews from synthetic DEMO_SEED fixtures.
    # Security requirement: Only genuine USER_ACTION reviews can satisfy human approval gates.
    user_action_reviews = [
        r for r in all_reviews if r.provenance == ReviewProvenance.USER_ACTION
    ]

    # Map latest USER_ACTION review per (document_id, field_name)
    latest_user_reviews_by_doc_field: Dict[tuple[UUID, str], DocumentFieldReview] = {}
    for r in user_action_reviews:
        k = (r.document_id, r.field_name)
        if k not in latest_user_reviews_by_doc_field:
            latest_user_reviews_by_doc_field[k] = r

    # Map latest review of any provenance for descriptive auditing and provenance diagnostics
    latest_any_reviews_by_doc_field: Dict[tuple[UUID, str], DocumentFieldReview] = {}
    for r in all_reviews:
        k = (r.document_id, r.field_name)
        if k not in latest_any_reviews_by_doc_field:
            latest_any_reviews_by_doc_field[k] = r

    for doc_type in REQUIRED_DOC_TYPES:
        mandatory_fields = MANDATORY_FIELDS_BY_DOC_TYPE.get(doc_type, [])
        doc = docs_by_type.get(doc_type)

        if not doc:
            for f in mandatory_fields:
                unreviewed_mandatory_fields.append(f"{doc_type.value}.{f}")
            continue

        # Check structured extraction completion
        ext_stmt = (
            select(StructuredExtraction)
            .where(StructuredExtraction.document_id == doc.id)
            .order_by(StructuredExtraction.attempt_number.desc())
            .limit(1)
        )
        latest_ext = (await session.execute(ext_stmt)).scalar_one_or_none()

        if not latest_ext or latest_ext.status != ExtractionStatus.COMPLETED:
            all_extractions_completed = False
            missing_requirements.append(
                f"Structured AI extraction is pending or incomplete for {doc_type.value} ({doc.original_filename})."
            )

        # Evaluate human reviews for each mandatory field
        for f in mandatory_fields:
            field_tag = f"{doc_type.value}.{f}"
            user_review = latest_user_reviews_by_doc_field.get((doc.id, f))

            if user_review is None:
                unreviewed_mandatory_fields.append(field_tag)
                any_review = latest_any_reviews_by_doc_field.get((doc.id, f))
                if any_review is not None and any_review.provenance == ReviewProvenance.DEMO_SEED:
                    missing_requirements.append(
                        f"{doc_type.value}: Mandatory field '{f}' is covered only by a demonstration fixture (DEMO_SEED) and requires genuine human review."
                    )
                else:
                    missing_requirements.append(
                        f"{doc_type.value}: Mandatory field '{f}' must be confirmed or corrected by an authorized human reviewer."
                    )
            else:
                effective_val = (
                    user_review.corrected_value
                    if user_review.action == FieldReviewActionType.CORRECTED
                    else (user_review.corrected_value if user_review.corrected_value is not None else user_review.original_value)
                )
                if effective_val is None or not str(effective_val).strip():
                    unreviewed_mandatory_fields.append(field_tag)
                    missing_requirements.append(
                        f"{doc_type.value}: Mandatory field '{f}' was confirmed without an extracted value. A valid value must be provided via human correction."
                    )

    if not all_docs_present:
        missing_requirements.insert(
            0,
            f"Missing required consignment documents: {', '.join(missing_docs)}."
        )

    # 3. Check blocking validation failures from latest run
    val_stmt = (
        select(ShipmentValidationResult)
        .where(ShipmentValidationResult.shipment_id == shipment.id)
        .order_by(ShipmentValidationResult.created_at.desc())
    )
    val_res = await session.execute(val_stmt)
    all_val_results = val_res.scalars().all()

    blocking_failures = 0
    if all_val_results:
        latest_run_id = all_val_results[0].run_id
        latest_results = [r for r in all_val_results if r.run_id == latest_run_id]
        blocking_failures = sum(1 for r in latest_results if r.outcome == ValidationOutcome.FAIL)
        if blocking_failures > 0:
            missing_requirements.append(
                f"Shipment has {blocking_failures} unresolved blocking cross-document validation failure(s)."
            )
    else:
        missing_requirements.append(
            "Cross-document validation has not yet been executed for this shipment."
        )

    all_mandatory_fields_reviewed = len(unreviewed_mandatory_fields) == 0
    is_ready = len(missing_requirements) == 0

    return VerificationReadinessResponse(
        shipment_id=shipment.id,
        current_status=shipment.status.value,
        is_ready=is_ready,
        documents_present=documents_present,
        documents_missing=missing_docs,
        all_documents_present=all_docs_present,
        all_extractions_completed=all_extractions_completed,
        blocking_validation_failures_count=blocking_failures,
        has_blocking_failures=(blocking_failures > 0),
        human_reviews_count=len(user_action_reviews),
        unreviewed_mandatory_fields=unreviewed_mandatory_fields,
        all_mandatory_fields_reviewed=all_mandatory_fields_reviewed,
        missing_requirements=missing_requirements,
    )


@router.get(
    "/shipments/{shipment_id}/verification-readiness",
    response_model=VerificationReadinessResponse,
    summary="Evaluate Shipment Verification Readiness",
    description="Evaluates whether a shipment satisfies all criteria required for verification approval.",
)
async def get_verification_readiness(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> VerificationReadinessResponse:
    shipment = await _get_authorized_shipment(shipment_id, current_user, session)
    return await evaluate_readiness(shipment, session)


@router.post(
    "/shipments/{shipment_id}/verify",
    response_model=VerifyShipmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Shipment Verification Workflow Action",
    description="Backend-enforced workflow action that verifies a shipment after confirming all readiness criteria are satisfied.",
)
async def verify_shipment_workflow(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> VerifyShipmentResponse:
    shipment = await _get_authorized_shipment(shipment_id, current_user, session)

    if shipment.status == ShipmentStatus.VERIFIED:
        return VerifyShipmentResponse(
            success=True,
            message=f"Shipment '{shipment.shipment_number}' is already verified.",
            shipment=ShipmentResponse.model_validate(shipment),
        )

    readiness = await evaluate_readiness(shipment, session)
    if not readiness.is_ready:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Shipment does not satisfy all verification requirements.",
                "missing_requirements": readiness.missing_requirements,
                "unreviewed_mandatory_fields": readiness.unreviewed_mandatory_fields,
            },
        )

    # Criteria fully satisfied: transition status to VERIFIED
    shipment.status = ShipmentStatus.VERIFIED
    await session.commit()
    await session.refresh(shipment)

    return VerifyShipmentResponse(
        success=True,
        message=f"Shipment '{shipment.shipment_number}' has been successfully verified for customs clearance.",
        shipment=ShipmentResponse.model_validate(shipment),
    )
