import json
import logging
import uuid
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentType
from app.models.structured_extraction import StructuredExtraction
from app.models.field_review import DocumentFieldReview, FieldReviewActionType
from app.models.extraction import ExtractionStatus
from app.models.validation import ShipmentValidationResult, ValidationOutcome, ValidationSeverity
from app.schemas.structured_extraction import (
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
)
from app.services.validation.models import ValidationRuleResult
from app.services.validation.rules import (
    BaseValidationRule,
    InvoiceReferenceConsistencyRule,
    BuyerImporterConsistencyRule,
    SellerExporterConsistencyRule,
    CurrencyConsistencyRule,
    ProductDescriptionRule,
    QuantityConsistencyRule,
    PackageCountConsistencyRule,
    GrossWeightConsistencyRule,
    NetWeightConsistencyRule,
    ContainerNumberConsistencyRule,
    InvoiceArithmeticRule,
)

logger = logging.getLogger("cargolens.validation.engine")


class CrossDocumentValidationEngine:
    """
    Deterministic cross-document validation engine.
    Compares extracted values across all uploaded documents for a shipment,
    applies business rules and tolerances, and persists audit results.
    """

    DEFAULT_RULES: List[BaseValidationRule] = [
        InvoiceReferenceConsistencyRule(),
        BuyerImporterConsistencyRule(),
        SellerExporterConsistencyRule(),
        CurrencyConsistencyRule(),
        ProductDescriptionRule(),
        QuantityConsistencyRule(),
        PackageCountConsistencyRule(),
        GrossWeightConsistencyRule(),
        NetWeightConsistencyRule(),
        ContainerNumberConsistencyRule(),
        InvoiceArithmeticRule(),
    ]

    def __init__(self, rules: Optional[List[BaseValidationRule]] = None):
        self.rules = rules or self.DEFAULT_RULES

    async def _load_latest_extractions(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
    ) -> Tuple[
        Optional[CommercialInvoiceExtraction],
        Optional[PackingListExtraction],
        Optional[BillOfLadingExtraction],
    ]:
        """Loads latest completed structured extractions for each document type in the shipment."""
        # Query active documents for shipment
        doc_stmt = (
            select(Document)
            .where(
                and_(
                    Document.shipment_id == shipment_id,
                    Document.is_active == True,
                )
            )
        )
        doc_res = await session.execute(doc_stmt)
        docs = doc_res.scalars().all()

        invoice_ext: Optional[CommercialInvoiceExtraction] = None
        packing_ext: Optional[PackingListExtraction] = None
        bl_ext: Optional[BillOfLadingExtraction] = None

        for doc in docs:
            # Query latest completed structured extraction
            ext_stmt = (
                select(StructuredExtraction)
                .where(
                    and_(
                        StructuredExtraction.document_id == doc.id,
                        StructuredExtraction.status == ExtractionStatus.COMPLETED,
                    )
                )
                .order_by(StructuredExtraction.attempt_number.desc())
                .limit(1)
            )
            ext_res = await session.execute(ext_stmt)
            ext = ext_res.scalar_one_or_none()

            if ext and ext.extracted_data:
                try:
                    # Deep copy data to preserve the original extraction row
                    effective_data = json.loads(json.dumps(ext.extracted_data))

                    # Overlay any human corrections in chronological order
                    rev_stmt = (
                        select(DocumentFieldReview)
                        .where(DocumentFieldReview.document_id == doc.id)
                        .order_by(DocumentFieldReview.created_at.asc())
                    )
                    rev_res = await session.execute(rev_stmt)
                    reviews = rev_res.scalars().all()

                    for r in reviews:
                        if r.action == FieldReviewActionType.CORRECTED and r.corrected_value is not None:
                            if r.field_name in effective_data and isinstance(effective_data[r.field_name], dict):
                                effective_data[r.field_name]["value"] = r.corrected_value
                                effective_data[r.field_name]["normalized_value"] = r.corrected_value
                            else:
                                effective_data[r.field_name] = {
                                    "value": r.corrected_value,
                                    "normalized_value": r.corrected_value,
                                    "confidence": 1.0,
                                }

                    if doc.document_type == DocumentType.COMMERCIAL_INVOICE:
                        invoice_ext = CommercialInvoiceExtraction.model_validate(effective_data)
                    elif doc.document_type == DocumentType.PACKING_LIST:
                        packing_ext = PackingListExtraction.model_validate(effective_data)
                    elif doc.document_type == DocumentType.BILL_OF_LADING:
                        bl_ext = BillOfLadingExtraction.model_validate(effective_data)
                except Exception as e:
                    logger.warning(f"Error parsing structured extraction for doc {doc.id}: {e}")

        return invoice_ext, packing_ext, bl_ext

    async def run_validation(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
    ) -> List[ShipmentValidationResult]:
        """
        Executes all validation rules against latest extractions for a shipment,
        persisting results to the database under a new run_id.
        """
        invoice_ext, packing_ext, bl_ext = await self._load_latest_extractions(session, shipment_id)

        run_id = uuid.uuid4()
        persisted_results: List[ShipmentValidationResult] = []

        for rule in self.rules:
            result_data: ValidationRuleResult = rule.evaluate(
                invoice=invoice_ext,
                packing_list=packing_ext,
                bl=bl_ext,
            )

            db_res = ShipmentValidationResult(
                shipment_id=shipment_id,
                run_id=run_id,
                rule_id=result_data.rule_id,
                rule_name=result_data.rule_name,
                severity=result_data.severity,
                outcome=result_data.outcome,
                explanation=result_data.explanation,
                compared_values=result_data.compared_values,
                source_document_ids=result_data.source_document_ids,
            )
            session.add(db_res)
            persisted_results.append(db_res)

        await session.commit()
        for r in persisted_results:
            await session.refresh(r)

        return persisted_results

    async def get_latest_validation_results(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
    ) -> List[ShipmentValidationResult]:
        """Returns the results from the most recent validation run for the shipment."""
        # Find latest run_id
        latest_stmt = (
            select(ShipmentValidationResult.run_id)
            .where(ShipmentValidationResult.shipment_id == shipment_id)
            .order_by(ShipmentValidationResult.created_at.desc())
            .limit(1)
        )
        latest_res = await session.execute(latest_stmt)
        latest_run_id = latest_res.scalar_one_or_none()

        if not latest_run_id:
            return []

        results_stmt = (
            select(ShipmentValidationResult)
            .where(
                and_(
                    ShipmentValidationResult.shipment_id == shipment_id,
                    ShipmentValidationResult.run_id == latest_run_id,
                )
            )
            .order_by(ShipmentValidationResult.created_at.asc())
        )
        res = await session.execute(results_stmt)
        return list(res.scalars().all())
