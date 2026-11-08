import io
import logging
from dataclasses import dataclass
from typing import List, Optional
import pymupdf
from PIL import Image

from app.config import settings
from app.models.extraction import PageExtractionMethod, PageProcessingStatus
from app.services.ocr.text_normalizer import TextNormalizer
from app.services.ocr.image_preprocessor import ImagePreprocessor
from app.services.ocr.tesseract_engine import TesseractEngine

logger = logging.getLogger("cargolens.ocr.pdf")


@dataclass
class PageExtractionResult:
    page_number: int
    raw_text: str
    extraction_method: PageExtractionMethod
    ocr_confidence: Optional[float]
    character_count: int
    processing_status: PageProcessingStatus
    error_message: Optional[str] = None


class PdfExtractor:
    """
    Implements a hybrid extraction strategy for PDF documents.
    Extracts digital text from electronic pages and selectively renders scanned pages
    at 300 DPI for Tesseract OCR.
    """

    def __init__(self, tesseract_engine: Optional[TesseractEngine] = None):
        self.tesseract_engine = tesseract_engine or TesseractEngine()

    @staticmethod
    def _pixmap_to_image(pix: pymupdf.Pixmap) -> Image.Image:
        """Converts PyMuPDF Pixmap into a PIL Image."""
        if pix.alpha:
            return Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def process_pdf(
        self,
        pdf_bytes: bytes,
        min_text_length: Optional[int] = None,
        dpi: Optional[int] = None,
    ) -> List[PageExtractionResult]:
        """
        Inspects PDF page by page:
        1. Checks for usable digital text.
        2. If meaningful digital text is present, retains it (DIGITAL_TEXT).
        3. If digital text is missing or sparse, renders page at 300 DPI and runs Tesseract OCR (OCR).
        """
        min_length = min_text_length or settings.OCR_MIN_TEXT_LENGTH
        render_dpi = dpi or settings.OCR_DPI

        results: List[PageExtractionResult] = []

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Failed to open PDF document: {str(e)}") from e

        try:
            page_count = len(doc)
            if page_count > settings.MAX_PDF_PAGES:
                raise ValueError(
                    f"PDF page count ({page_count}) exceeds maximum allowed limit of {settings.MAX_PDF_PAGES} pages."
                )

            for page_idx in range(page_count):
                page_num = page_idx + 1
                try:
                    page = doc[page_idx]

                    # 1. Attempt digital text extraction
                    digital_text_raw = page.get_text("text")
                    normalized_digital = TextNormalizer.normalize_text(digital_text_raw)

                    # 2. Check if digital text contains meaningful content
                    if TextNormalizer.is_meaningful_text(normalized_digital, min_length=min_length):
                        # Retain digital text; confidence is None (no fabricated confidence)
                        results.append(
                            PageExtractionResult(
                                page_number=page_num,
                                raw_text=normalized_digital,
                                extraction_method=PageExtractionMethod.DIGITAL_TEXT,
                                ocr_confidence=None,
                                character_count=len(normalized_digital),
                                processing_status=PageProcessingStatus.COMPLETED,
                            )
                        )
                    else:
                        # 3. Page is scanned image or empty digital page -> render and apply OCR
                        logger.info(
                            f"Page {page_num} has insufficient digital text ({len(normalized_digital)} chars). "
                            f"Rendering at {render_dpi} DPI for OCR."
                        )
                        pix = page.get_pixmap(dpi=render_dpi)
                        page_img = self._pixmap_to_image(pix)
                        pix = None  # Free pixmap memory

                        preprocessed = ImagePreprocessor.preprocess_for_ocr(page_img)
                        ocr_text_raw, ocr_conf = self.tesseract_engine.extract_text_and_confidence(preprocessed)
                        normalized_ocr = TextNormalizer.normalize_text(ocr_text_raw)

                        if not normalized_ocr:
                            # Empty page
                            results.append(
                                PageExtractionResult(
                                    page_number=page_num,
                                    raw_text="",
                                    extraction_method=PageExtractionMethod.EMPTY,
                                    ocr_confidence=None,
                                    character_count=0,
                                    processing_status=PageProcessingStatus.EMPTY,
                                )
                            )
                        else:
                            results.append(
                                PageExtractionResult(
                                    page_number=page_num,
                                    raw_text=normalized_ocr,
                                    extraction_method=PageExtractionMethod.OCR,
                                    ocr_confidence=ocr_conf,
                                    character_count=len(normalized_ocr),
                                    processing_status=PageProcessingStatus.COMPLETED,
                                )
                            )
                except Exception as page_exc:
                    logger.error(f"Error extracting PDF page {page_num}: {page_exc}", exc_info=True)
                    results.append(
                        PageExtractionResult(
                            page_number=page_num,
                            raw_text="",
                            extraction_method=PageExtractionMethod.FAILED,
                            ocr_confidence=None,
                            character_count=0,
                            processing_status=PageProcessingStatus.FAILED,
                            error_message=str(page_exc)[:500],
                        )
                    )
        finally:
            doc.close()

        return results
