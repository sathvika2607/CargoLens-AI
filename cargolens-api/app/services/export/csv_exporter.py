import csv
import hashlib
import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shipment import Shipment, ShipmentStatus
from app.models.document import Document, DocumentType
from app.models.field_review import DocumentFieldReview, FieldReviewActionType, ReviewProvenance
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.models.export import ShipmentExportRecord, ExportStatus
from app.models.user import User, UserRole
from app.schemas.export import ExportTemplateType, ExportTemplateInfo

DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

MANDATORY_EXPORT_FIELDS = [
    "invoice_number",
    "invoice_date",
    "seller_name",
    "buyer_name",
    "grand_total",
    "currency",
    "invoice_reference",
    "package_count",
    "gross_weight_kg",
    "bl_number",
    "shipper_name",
    "consignee_name",
]

AVAILABLE_TEMPLATES: List[ExportTemplateInfo] = [
    ExportTemplateInfo(
        template_id=ExportTemplateType.STANDARD_CUSTOMS_CLEARANCE.value,
        name="Standard Customs Clearance (Single Consignment)",
        description="Comprehensive customs declaration row containing validated invoice, bill of lading, and packing list values.",
        columns=[
            "Shipment Reference",
            "Customs Client",
            "Origin Country",
            "Commercial Invoice Number",
            "Invoice Date",
            "Seller / Exporter",
            "Buyer / Importer",
            "Bill of Lading Number",
            "Shipper",
            "Consignee",
            "Packing List Reference",
            "Package Count",
            "Gross Weight (KG)",
            "Net Weight (KG)",
            "Container Numbers",
            "Currency",
            "Grand Total",
            "Product Description",
            "Export Timestamp",
        ],
    ),
    ExportTemplateInfo(
        template_id=ExportTemplateType.LINE_ITEM_DECLARATION.value,
        name="Line-Item Customs Declaration",
        description="Detailed customs declaration with individual line-item breakdown for customs valuation and tariff classification.",
        columns=[
            "Shipment Reference",
            "Customs Client",
            "Commercial Invoice Number",
            "Invoice Date",
            "Seller / Exporter",
            "Buyer / Importer",
            "Bill of Lading Number",
            "Line Item Number",
            "Item Description",
            "Quantity",
            "Unit Price",
            "Line Total",
            "Currency",
            "Package Count",
            "Gross Weight (KG)",
            "Container Numbers",
            "Export Timestamp",
        ],
    ),
]


def sanitize_csv_cell(value: Any) -> str:
    """
    Neutralizes CSV formula injection vulnerabilities (OWASP).
    If a string begins with dangerous spreadsheet formula starters (=, +, -, @, \t, \r),
    prefixes it with a single quote to force spreadsheet software to treat it as text.
    Preserves None as empty string.
    """
    if value is None:
        return ""
    val_str = str(value)
    if not val_str:
        return ""
    if val_str.startswith(DANGEROUS_CSV_PREFIXES):
        return f"'{val_str}"
    return val_str


class CSVExportService:
    """
    Generates deterministic, verified customs declaration exports in CSV format.
    Strictly uses human-reviewed and confirmed values from the review overlay.
    Raw unreviewed AI values are never exported.
    """

    @staticmethod
    async def get_approved_review_overlay(
        session: AsyncSession,
        shipment_id: UUID,
        user_action_only: bool = True,
    ) -> Dict[str, str]:
        """
        Loads the approved human review overlay for a shipment.
        Only fields that have been confirmed or corrected by an authorized reviewer
        are returned. Unreviewed raw AI extraction values are omitted.
        If user_action_only is True (default for customs clearance and export),
        only reviews with provenance=ReviewProvenance.USER_ACTION are included.
        DEMO_SEED reviews are excluded from satisfying export/verification requirements.
        """
        stmt = (
            select(DocumentFieldReview)
            .where(DocumentFieldReview.shipment_id == shipment_id)
        )
        if user_action_only:
            stmt = stmt.where(DocumentFieldReview.provenance == ReviewProvenance.USER_ACTION)
        stmt = stmt.order_by(DocumentFieldReview.created_at.asc())

        res = await session.execute(stmt)
        reviews = res.scalars().all()

        approved_values: Dict[str, str] = {}
        for r in reviews:
            if r.action == FieldReviewActionType.CORRECTED:
                if r.corrected_value is not None:
                    val = r.corrected_value
                    if not val.startswith(DANGEROUS_CSV_PREFIXES):
                        val = val.strip()
                    approved_values[r.field_name] = val
            elif r.action == FieldReviewActionType.CONFIRMED:
                effective = r.corrected_value if r.corrected_value is not None else r.original_value
                if effective is not None:
                    val = effective
                    if not val.startswith(DANGEROUS_CSV_PREFIXES):
                        val = val.strip()
                    approved_values[r.field_name] = val

        return approved_values

    @staticmethod
    async def evaluate_export_readiness(
        session: AsyncSession,
        shipment: Shipment,
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates whether a shipment is fully eligible for customs declaration export.
        Checks:
        1. Shipment status must be VERIFIED or EXPORTED.
        2. No unresolved blocking validation failures.
        3. All mandatory export fields confirmed or corrected with valid non-empty values
           by genuine human reviewers (ReviewProvenance.USER_ACTION).
        """
        missing_requirements: List[str] = []

        # 1. Status verification
        if shipment.status == ShipmentStatus.EXPORTED:
            missing_requirements.append(
                "Shipment has already been exported. Duplicate or concurrent export is not permitted."
            )
        elif shipment.status != ShipmentStatus.VERIFIED:
            missing_requirements.append(
                f"Shipment is currently in '{shipment.status.value}' status. Only VERIFIED shipments can be exported."
            )

        # 2. Check blocking validation failures from latest run
        val_stmt = (
            select(ShipmentValidationResult)
            .where(ShipmentValidationResult.shipment_id == shipment.id)
            .order_by(ShipmentValidationResult.created_at.desc())
        )
        val_res = await session.execute(val_stmt)
        val_results = val_res.scalars().all()

        if val_results:
            latest_run_id = val_results[0].run_id
            latest_failures = [
                r for r in val_results
                if r.run_id == latest_run_id and r.outcome == ValidationOutcome.FAIL
            ]
            if latest_failures:
                missing_requirements.append(
                    f"Shipment has {len(latest_failures)} unresolved blocking validation failure(s)."
                )
        else:
            missing_requirements.append(
                "Cross-document validation has not been executed for this shipment."
            )

        # 3. Check approved human reviews for mandatory fields (USER_ACTION strictly required)
        user_overlay = await CSVExportService.get_approved_review_overlay(
            session, shipment.id, user_action_only=True
        )
        all_overlay = await CSVExportService.get_approved_review_overlay(
            session, shipment.id, user_action_only=False
        )

        for field in MANDATORY_EXPORT_FIELDS:
            user_val = user_overlay.get(field)
            if not user_val or not user_val.strip():
                demo_val = all_overlay.get(field)
                if demo_val and demo_val.strip():
                    missing_requirements.append(
                        f"Mandatory export field '{field}' is covered only by a demonstration fixture (DEMO_SEED) and requires genuine human review."
                    )
                else:
                    missing_requirements.append(
                        f"Mandatory export field '{field}' has not been confirmed or corrected by an authorized reviewer."
                    )

        is_ready = len(missing_requirements) == 0
        return is_ready, missing_requirements

    @staticmethod
    async def generate_export(
        session: AsyncSession,
        shipment_id: UUID,
        current_user: User,
        template_name: str = ExportTemplateType.STANDARD_CUSTOMS_CLEARANCE.value,
    ) -> Tuple[ShipmentExportRecord, bytes]:
        """
        Generates verified CSV export under exclusive PostgreSQL row lock.
        Rechecks authorization, eligibility, and validation blockers after acquiring lock.
        Atomic commit updates shipment status to EXPORTED and stores immutable snapshot in
        shipment_export_records, safely releasing row lock.
        """
        # 1. Acquire exclusive PostgreSQL row lock on Shipment
        stmt = (
            select(Shipment)
            .where(Shipment.id == shipment_id)
            .with_for_update()
        )

        res = await session.execute(stmt)
        shipment = res.scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment '{shipment_id}' not found or access denied.",
            )

        # 2. Recheck status under row lock:
        # If already EXPORTED, reject with 409 Conflict under the single-export policy
        if shipment.status == ShipmentStatus.EXPORTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Shipment '{shipment.shipment_number}' has already been exported. Duplicate or concurrent export is not permitted.",
            )

        if shipment.status != ShipmentStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Shipment is not eligible for export.",
                    "missing_requirements": [
                        f"Shipment is currently in '{shipment.status.value}' status. Only VERIFIED shipments can be exported."
                    ],
                },
            )

        # 3. Recheck readiness under row lock
        is_ready, missing_reqs = await CSVExportService.evaluate_export_readiness(session, shipment)
        if not is_ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Shipment is not eligible for export.",
                    "missing_requirements": missing_reqs,
                },
            )

        # Load approved review overlay (enforcing USER_ACTION provenance)
        overlay = await CSVExportService.get_approved_review_overlay(
            session, shipment.id, user_action_only=True
        )

        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_shipment_num = shipment.shipment_number.replace("/", "_").replace("\\", "_")
        filename = f"cargolens_export_{safe_shipment_num}_{timestamp_slug}.csv"

        # Determine template
        template_info = next(
            (t for t in AVAILABLE_TEMPLATES if t.template_id == template_name),
            None,
        )
        if not template_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown export template '{template_name}'. Available: {[t.template_id for t in AVAILABLE_TEMPLATES]}",
            )

        rows: List[List[str]] = []
        raw_rows_data: List[Dict[str, Any]] = []

        if template_name == ExportTemplateType.STANDARD_CUSTOMS_CLEARANCE.value:
            # Single consolidated declaration row
            row_dict = {
                "Shipment Reference": shipment.shipment_number,
                "Customs Client": shipment.client_name,
                "Origin Country": shipment.origin_country,
                "Commercial Invoice Number": overlay.get("invoice_number", ""),
                "Invoice Date": overlay.get("invoice_date", ""),
                "Seller / Exporter": overlay.get("seller_name", overlay.get("shipper_name", "")),
                "Buyer / Importer": overlay.get("buyer_name", overlay.get("consignee_name", "")),
                "Bill of Lading Number": overlay.get("bl_number", ""),
                "Shipper": overlay.get("shipper_name", overlay.get("seller_name", "")),
                "Consignee": overlay.get("consignee_name", overlay.get("buyer_name", "")),
                "Packing List Reference": overlay.get("invoice_reference", ""),
                "Package Count": overlay.get("package_count", ""),
                "Gross Weight (KG)": overlay.get("gross_weight_kg", ""),
                "Net Weight (KG)": overlay.get("net_weight_kg", ""),
                "Container Numbers": overlay.get("container_numbers", ""),
                "Currency": overlay.get("currency", shipment.currency or ""),
                "Grand Total": overlay.get("grand_total", ""),
                "Product Description": overlay.get("product_description", shipment.product_description or ""),
                "Export Timestamp": timestamp_str,
            }
            raw_rows_data.append(row_dict)
            rows.append([sanitize_csv_cell(row_dict[col]) for col in template_info.columns])

        elif template_name == ExportTemplateType.LINE_ITEM_DECLARATION.value:
            # Check for line items in approved overlay
            # Line items could be reviewed as line_items.0.description etc.
            line_item_indices = set()
            for k in overlay.keys():
                if k.startswith("line_items."):
                    parts = k.split(".")
                    if len(parts) >= 2 and parts[1].isdigit():
                        line_item_indices.add(int(parts[1]))

            if line_item_indices:
                sorted_indices = sorted(list(line_item_indices))
                for idx in sorted_indices:
                    row_dict = {
                        "Shipment Reference": shipment.shipment_number,
                        "Customs Client": shipment.client_name,
                        "Commercial Invoice Number": overlay.get("invoice_number", ""),
                        "Invoice Date": overlay.get("invoice_date", ""),
                        "Seller / Exporter": overlay.get("seller_name", overlay.get("shipper_name", "")),
                        "Buyer / Importer": overlay.get("buyer_name", overlay.get("consignee_name", "")),
                        "Bill of Lading Number": overlay.get("bl_number", ""),
                        "Line Item Number": str(idx + 1),
                        "Item Description": overlay.get(f"line_items.{idx}.description", ""),
                        "Quantity": overlay.get(f"line_items.{idx}.quantity", ""),
                        "Unit Price": overlay.get(f"line_items.{idx}.unit_price", ""),
                        "Line Total": overlay.get(f"line_items.{idx}.line_total", ""),
                        "Currency": overlay.get("currency", shipment.currency or ""),
                        "Package Count": overlay.get("package_count", ""),
                        "Gross Weight (KG)": overlay.get("gross_weight_kg", ""),
                        "Container Numbers": overlay.get("container_numbers", ""),
                        "Export Timestamp": timestamp_str,
                    }
                    raw_rows_data.append(row_dict)
                    rows.append([sanitize_csv_cell(row_dict[col]) for col in template_info.columns])
            else:
                # Default single row fallback if no itemized line items reviewed
                row_dict = {
                    "Shipment Reference": shipment.shipment_number,
                    "Customs Client": shipment.client_name,
                    "Commercial Invoice Number": overlay.get("invoice_number", ""),
                    "Invoice Date": overlay.get("invoice_date", ""),
                    "Seller / Exporter": overlay.get("seller_name", overlay.get("shipper_name", "")),
                    "Buyer / Importer": overlay.get("buyer_name", overlay.get("consignee_name", "")),
                    "Bill of Lading Number": overlay.get("bl_number", ""),
                    "Line Item Number": "1",
                    "Item Description": overlay.get("product_description", shipment.product_description or "General Cargo"),
                    "Quantity": str(shipment.quantity) if shipment.quantity is not None else "1",
                    "Unit Price": str(shipment.unit_price) if shipment.unit_price is not None else overlay.get("grand_total", ""),
                    "Line Total": overlay.get("grand_total", ""),
                    "Currency": overlay.get("currency", shipment.currency or ""),
                    "Package Count": overlay.get("package_count", ""),
                    "Gross Weight (KG)": overlay.get("gross_weight_kg", ""),
                    "Container Numbers": overlay.get("container_numbers", ""),
                    "Export Timestamp": timestamp_str,
                }
                raw_rows_data.append(row_dict)
                rows.append([sanitize_csv_cell(row_dict[col]) for col in template_info.columns])

        # Generate CSV string
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        # Write header
        writer.writerow(template_info.columns)
        # Write rows
        for row in rows:
            writer.writerow(row)

        csv_text = output.getvalue()
        csv_bytes = csv_text.encode("utf-8")
        sha256 = hashlib.sha256(csv_bytes).hexdigest()

        # Build immutable snapshot
        snapshot_payload = {
            "template_name": template_name,
            "template_version": "1.0",
            "columns": template_info.columns,
            "row_count": len(rows),
            "file_size_bytes": len(csv_bytes),
            "sha256_checksum": sha256,
            "approved_overlay": overlay,
            "rows": raw_rows_data,
            "csv_content": csv_text,
            "exported_at": timestamp_str,
        }

        # Create export record
        export_record = ShipmentExportRecord(
            shipment_id=shipment.id,
            exported_by=current_user.id,
            template_name=template_name,
            template_version="1.0",
            filename=filename,
            sha256_checksum=sha256,
            export_status=ExportStatus.COMPLETED,
            row_count=len(rows),
            file_size_bytes=len(csv_bytes),
            snapshot_data=snapshot_payload,
        )
        session.add(export_record)

        # Transition shipment to EXPORTED
        shipment.status = ShipmentStatus.EXPORTED
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Shipment '{shipment.shipment_number}' has already been exported. Duplicate or concurrent export is not permitted.",
            )

        await session.refresh(export_record)
        await session.refresh(shipment)

        return export_record, csv_bytes
