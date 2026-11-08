import io
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from PIL import Image

from app.config import settings
from app.models.extraction import (
    ExtractionStatus,
    ExtractionMethod,
    ExtractionQualityStatus,
    PageExtractionMethod,
    PageProcessingStatus,
)
from app.services.ocr.pdf_extractor import PdfExtractor, PageExtractionResult
from app.services.ocr.image_preprocessor import ImagePreprocessor
from app.services.ocr.tesseract_engine import TesseractEngine
from app.services.ocr.text_normalizer import TextNormalizer
from app.services.ocr.quality_assessment import QualityAssessmentService

logger = logging.getLogger("cargolens.ocr.pipeline")


@dataclass
class ExtractionPipelineResult:
    document_id: UUID
    status: ExtractionStatus
    extraction_method: ExtractionMethod
    raw_text: str
    page_count: int
    processed_page_count: int
    failed_page_count: int
    avg_confidence: Optional[float]
    character_count: int
    quality_status: ExtractionQualityStatus
    pages: List[PageExtractionResult] = field(default_factory=list)
    error_summary: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = 0.0


class OcrPipeline:
    """
    End-to-end OCR and Text Intelligence Pipeline for CargoLens AI.
    Processes digital PDFs, scanned PDFs, PNG, JPG, and JPEG images.
    """

    def __init__(self, tesseract_engine: Optional[TesseractEngine] = None):
        self.tesseract_engine = tesseract_engine or TesseractEngine()
        self.pdf_extractor = PdfExtractor(tesseract_engine=self.tesseract_engine)

    def process_image(self, file_bytes: bytes) -> List[PageExtractionResult]:
        """Processes a single image document (PNG, JPEG, JPG)."""
        try:
            with Image.open(io.BytesIO(file_bytes)) as raw_img:
                preprocessed = ImagePreprocessor.preprocess_for_ocr(raw_img, check_orientation=True)
                ocr_text, ocr_conf = self.tesseract_engine.extract_text_and_confidence(preprocessed)
                normalized = TextNormalizer.normalize_text(ocr_text)

                if not normalized:
                    return [
                        PageExtractionResult(
                            page_number=1,
                            raw_text="",
                            extraction_method=PageExtractionMethod.EMPTY,
                            ocr_confidence=None,
                            character_count=0,
                            processing_status=PageProcessingStatus.EMPTY,
                        )
                    ]

                return [
                    PageExtractionResult(
                        page_number=1,
                        raw_text=normalized,
                        extraction_method=PageExtractionMethod.OCR,
                        ocr_confidence=ocr_conf,
                        character_count=len(normalized),
                        processing_status=PageProcessingStatus.COMPLETED,
                    )
                ]
        except Exception as e:
            logger.error(f"Image OCR processing failed: {e}", exc_info=True)
            return [
                PageExtractionResult(
                    page_number=1,
                    raw_text="",
                    extraction_method=PageExtractionMethod.FAILED,
                    ocr_confidence=None,
                    character_count=0,
                    processing_status=PageProcessingStatus.FAILED,
                    error_message=str(e)[:500],
                )
            ]

    async def process_document(
        self,
        file_bytes: bytes,
        file_extension: str,
        document_id: UUID,
    ) -> ExtractionPipelineResult:
        """
        Executes complete extraction pipeline on uploaded document bytes.
        Returns aggregate extraction metrics and page-level results.
        """
        start_time = time.monotonic()
        started_at = datetime.now(timezone.utc)
        clean_ext = file_extension.lower().lstrip(".")

        pages: List[PageExtractionResult] = []
        error_summary: Optional[str] = None

        try:
            if clean_ext == "pdf":
                pages = self.pdf_extractor.process_pdf(file_bytes)
            elif clean_ext in ("png", "jpg", "jpeg"):
                pages = self.process_image(file_bytes)
            else:
                raise ValueError(f"Unsupported file extension for OCR pipeline: .{clean_ext}")
        except Exception as e:
            logger.error(f"Fatal error during document extraction for doc {document_id}: {e}", exc_info=True)
            error_summary = str(e)[:1000]

        completed_at = datetime.now(timezone.utc)
        duration = round(time.monotonic() - start_time, 2)

        page_count = len(pages)
        processed_page_count = sum(
            1 for p in pages if p.processing_status == PageProcessingStatus.COMPLETED
        )
        failed_page_count = sum(
            1 for p in pages if p.processing_status == PageProcessingStatus.FAILED
        )
        character_count = sum(p.character_count for p in pages)

        # Reconstruct aggregated text
        text_parts = [p.raw_text for p in pages if p.raw_text]
        raw_text = "\n\n".join(text_parts) if text_parts else ""

        # Determine overall extraction method
        methods = {p.extraction_method for p in pages}
        if not pages or methods == {PageExtractionMethod.FAILED}:
            overall_method = ExtractionMethod.FAILED
        elif methods == {PageExtractionMethod.EMPTY}:
            overall_method = ExtractionMethod.EMPTY
        elif PageExtractionMethod.DIGITAL_TEXT in methods and PageExtractionMethod.OCR in methods:
            overall_method = ExtractionMethod.HYBRID
        elif PageExtractionMethod.OCR in methods:
            overall_method = ExtractionMethod.OCR
        else:
            overall_method = ExtractionMethod.DIGITAL_TEXT

        # Calculate average confidence across pages where OCR ran and gave confidence
        conf_values = [p.ocr_confidence for p in pages if p.ocr_confidence is not None]
        avg_confidence = round(sum(conf_values) / len(conf_values), 2) if conf_values else None

        # Quality assessment
        if error_summary and not pages:
            quality = ExtractionQualityStatus.FAILED
            status = ExtractionStatus.FAILED
        else:
            quality = QualityAssessmentService.evaluate_document_quality(
                total_pages=page_count,
                processed_pages=processed_page_count,
                failed_pages=failed_page_count,
                character_count=character_count,
                avg_confidence=avg_confidence,
            )
            status = (
                ExtractionStatus.FAILED
                if (page_count > 0 and failed_page_count == page_count)
                else ExtractionStatus.COMPLETED
            )

        return ExtractionPipelineResult(
            document_id=document_id,
            status=status,
            extraction_method=overall_method,
            raw_text=raw_text,
            page_count=page_count,
            processed_page_count=processed_page_count,
            failed_page_count=failed_page_count,
            avg_confidence=avg_confidence,
            character_count=character_count,
            quality_status=quality,
            pages=pages,
            error_summary=error_summary,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
        )
