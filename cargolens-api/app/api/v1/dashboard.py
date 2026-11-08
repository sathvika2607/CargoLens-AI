from typing import Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentProcessingStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.models.field_review import DocumentFieldReview
from app.schemas.shipment import ShipmentResponse
from app.schemas.dashboard import (
    DashboardStatsResponse,
    ExecutiveDashboardStats,
    ManagerDashboardStats,
    RecentActivityItem,
)

router = APIRouter(tags=["Role-Aware Operations Dashboard"])


@router.get(
    "/dashboard/stats",
    response_model=DashboardStatsResponse,
    summary="Get Role-Aware Dashboard Statistics",
    description="Returns authenticated live metrics, breakdown stats, and recent activity for the current user's role.",
)
async def get_dashboard_stats(
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    if current_user.role == UserRole.DOCUMENTATION_EXECUTIVE:
        # Executive stats: Shared Customs Operations Workspace metrics
        my_shipments_q = select(func.count(Shipment.id))
        my_shipments_cnt = int((await session.execute(my_shipments_q)).scalar() or 0)

        docs_uploaded_q = select(func.count(Document.id)).where(Document.is_active == True)
        docs_uploaded_cnt = int((await session.execute(docs_uploaded_q)).scalar() or 0)

        in_prog_q = select(func.count(Document.id)).where(
            Document.is_active == True,
            Document.processing_status == DocumentProcessingStatus.PROCESSING,
        )
        in_prog_cnt = int((await session.execute(in_prog_q)).scalar() or 0)

        awaiting_rev_q = select(func.count(Shipment.id)).where(
            Shipment.status == ShipmentStatus.REVIEW_REQUIRED,
        )
        awaiting_rev_cnt = int((await session.execute(awaiting_rev_q)).scalar() or 0)

        val_failures_q = select(func.count(func.distinct(ShipmentValidationResult.shipment_id))).where(
            ShipmentValidationResult.outcome == ValidationOutcome.FAIL,
        )
        val_failures_cnt = int((await session.execute(val_failures_q)).scalar() or 0)

        recent_shipments_stmt = (
            select(Shipment)
            .order_by(Shipment.updated_at.desc())
            .limit(5)
        )
        recent_shipments = (await session.execute(recent_shipments_stmt)).scalars().all()

        # Shared operational review activity
        rev_stmt = (
            select(DocumentFieldReview, Shipment.shipment_number, User.full_name)
            .join(Shipment, DocumentFieldReview.shipment_id == Shipment.id)
            .outerjoin(User, DocumentFieldReview.reviewer_id == User.id)
            .order_by(DocumentFieldReview.created_at.desc())
            .limit(5)
        )
        recent_reviews = (await session.execute(rev_stmt)).all()
        recent_activity: List[RecentActivityItem] = [
            RecentActivityItem(
                id=str(r[0].id),
                action_type=f"FIELD_{r[0].action.value}",
                description=f"{r[0].action.value.capitalize()} field '{r[0].field_name}' on shipment {r[1]}",
                actor_name=r[2] or "Customs Officer",
                shipment_id=r[0].shipment_id,
                shipment_number=r[1],
                created_at=r[0].created_at.isoformat(),
            )
            for r in recent_reviews
        ]

        return DashboardStatsResponse(
            role=current_user.role.value,
            executive=ExecutiveDashboardStats(
                my_shipments_count=my_shipments_cnt,
                documents_uploaded_count=docs_uploaded_cnt,
                processing_in_progress_count=in_prog_cnt,
                documents_awaiting_review_count=awaiting_rev_cnt,
                validation_failures_count=val_failures_cnt,
                recent_shipments=[ShipmentResponse.model_validate(s) for s in recent_shipments],
                recent_activity=recent_activity,
            ),
        )

    else:
        # Manager stats: Organization-wide
        total_shipments_q = select(func.count(Shipment.id))
        total_shipments_cnt = int((await session.execute(total_shipments_q)).scalar() or 0)

        # Status breakdown
        status_q = select(Shipment.status, func.count(Shipment.id)).group_by(Shipment.status)
        status_rows = (await session.execute(status_q)).all()
        status_map: Dict[str, int] = {st.value: 0 for st in ShipmentStatus}
        for st_val, cnt in status_rows:
            status_map[st_val.value] = int(cnt)

        awaiting_rev_cnt = status_map.get(ShipmentStatus.REVIEW_REQUIRED.value, 0)

        val_failures_q = select(func.count(func.distinct(ShipmentValidationResult.shipment_id))).where(
            ShipmentValidationResult.outcome == ValidationOutcome.FAIL
        )
        val_failures_cnt = int((await session.execute(val_failures_q)).scalar() or 0)

        proc_failures_q = select(func.count(Document.id)).where(
            Document.processing_status == DocumentProcessingStatus.FAILED,
            Document.is_active == True,
        )
        proc_failures_cnt = int((await session.execute(proc_failures_q)).scalar() or 0)

        recent_shipments_stmt = (
            select(Shipment)
            .order_by(Shipment.updated_at.desc())
            .limit(5)
        )
        recent_shipments = (await session.execute(recent_shipments_stmt)).scalars().all()

        rev_stmt = (
            select(DocumentFieldReview, Shipment.shipment_number, User.full_name)
            .join(Shipment, DocumentFieldReview.shipment_id == Shipment.id)
            .outerjoin(User, DocumentFieldReview.reviewer_id == User.id)
            .order_by(DocumentFieldReview.created_at.desc())
            .limit(5)
        )
        recent_reviews = (await session.execute(rev_stmt)).all()
        recent_activity: List[RecentActivityItem] = [
            RecentActivityItem(
                id=str(r[0].id),
                action_type=f"FIELD_{r[0].action.value}",
                description=f"{r[0].action.value.capitalize()} field '{r[0].field_name}' on shipment {r[1]}",
                actor_name=r[2] or "Customs Officer",
                shipment_id=r[0].shipment_id,
                shipment_number=r[1],
                created_at=r[0].created_at.isoformat(),
            )
            for r in recent_reviews
        ]

        return DashboardStatsResponse(
            role=current_user.role.value,
            manager=ManagerDashboardStats(
                total_shipments_count=total_shipments_cnt,
                shipments_by_status=status_map,
                documents_awaiting_review_count=awaiting_rev_cnt,
                validation_failures_count=val_failures_cnt,
                processing_failures_count=proc_failures_cnt,
                recent_shipments=[ShipmentResponse.model_validate(s) for s in recent_shipments],
                recent_activity=recent_activity,
            ),
        )
