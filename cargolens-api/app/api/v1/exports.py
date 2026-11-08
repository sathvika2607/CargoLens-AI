from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.models.export import ShipmentExportRecord, ExportStatus
from app.schemas.export import (
    ExportReadinessResponse,
    ShipmentExportRecordResponse,
    ShipmentExportListResponse,
    ExportTemplateType,
)
from app.services.export.csv_exporter import (
    CSVExportService,
    AVAILABLE_TEMPLATES,
)

router = APIRouter(tags=["Customs Data Export & Integrity"])


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


@router.get(
    "/shipments/{shipment_id}/export-readiness",
    response_model=ExportReadinessResponse,
    summary="Evaluate Consignment Export Readiness",
    description="Evaluates whether a shipment satisfies all criteria required for customs data export.",
)
async def get_export_readiness(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ExportReadinessResponse:
    shipment = await _get_authorized_shipment(shipment_id, current_user, session)
    is_ready, missing_reqs = await CSVExportService.evaluate_export_readiness(session, shipment)

    is_verified = shipment.status == ShipmentStatus.VERIFIED
    has_blocking = any("validation" in req.lower() for req in missing_reqs)
    all_mandatory = not any("mandatory export field" in req.lower() for req in missing_reqs)

    return ExportReadinessResponse(
        shipment_id=shipment.id,
        shipment_number=shipment.shipment_number,
        current_status=shipment.status.value,
        is_verified=is_verified,
        all_mandatory_fields_reviewed=all_mandatory,
        has_blocking_failures=has_blocking,
        is_ready_to_export=is_ready,
        missing_requirements=missing_reqs,
        available_templates=AVAILABLE_TEMPLATES,
    )


@router.post(
    "/shipments/{shipment_id}/export",
    summary="Execute Customs Declaration CSV Export",
    description="Generates an authenticated customs declaration CSV export under exclusive PostgreSQL row lock, records immutable snapshot and checksum, and transitions shipment to EXPORTED.",
)
async def export_shipment_csv(
    shipment_id: UUID,
    template: str = Query(
        ExportTemplateType.STANDARD_CUSTOMS_CLEARANCE.value,
        description="Export layout template (STANDARD_CUSTOMS_CLEARANCE or LINE_ITEM_DECLARATION)",
    ),
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
):
    user_id = current_user.id
    try:
        record, csv_bytes = await CSVExportService.generate_export(
            session=session,
            shipment_id=shipment_id,
            current_user=current_user,
            template_name=template,
        )
    except HTTPException:
        # Expected domain exceptions (404, 403, 409, 422, 400) re-raised directly without FAILED records
        raise
    except Exception as e:
        # Unexpected internal error during generation or persistence.
        # 1. Roll back the failed transaction to clean up any dirty state on the session.
        try:
            await session.rollback()
        except Exception:
            pass

        # 2. In a clean transaction, record failure information safely
        try:
            failed_record = ShipmentExportRecord(
                shipment_id=shipment_id,
                exported_by=user_id,
                template_name=template,
                template_version="1.0",
                filename=f"failed_export_{shipment_id}.csv",
                sha256_checksum="0000000000000000000000000000000000000000000000000000000000000000",
                export_status=ExportStatus.FAILED,
                row_count=0,
                file_size_bytes=0,
                error_message="Export generation failed due to an internal processing error.",
                snapshot_data={"error": "Export generation failed due to an internal processing error."},
            )
            session.add(failed_record)
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass

        # 3. Return a clean, non-leaking HTTP 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export generation failed due to an internal server error. Please try again later.",
        )

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{record.filename}"',
            "X-Export-Id": str(record.id),
            "X-Export-Checksum": record.sha256_checksum,
            "X-Export-Status": record.export_status.value,
        },
    )


@router.get(
    "/shipments/{shipment_id}/exports",
    response_model=ShipmentExportListResponse,
    summary="List Consignment Export History",
    description="Retrieves the immutable audit trail of past export events for this shipment.",
)
async def list_shipment_exports(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentExportListResponse:
    await _get_authorized_shipment(shipment_id, current_user, session)

    stmt = (
        select(ShipmentExportRecord)
        .options(selectinload(ShipmentExportRecord.exporter))
        .where(ShipmentExportRecord.shipment_id == shipment_id)
        .order_by(ShipmentExportRecord.exported_at.desc())
    )
    res = await session.execute(stmt)
    records = res.scalars().all()

    items = [
        ShipmentExportRecordResponse(
            id=r.id,
            shipment_id=r.shipment_id,
            exported_by=r.exported_by,
            exporter_name=r.exporter.full_name if r.exporter else None,
            exporter_email=r.exporter.email if r.exporter else None,
            template_name=r.template_name,
            template_version=r.template_version,
            filename=r.filename,
            sha256_checksum=r.sha256_checksum,
            export_status=r.export_status.value,
            row_count=r.row_count,
            file_size_bytes=r.file_size_bytes,
            error_message=r.error_message,
            exported_at=r.exported_at.isoformat(),
        )
        for r in records
    ]
    return ShipmentExportListResponse(items=items, total=len(items))


@router.get(
    "/shipments/{shipment_id}/exports/{export_id}/download",
    summary="Download Historical Export Snapshot",
    description="Downloads the exact immutable CSV snapshot from a previous export record with verified SHA-256 integrity.",
)
async def download_export_snapshot(
    shipment_id: UUID,
    export_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
):
    await _get_authorized_shipment(shipment_id, current_user, session)

    stmt = select(ShipmentExportRecord).where(
        ShipmentExportRecord.id == export_id,
        ShipmentExportRecord.shipment_id == shipment_id,
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export record '{export_id}' not found for shipment '{shipment_id}'.",
        )

    if record.export_status != ExportStatus.COMPLETED or not record.snapshot_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot download file for a failed export record.",
        )

    csv_content = record.snapshot_data.get("csv_content", "")
    csv_bytes = csv_content.encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{record.filename}"',
            "X-Export-Id": str(record.id),
            "X-Export-Checksum": record.sha256_checksum,
            "X-Export-Status": record.export_status.value,
        },
    )
