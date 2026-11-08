from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment
from app.models.validation import ShipmentValidationResult, ValidationOutcome, ValidationSeverity
from app.schemas.validation import (
    ValidationResultResponse,
    ShipmentValidationsSummaryResponse,
    ValidationIssueItem,
    ValidationIssuesListResponse,
)
from app.services.validation.engine import CrossDocumentValidationEngine

router = APIRouter(tags=["Cross-Document Validation Engine"])


async def _get_authorized_shipment(
    shipment_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> Shipment:
    """Verifies shipment exists in shared workspace."""
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    res = await session.execute(stmt)
    shipment = res.scalar_one_or_none()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found or access denied.",
        )
    return shipment


def _build_summary(
    shipment_id: UUID,
    results: List[ShipmentValidationResult],
) -> ShipmentValidationsSummaryResponse:
    run_id: Optional[UUID] = results[0].run_id if results else None
    passed = sum(1 for r in results if r.outcome == ValidationOutcome.PASS)
    failed = sum(1 for r in results if r.outcome == ValidationOutcome.FAIL)
    missing = sum(1 for r in results if r.outcome == ValidationOutcome.MISSING_DATA)
    not_app = sum(1 for r in results if r.outcome == ValidationOutcome.NOT_APPLICABLE)
    info = sum(1 for r in results if r.outcome == ValidationOutcome.INFO)

    dtos = [
        ValidationResultResponse(
            id=r.id,
            shipment_id=r.shipment_id,
            run_id=r.run_id,
            rule_id=r.rule_id,
            rule_name=r.rule_name,
            severity=r.severity,
            outcome=r.outcome,
            explanation=r.explanation,
            compared_values=r.compared_values,
            source_document_ids=r.source_document_ids,
            created_at=r.created_at.isoformat(),
        )
        for r in results
    ]

    return ShipmentValidationsSummaryResponse(
        shipment_id=shipment_id,
        run_id=run_id,
        total_rules=len(results),
        passed_count=passed,
        failed_count=failed,
        missing_data_count=missing,
        not_applicable_count=not_app,
        info_count=info,
        has_blocking_failures=(failed > 0),
        results=dtos,
    )


@router.get(
    "/shipments/{shipment_id}/validations",
    response_model=ShipmentValidationsSummaryResponse,
    summary="Get Latest Cross-Document Validation Results",
    description="Retrieves the results from the most recent deterministic cross-document validation run for a shipment.",
)
async def get_validation_results(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentValidationsSummaryResponse:
    await _get_authorized_shipment(shipment_id, current_user, session)

    engine = CrossDocumentValidationEngine()
    results = await engine.get_latest_validation_results(session, shipment_id)
    return _build_summary(shipment_id, results)


@router.post(
    "/shipments/{shipment_id}/validations/run",
    response_model=ShipmentValidationsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Cross-Document Validation Run",
    description="Executes deterministic cross-document comparison rules across all latest extracted shipment documents.",
)
async def run_validations(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentValidationsSummaryResponse:
    await _get_authorized_shipment(shipment_id, current_user, session)

    engine = CrossDocumentValidationEngine()
    results = await engine.run_validation(session, shipment_id)
    return _build_summary(shipment_id, results)


@router.get(
    "/validations/issues",
    response_model=ValidationIssuesListResponse,
    summary="List Cross-Document Validation Issues",
    description="Queries cross-document validation issues across shipments with optional filtering by severity and outcome.",
)
async def list_validation_issues(
    shipment_id: Optional[UUID] = None,
    severity: Optional[ValidationSeverity] = None,
    outcome: Optional[ValidationOutcome] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ValidationIssuesListResponse:
    stmt = (
        select(
            ShipmentValidationResult,
            Shipment.shipment_number,
            Shipment.client_name,
        )
        .join(Shipment, ShipmentValidationResult.shipment_id == Shipment.id)
    )

    if shipment_id:
        stmt = stmt.where(Shipment.id == shipment_id)

    if outcome:
        stmt = stmt.where(ShipmentValidationResult.outcome == outcome)
    else:
        # Default: show issues (FAIL and MISSING_DATA), excluding PASS
        stmt = stmt.where(ShipmentValidationResult.outcome.in_([ValidationOutcome.FAIL, ValidationOutcome.MISSING_DATA]))

    if severity:
        stmt = stmt.where(ShipmentValidationResult.severity == severity)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await session.execute(count_stmt)).scalar() or 0)

    # Order and paginate
    stmt = stmt.order_by(ShipmentValidationResult.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()

    items = [
        ValidationIssueItem(
            id=r[0].id,
            shipment_id=r[0].shipment_id,
            shipment_number=r[1],
            client_name=r[2],
            run_id=r[0].run_id,
            rule_id=r[0].rule_id,
            rule_name=r[0].rule_name,
            severity=r[0].severity,
            outcome=r[0].outcome,
            explanation=r[0].explanation,
            compared_values=r[0].compared_values,
            source_document_ids=r[0].source_document_ids,
            created_at=r[0].created_at.isoformat(),
        )
        for r in rows
    ]

    return ValidationIssuesListResponse(items=items, total=total)
