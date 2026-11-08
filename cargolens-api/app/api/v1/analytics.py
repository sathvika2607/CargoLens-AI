from datetime import datetime, timezone, time
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, desc, cast, Date
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType, DocumentProcessingStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.models.export import ShipmentExportRecord, ExportStatus
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    TimeSeriesPoint,
    StatusDistributionItem,
    ValidationRuleBreakdownItem,
    ValidationSeverityBreakdownItem,
    ValidationDiscrepancyDetail,
    DocumentTypeBreakdownItem,
    RecentExportActivityItem,
)

router = APIRouter(tags=["Manager & Executive Operational Analytics"])


@router.get(
    "/analytics/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get Authenticated Operational Analytics",
    description="Returns authenticated live PostgreSQL metrics, status distribution, time series volume, validation issues, and export activity for the shared customs documentation workspace.",
)
async def get_analytics_overview(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    interval: Optional[str] = Query("daily", description="Time series interval (daily, weekly, monthly)"),
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> AnalyticsOverviewResponse:
    # 1. Parse date filters if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            d = datetime.strptime(start_date.strip(), "%Y-%m-%d")
            start_dt = datetime.combine(d.date(), time.min, tzinfo=timezone.utc)
        except ValueError:
            pass

    if end_date:
        try:
            d = datetime.strptime(end_date.strip(), "%Y-%m-%d")
            end_dt = datetime.combine(d.date(), time.max, tzinfo=timezone.utc)
        except ValueError:
            pass

    # Helper filters for shipments (Shared Workspace: all consignments accessible)
    shipment_filters = []
    if start_dt:
        shipment_filters.append(Shipment.created_at >= start_dt)
    if end_dt:
        shipment_filters.append(Shipment.created_at <= end_dt)

    # 2. Total shipments
    total_q = select(func.count(Shipment.id))
    if shipment_filters:
        total_q = total_q.where(and_(*shipment_filters))
    total_shipments = int((await session.execute(total_q)).scalar() or 0)

    # 3. Shipments by workflow status
    status_q = select(Shipment.status, func.count(Shipment.id))
    if shipment_filters:
        status_q = status_q.where(and_(*shipment_filters))
    status_q = status_q.group_by(Shipment.status)
    status_rows = (await session.execute(status_q)).all()

    shipments_by_status: Dict[str, int] = {st.value: 0 for st in ShipmentStatus}
    for st_enum, cnt in status_rows:
        shipments_by_status[st_enum.value] = int(cnt)

    status_distribution: List[StatusDistributionItem] = []
    for st_key, cnt in shipments_by_status.items():
        pct = round((cnt / total_shipments * 100.0), 1) if total_shipments > 0 else 0.0
        status_distribution.append(
            StatusDistributionItem(
                status=st_key,
                count=cnt,
                percentage=pct,
            )
        )

    # 4. Documents breakdown (Shared Workspace)
    doc_filters = [Document.is_active == True]
    if start_dt:
        doc_filters.append(Document.created_at >= start_dt)
    if end_dt:
        doc_filters.append(Document.created_at <= end_dt)

    doc_base_q = select(Document.document_type, func.count(Document.id)).join(
        Shipment, Document.shipment_id == Shipment.id
    ).where(and_(*doc_filters)).group_by(Document.document_type)

    doc_type_rows = (await session.execute(doc_base_q)).all()
    docs_by_type_map: Dict[str, int] = {dt.value: 0 for dt in DocumentType}
    for dt_enum, cnt in doc_type_rows:
        docs_by_type_map[dt_enum.value] = int(cnt)

    documents_by_type = [
        DocumentTypeBreakdownItem(document_type=k, count=v)
        for k, v in docs_by_type_map.items()
    ]
    total_documents = sum(docs_by_type_map.values())

    # Processing status breakdown
    proc_q = select(Document.processing_status, func.count(Document.id)).join(
        Shipment, Document.shipment_id == Shipment.id
    ).where(and_(*doc_filters)).group_by(Document.processing_status)
    proc_rows = (await session.execute(proc_q)).all()

    proc_status_map: Dict[str, int] = {ps.value: 0 for ps in DocumentProcessingStatus}
    for ps_enum, cnt in proc_rows:
        proc_status_map[ps_enum.value] = int(cnt)

    awaiting_extraction = (
        proc_status_map.get(DocumentProcessingStatus.PENDING.value, 0)
        + proc_status_map.get(DocumentProcessingStatus.PROCESSING.value, 0)
    )
    extraction_failures = proc_status_map.get(DocumentProcessingStatus.FAILED.value, 0)

    # 5. Review & Validation Metrics
    awaiting_review = shipments_by_status.get(ShipmentStatus.REVIEW_REQUIRED.value, 0)
    verified_cnt = shipments_by_status.get(ShipmentStatus.VERIFIED.value, 0)
    exported_cnt = shipments_by_status.get(ShipmentStatus.EXPORTED.value, 0)
    missing_data_issues = shipments_by_status.get(ShipmentStatus.DOCUMENTS_PENDING.value, 0)

    # Validation failures breakdown (Shared Workspace)
    val_filters = [ShipmentValidationResult.outcome == ValidationOutcome.FAIL]
    if start_dt:
        val_filters.append(ShipmentValidationResult.created_at >= start_dt)
    if end_dt:
        val_filters.append(ShipmentValidationResult.created_at <= end_dt)

    val_rule_q = (
        select(
            ShipmentValidationResult.rule_id,
            ShipmentValidationResult.rule_name,
            ShipmentValidationResult.severity,
            func.count(ShipmentValidationResult.id),
        )
        .join(Shipment, ShipmentValidationResult.shipment_id == Shipment.id)
        .where(and_(*val_filters))
        .group_by(
            ShipmentValidationResult.rule_id,
            ShipmentValidationResult.rule_name,
            ShipmentValidationResult.severity,
        )
        .order_by(func.count(ShipmentValidationResult.id).desc())
    )
    val_rule_rows = (await session.execute(val_rule_q)).all()

    validation_issues_by_rule = [
        ValidationRuleBreakdownItem(
            rule_id=r[0],
            rule_name=r[1],
            severity=r[2].value if hasattr(r[2], "value") else str(r[2]),
            failure_count=int(r[3]),
        )
        for r in val_rule_rows
    ]
    val_failures_total = sum(item.failure_count for item in validation_issues_by_rule)

    # Validation failures breakdown by severity
    val_sev_q = (
        select(
            ShipmentValidationResult.severity,
            func.count(ShipmentValidationResult.id),
        )
        .join(Shipment, ShipmentValidationResult.shipment_id == Shipment.id)
        .where(and_(*val_filters))
        .group_by(ShipmentValidationResult.severity)
        .order_by(func.count(ShipmentValidationResult.id).desc())
    )
    val_sev_rows = (await session.execute(val_sev_q)).all()
    validation_issues_by_severity = [
        ValidationSeverityBreakdownItem(
            severity=r[0].value if hasattr(r[0], "value") else str(r[0]),
            count=int(r[1]),
        )
        for r in val_sev_rows
    ]

    # Validation discrepancy detail items (for inspection and direct review navigation)
    val_disc_q = (
        select(
            ShipmentValidationResult.id,
            ShipmentValidationResult.shipment_id,
            Shipment.shipment_number,
            Shipment.client_name,
            ShipmentValidationResult.rule_id,
            ShipmentValidationResult.rule_name,
            ShipmentValidationResult.severity,
            ShipmentValidationResult.explanation,
            ShipmentValidationResult.created_at,
        )
        .join(Shipment, ShipmentValidationResult.shipment_id == Shipment.id)
        .where(and_(*val_filters))
        .order_by(ShipmentValidationResult.created_at.desc())
    )
    val_disc_rows = (await session.execute(val_disc_q)).all()
    validation_discrepancies = [
        ValidationDiscrepancyDetail(
            id=r[0],
            shipment_id=r[1],
            shipment_number=r[2],
            client_name=r[3] or "Consolidated Consignee",
            rule_id=r[4],
            rule_name=r[5],
            severity=r[6].value if hasattr(r[6], "value") else str(r[6]),
            explanation=r[7] or "Validation rule discrepancy detected.",
            created_at=r[8].isoformat() if r[8] else "",
        )
        for r in val_disc_rows
    ]
    distinct_shipments_with_discrepancies = len({r.shipment_id for r in validation_discrepancies})

    # 6. Volume over time (grouped by selected interval)
    intv = (interval or "daily").strip().lower()
    if intv not in ("daily", "weekly", "monthly"):
        intv = "daily"

    if intv == "weekly":
        date_col = cast(func.date_trunc("week", Shipment.created_at), Date)
    elif intv == "monthly":
        date_col = func.to_char(func.date_trunc("month", Shipment.created_at), "YYYY-MM")
    else:
        date_col = cast(Shipment.created_at, Date)

    vol_q = select(date_col, func.count(Shipment.id))
    if shipment_filters:
        vol_q = vol_q.where(and_(*shipment_filters))
    vol_q = vol_q.group_by(date_col).order_by(date_col.asc())
    vol_rows = (await session.execute(vol_q)).all()
    volume_over_time = [
        TimeSeriesPoint(date=str(r[0]), count=int(r[1])) for r in vol_rows
    ]

    # 7. Exports over time (Shared Workspace)
    exp_filters = [ShipmentExportRecord.export_status == ExportStatus.COMPLETED]
    if start_dt:
        exp_filters.append(ShipmentExportRecord.exported_at >= start_dt)
    if end_dt:
        exp_filters.append(ShipmentExportRecord.exported_at <= end_dt)

    if intv == "weekly":
        exp_date_col = cast(func.date_trunc("week", ShipmentExportRecord.exported_at), Date)
    elif intv == "monthly":
        exp_date_col = func.to_char(func.date_trunc("month", ShipmentExportRecord.exported_at), "YYYY-MM")
    else:
        exp_date_col = cast(ShipmentExportRecord.exported_at, Date)

    exp_time_q = (
        select(exp_date_col, func.count(ShipmentExportRecord.id))
        .join(Shipment, ShipmentExportRecord.shipment_id == Shipment.id)
        .where(and_(*exp_filters))
        .group_by(exp_date_col)
        .order_by(exp_date_col.asc())
    )
    exp_time_rows = (await session.execute(exp_time_q)).all()
    exports_over_time = [
        TimeSeriesPoint(date=str(r[0]), count=int(r[1])) for r in exp_time_rows
    ]

    # 8. Recent export activity (Shared Workspace)
    recent_exp_stmt = (
        select(ShipmentExportRecord, Shipment.shipment_number, User.full_name)
        .join(Shipment, ShipmentExportRecord.shipment_id == Shipment.id)
        .outerjoin(User, ShipmentExportRecord.exported_by == User.id)
    )
    recent_exp_stmt = recent_exp_stmt.order_by(
        ShipmentExportRecord.exported_at.desc()
    ).limit(5)
    recent_exp_res = await session.execute(recent_exp_stmt)
    recent_exp_rows = recent_exp_res.all()

    recent_exports = [
        RecentExportActivityItem(
            export_id=r[0].id,
            shipment_id=r[0].shipment_id,
            shipment_number=r[1],
            template_name=r[0].template_name,
            exporter_name=r[2] or "Customs Documentation Specialist",
            filename=r[0].filename,
            row_count=r[0].row_count,
            sha256_checksum=r[0].sha256_checksum,
            export_status=r[0].export_status.value if hasattr(r[0].export_status, "value") else str(r[0].export_status),
            is_demo=True,
            exported_at=r[0].exported_at.isoformat(),
        )
        for r in recent_exp_rows
    ]

    return AnalyticsOverviewResponse(
        role=current_user.role.value,
        total_shipments=total_shipments,
        shipments_by_status=shipments_by_status,
        status_distribution=status_distribution,
        total_documents=total_documents,
        documents_uploaded_by_type=docs_by_type_map,
        documents_by_type=documents_by_type,
        document_processing_status_breakdown=proc_status_map,
        documents_awaiting_extraction=awaiting_extraction,
        extraction_failures=extraction_failures,
        shipments_awaiting_human_review=awaiting_review,
        validation_failures_count=val_failures_total,
        missing_data_issues_count=missing_data_issues,
        validation_issues_by_rule=validation_issues_by_rule,
        validation_issues_by_severity=validation_issues_by_severity,
        validation_discrepancies=validation_discrepancies,
        distinct_shipments_with_discrepancies=distinct_shipments_with_discrepancies,
        verified_shipments_count=verified_cnt,
        exported_shipments_count=exported_cnt,
        volume_over_time=volume_over_time,
        exports_over_time=exports_over_time,
        aggregation_interval=intv,
        recent_exports=recent_exports,
        start_date=start_date,
        end_date=end_date,
    )
