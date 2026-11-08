from typing import List, Optional
from app.config import settings
from app.models.extraction import ExtractionQualityStatus, PageProcessingStatus


class QualityAssessmentService:
    """
    Evaluates extraction quality, detecting empty results, low confidence,
    partial page failures, and technical errors.
    """

    @classmethod
    def evaluate_document_quality(
        cls,
        total_pages: int,
        processed_pages: int,
        failed_pages: int,
        character_count: int,
        avg_confidence: Optional[float],
        min_confidence: Optional[float] = None,
    ) -> ExtractionQualityStatus:
        """
        Calculates the overall quality status for a document extraction attempt.
        """
        threshold_conf = min_confidence or settings.OCR_MIN_CONFIDENCE

        # 1. Total failure
        if total_pages > 0 and failed_pages == total_pages:
            return ExtractionQualityStatus.FAILED

        # 2. Zero characters extracted across all pages
        if character_count == 0:
            return ExtractionQualityStatus.EMPTY

        # 3. Partial page failure
        if failed_pages > 0 and processed_pages > 0:
            return ExtractionQualityStatus.PARTIAL

        # 4. Low confidence for OCR pages
        if avg_confidence is not None and avg_confidence < threshold_conf:
            return ExtractionQualityStatus.LOW_CONFIDENCE

        # 5. Suspiciously low text density (e.g. fewer than 10 characters across multi-page document)
        if total_pages > 1 and character_count < 15:
            return ExtractionQualityStatus.LOW_CONFIDENCE

        return ExtractionQualityStatus.GOOD

    @classmethod
    def evaluate_page_status(
        cls,
        text: str,
        has_error: bool = False,
    ) -> PageProcessingStatus:
        """Evaluates status of an individual page extraction."""
        if has_error:
            return PageProcessingStatus.FAILED
        if not text or not text.strip():
            return PageProcessingStatus.EMPTY
        return PageProcessingStatus.COMPLETED
