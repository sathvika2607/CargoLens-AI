import io
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple, Set
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import pymupdf
from PIL import Image

from app.config import settings
from app.models.document import Document, DocumentType
from app.models.extraction import (
    DocumentExtraction,
    DocumentExtractionPage,
    ExtractionStatus,
    PageExtractionMethod,
)
from app.models.structured_extraction import StructuredExtraction
from app.schemas.structured_extraction import (
    CommercialInvoiceExtraction,
    PackingListExtraction,
    BillOfLadingExtraction,
    ExtractedField,
    AnyStructuredDocument,
)
from app.services.ai.base import (
    BaseExtractionProvider,
    DocumentPageInput,
    RawProviderResult,
    ExtractionProviderError,
)
from app.services.ai.claude_provider import ClaudeVisionExtractionProvider
from app.storage import get_storage_service

logger = logging.getLogger("cargolens.ai.service")


class StructuredExtractionService:
    """
    Coordinates end-to-end structured document extraction:
    - Inspects page-level extraction results to handle mixed digital/scanned pages.
    - Processes documents in bounded page batches for documents of any length.
    - Combines batch results with original page numbers and provenance.
    - Marks incomplete processing strictly as PARTIAL or FAILED (never COMPLETED).
    - Exposes total_page_count and processed_page_count.
    """

    def __init__(self, provider: Optional[BaseExtractionProvider] = None):
        self.provider = provider or ClaudeVisionExtractionProvider()
        self.storage = get_storage_service()

    @staticmethod
    def _attach_document_id(data_dict: Dict[str, Any], doc_id: uuid.UUID) -> None:
        """Recursively stamps source_document_id on all ExtractedField dictionaries."""
        for key, val in data_dict.items():
            if isinstance(val, dict):
                if "value" in val:
                    val["source_document_id"] = str(doc_id)
                else:
                    StructuredExtractionService._attach_document_id(val, doc_id)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        StructuredExtractionService._attach_document_id(item, doc_id)

    @staticmethod
    def _calculate_confidence_summary(data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates average confidence, missing fields, and low confidence fields (< 0.7)."""
        confidences: List[float] = []
        missing_fields: List[str] = []
        low_confidence_fields: List[str] = []

        def _traverse(prefix: str, d: Dict[str, Any]):
            for k, v in d.items():
                curr_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    if "value" in v:
                        val = v.get("value")
                        conf = v.get("confidence")
                        if val is None or (isinstance(val, str) and not val.strip()):
                            missing_fields.append(curr_key)
                        elif conf is not None:
                            try:
                                conf_float = float(conf)
                                confidences.append(conf_float)
                                if conf_float < 0.70:
                                    low_confidence_fields.append(curr_key)
                            except (ValueError, TypeError):
                                pass
                    else:
                        _traverse(curr_key, v)
                elif isinstance(v, list):
                    for idx, item in enumerate(v):
                        if isinstance(item, dict):
                            _traverse(f"{curr_key}[{idx}]", item)

        _traverse("", data_dict)

        avg_conf = None
        if confidences:
            avg_conf = round(sum(confidences) / len(confidences), 4)

        return {
            "average_confidence": avg_conf,
            "total_evaluated_fields": len(confidences),
            "missing_field_count": len(missing_fields),
            "low_confidence_field_count": len(low_confidence_fields),
            "low_confidence_fields": low_confidence_fields[:10],
        }

    @staticmethod
    def _merge_batch_extractions(
        base_data: Dict[str, Any],
        incoming_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Combines extractions from multiple batches:
        - Appends items in array fields (e.g. line_items, container_numbers).
        - Populates previously missing scalar fields from later pages.
        - Preserves higher-confidence fields if present in multiple batches.
        """
        for key, inc_val in incoming_data.items():
            if key not in base_data:
                base_data[key] = inc_val
                continue

            base_val = base_data[key]
            if isinstance(base_val, list) and isinstance(inc_val, list):
                # Array fields (e.g. line_items, container_numbers, seal_numbers)
                for item in inc_val:
                    if item not in base_val:
                        base_val.append(item)
            elif isinstance(base_val, dict) and isinstance(inc_val, dict):
                if "value" in inc_val and "value" in base_val:
                    # ExtractedField dictionary
                    if base_val.get("value") is None and inc_val.get("value") is not None:
                        base_data[key] = inc_val
                    elif base_val.get("value") is not None and inc_val.get("value") is not None:
                        base_conf = float(base_val.get("confidence") or 0.0)
                        inc_conf = float(inc_val.get("confidence") or 0.0)
                        if inc_conf > base_conf:
                            base_data[key] = inc_val
                else:
                    StructuredExtractionService._merge_batch_extractions(base_val, inc_val)

        return base_data

    async def _get_next_attempt_number(self, session: AsyncSession, doc_id: uuid.UUID) -> int:
        """Determines the next sequential attempt number for a document."""
        stmt = (
            select(func.coalesce(func.max(StructuredExtraction.attempt_number), 0))
            .where(StructuredExtraction.document_id == doc_id)
        )
        res = await session.execute(stmt)
        return int(res.scalar() or 0) + 1

    async def _prepare_document_pages(
        self,
        session: AsyncSession,
        document: Document,
    ) -> List[DocumentPageInput]:
        """
        Inspects page-level extraction results to determine the native modality
        for each individual page (DIGITAL_TEXT vs VISION).
        Ensures mixed digital/scanned PDFs are accurately partitioned without skipping pages.
        """
        # Read file bytes from storage
        chunks = []
        async for chunk in self.storage.get_file_stream(document.storage_key):
            chunks.append(chunk)
        file_bytes = b"".join(chunks)

        if "pdf" not in document.mime_type.lower():
            # Image document (single page)
            return [
                DocumentPageInput(
                    page_number=1,
                    is_digital_text=False,
                    image_bytes=file_bytes,
                    mime_type=document.mime_type,
                )
            ]

        # Multi-page PDF document
        pages_input: List[DocumentPageInput] = []
        pdf_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        total_pages = len(pdf_doc)

        # 1. Check if Prompt 5 page-level extraction records exist
        txt_stmt = (
            select(DocumentExtraction)
            .options(selectinload(DocumentExtraction.pages))
            .where(
                and_(
                    DocumentExtraction.document_id == document.id,
                    DocumentExtraction.status == ExtractionStatus.COMPLETED,
                )
            )
            .order_by(DocumentExtraction.attempt_number.desc())
            .limit(1)
        )
        txt_res = await session.execute(txt_stmt)
        latest_txt_ext = txt_res.scalar_one_or_none()

        page_record_map: Dict[int, DocumentExtractionPage] = {}
        if latest_txt_ext and latest_txt_ext.pages:
            for p in latest_txt_ext.pages:
                page_record_map[p.page_number] = p

        # 2. Iterate each page and determine modality individually
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            p_rec = page_record_map.get(page_num)

            is_digital = False
            page_text: Optional[str] = None
            page_img: Optional[bytes] = None

            if p_rec and p_rec.extraction_method == PageExtractionMethod.DIGITAL_TEXT and p_rec.raw_text and len(p_rec.raw_text.strip()) >= 30:
                is_digital = True
                page_text = p_rec.raw_text.strip()
            else:
                # Inspect directly from PDF if no Prompt 5 digital classification
                try:
                    pdf_page = pdf_doc.load_page(page_idx)
                    inline_text = pdf_page.get_text().strip()
                    if inline_text and len(inline_text) >= 30 and (not p_rec or p_rec.extraction_method != PageExtractionMethod.OCR):
                        is_digital = True
                        page_text = inline_text
                    else:
                        # Scanned or image-heavy page: render to JPEG image bytes
                        pix = pdf_page.get_pixmap(dpi=150)
                        page_img = pix.tobytes("jpeg")
                except Exception as e:
                    logger.warning(f"Error loading PDF page {page_num}: {e}")

            pages_input.append(
                DocumentPageInput(
                    page_number=page_num,
                    is_digital_text=is_digital,
                    text_content=page_text,
                    image_bytes=page_img,
                    mime_type="image/jpeg" if page_img else None,
                )
            )

        pdf_doc.close()
        return pages_input

    async def execute_extraction(
        self,
        session: AsyncSession,
        document: Document,
    ) -> StructuredExtraction:
        """
        Executes structured extraction across all document pages:
        - Processes in bounded page batches (e.g. 5 pages max per batch).
        - Combines batch results while preserving page numbers and provenance.
        - Marks incomplete or interrupted processing as PARTIAL or FAILED (never COMPLETED).
        """
        attempt_number = await self._get_next_attempt_number(session, document.id)
        started_at = datetime.now(timezone.utc)

        # Initial state in PROCESSING
        extraction_rec = StructuredExtraction(
            document_id=document.id,
            document_type=document.document_type,
            attempt_number=attempt_number,
            status=ExtractionStatus.PROCESSING,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            extraction_mode="TEXT_FIRST",
            total_page_count=0,
            processed_page_count=0,
            started_at=started_at,
        )
        session.add(extraction_rec)
        await session.commit()
        await session.refresh(extraction_rec)

        try:
            # 1. Prepare and classify all individual pages
            all_pages = await self._prepare_document_pages(session, document)
            total_page_count = len(all_pages)
            extraction_rec.total_page_count = total_page_count

            batch_size = max(1, settings.STRUCTURED_EXTRACTION_MAX_IMAGE_PAGES)
            page_batches: List[List[DocumentPageInput]] = [
                all_pages[i : i + batch_size] for i in range(0, total_page_count, batch_size)
            ]

            combined_data: Dict[str, Any] = {}
            processed_page_count = 0
            modes_used: Set[str] = set()
            total_tokens = {"input_tokens": 0, "output_tokens": 0}
            total_latency = 0.0
            batch_failure_err: Optional[str] = None

            # 2. Process each bounded batch
            for batch in page_batches:
                try:
                    batch_res: RawProviderResult = await self.provider.extract_pages_batch(
                        document_type=document.document_type,
                        pages=batch,
                    )
                    modes_used.add(batch_res.extraction_mode)
                    total_tokens["input_tokens"] += batch_res.token_usage.get("input_tokens", 0)
                    total_tokens["output_tokens"] += batch_res.token_usage.get("output_tokens", 0)
                    total_latency += batch_res.latency_seconds

                    # Combine into accumulated extraction data
                    combined_data = self._merge_batch_extractions(combined_data, batch_res.data)
                    processed_page_count += len(batch)

                except Exception as b_err:
                    logger.warning(
                        f"Batch extraction failed for doc {document.id} (pages {batch[0].page_number}..{batch[-1].page_number}): {b_err}"
                    )
                    batch_failure_err = str(b_err)
                    break

            extraction_rec.processed_page_count = processed_page_count

            # 3. Handle total failure vs partial completion
            if processed_page_count == 0:
                raise ExtractionProviderError(
                    f"Extraction failed on first page batch: {batch_failure_err}"
                )

            # Determine composite modality
            if "HYBRID" in modes_used or ("TEXT_FIRST" in modes_used and "VISION" in modes_used):
                overall_mode = "HYBRID"
            elif "VISION" in modes_used:
                overall_mode = "VISION"
            else:
                overall_mode = "TEXT_FIRST"

            extraction_rec.extraction_mode = overall_mode

            # 4. Attach document provenance and validate schema
            self._attach_document_id(combined_data, document.id)

            schema_cls: Any
            if document.document_type == DocumentType.COMMERCIAL_INVOICE:
                schema_cls = CommercialInvoiceExtraction
            elif document.document_type == DocumentType.PACKING_LIST:
                schema_cls = PackingListExtraction
            elif document.document_type == DocumentType.BILL_OF_LADING:
                schema_cls = BillOfLadingExtraction
            else:
                raise ExtractionProviderError(f"Unsupported document type: {document.document_type}")

            validated_obj = schema_cls.model_validate(combined_data)
            validated_dict = validated_obj.model_dump(mode="json")
            confidence_summary = self._calculate_confidence_summary(validated_dict)

            extraction_rec.extracted_data = validated_dict
            extraction_rec.field_confidence_summary = confidence_summary
            extraction_rec.raw_response_metadata = {
                "token_usage": total_tokens,
                "latency_seconds": round(total_latency, 3),
                "batches_count": len(page_batches),
            }
            extraction_rec.completed_at = datetime.now(timezone.utc)

            # 5. Rule: Never mark a partially processed document as COMPLETED
            if processed_page_count < total_page_count:
                extraction_rec.status = ExtractionStatus.PARTIAL
                extraction_rec.error_summary = (
                    f"Partial processing: {processed_page_count} of {total_page_count} pages processed. "
                    f"Batch error: {batch_failure_err}"
                )
            else:
                extraction_rec.status = ExtractionStatus.COMPLETED
                extraction_rec.error_summary = None

            await session.commit()
            await session.refresh(extraction_rec)
            return extraction_rec

        except Exception as e:
            logger.exception(f"Structured extraction aborted for doc {document.id}: {e}")
            extraction_rec.status = ExtractionStatus.FAILED
            extraction_rec.completed_at = datetime.now(timezone.utc)
            extraction_rec.error_summary = str(e)
            await session.commit()
            await session.refresh(extraction_rec)
            return extraction_rec
