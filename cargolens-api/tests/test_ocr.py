import io
import pytest
from PIL import Image, ImageDraw
import pymupdf

from app.models.extraction import (
    ExtractionMethod,
    ExtractionQualityStatus,
    PageExtractionMethod,
    PageProcessingStatus,
)
from app.services.ocr.text_normalizer import TextNormalizer
from app.services.ocr.image_preprocessor import ImagePreprocessor
from app.services.ocr.tesseract_engine import TesseractEngine, OcrEngineError
from app.services.ocr.pdf_extractor import PdfExtractor
from app.services.ocr.pipeline import OcrPipeline
from app.services.ocr.quality_assessment import QualityAssessmentService
from uuid import uuid4


def create_digital_pdf(page_texts: list[str]) -> bytes:
    """Generates a valid digital multi-page PDF using PyMuPDF."""
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_text_image(text: str, width: int = 500, height: int = 150, format: str = "PNG") -> bytes:
    """Renders text onto a PIL Image and returns bytes."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def create_scanned_pdf(image_texts: list[str]) -> bytes:
    """Generates a PDF where each page embeds an image with no selectable digital text."""
    doc = pymupdf.open()
    for text in image_texts:
        img_bytes = create_text_image(text, width=600, height=200)
        page = doc.new_page(width=595, height=842)
        page.insert_image(pymupdf.Rect(50, 50, 500, 200), stream=img_bytes)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_hybrid_pdf() -> bytes:
    """Generates a 2-page PDF: Page 1 has digital text, Page 2 has an embedded scanned image."""
    doc = pymupdf.open()
    # Page 1: Digital text
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 72), "COMMERCIAL INVOICE\nInvoice Number: DIGI-INV-2026\nTotal: $18,450.00 USD", fontsize=12)

    # Page 2: Scanned image
    img_bytes = create_text_image("PACKING LIST DETAILS\nTOTAL PACKAGES: 40 DRUMS\nWEIGHT: 800.5 KG", width=600, height=200)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_image(pymupdf.Rect(50, 50, 500, 200), stream=img_bytes)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# =========================================================================
# A. Text Normalizer Tests
# =========================================================================

def test_text_normalizer_preserves_characters_and_currencies():
    """
    Verifies that normalization strips non-printable control characters
    while preserving numbers, decimals, currencies ($ € ₹ £), slashes, and invoice codes.
    """
    raw_input = (
        "COMMERCIAL INVOICE\x00\x07\n"
        "Invoice No: INV/2026/099-A\r\n"
        "Total Value: $45,250.50 USD / €38,100.00 EUR / ₹37,50,000 INR\n\n\n\n"
        "HS Code: 8471.30.10 \t\n"
        "Gross Weight: 1,250.750 kg\n"
    )
    normalized = TextNormalizer.normalize_text(raw_input)

    assert "\x00" not in normalized
    assert "\x07" not in normalized
    assert "\r" not in normalized
    assert "INV/2026/099-A" in normalized
    assert "$45,250.50 USD" in normalized
    assert "€38,100.00 EUR" in normalized
    assert "₹37,50,000 INR" in normalized
    assert "8471.30.10" in normalized
    assert "1,250.750 kg" in normalized
    # Consecutive blank lines collapsed
    assert "\n\n\n" not in normalized


def test_text_normalizer_meaningful_text_threshold():
    """Verifies alphanumeric counting and threshold detection."""
    assert TextNormalizer.is_meaningful_text("Invoice No 12345", min_length=10) is True
    assert TextNormalizer.is_meaningful_text("   ... ---   ", min_length=5) is False
    assert TextNormalizer.is_meaningful_text("", min_length=5) is False
    assert TextNormalizer.is_meaningful_text(None, min_length=5) is False


# =========================================================================
# B. Digital PDF Tests
# =========================================================================

@pytest.mark.asyncio
async def test_digital_pdf_extraction_no_unnecessary_ocr():
    """
    Verifies that a digital PDF is extracted directly via PyMuPDF without running OCR.
    Confidence score must remain None (no fabricated confidence scores).
    Page order and multiple pages are strictly preserved.
    """
    page_1_text = "INVOICE PAGE ONE\nConsignee: Global Cargo Ltd\nInvoice No: EXP-2026-001\nTotal: $25,000.00"
    page_2_text = "INVOICE PAGE TWO\nItem: Industrial Machinery Parts\nQuantity: 10 Units\nOrigin: Germany"

    pdf_bytes = create_digital_pdf([page_1_text, page_2_text])

    pipeline = OcrPipeline()
    result = await pipeline.process_document(pdf_bytes, ".pdf", uuid4())

    assert result.page_count == 2
    assert result.processed_page_count == 2
    assert result.failed_page_count == 0
    assert result.extraction_method == ExtractionMethod.DIGITAL_TEXT
    assert result.quality_status == ExtractionQualityStatus.GOOD
    assert result.avg_confidence is None  # Must NOT fabricate confidence for digital text!

    # Check Page 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].extraction_method == PageExtractionMethod.DIGITAL_TEXT
    assert result.pages[0].ocr_confidence is None
    assert "INVOICE PAGE ONE" in result.pages[0].raw_text
    assert "EXP-2026-001" in result.pages[0].raw_text

    # Check Page 2
    assert result.pages[1].page_number == 2
    assert result.pages[1].extraction_method == PageExtractionMethod.DIGITAL_TEXT
    assert result.pages[1].ocr_confidence is None
    assert "INVOICE PAGE TWO" in result.pages[1].raw_text
    assert "Industrial Machinery" in result.pages[1].raw_text


# =========================================================================
# C. Scanned PDF Tests
# =========================================================================

@pytest.mark.asyncio
async def test_scanned_pdf_extraction_renders_and_runs_ocr():
    """
    Verifies that a scanned PDF page (image without digital text) is rendered at 300 DPI,
    processed via Tesseract OCR, and has its OCR confidence score recorded.
    """
    scanned_text = "SCANNED BILL OF LADING CARGOLENS"
    pdf_bytes = create_scanned_pdf([scanned_text])

    pipeline = OcrPipeline()
    result = await pipeline.process_document(pdf_bytes, ".pdf", uuid4())

    assert result.page_count == 1
    assert result.processed_page_count == 1
    assert result.extraction_method == ExtractionMethod.OCR
    assert result.pages[0].extraction_method == PageExtractionMethod.OCR
    assert result.pages[0].ocr_confidence is not None
    assert result.pages[0].ocr_confidence > 0.0
    assert result.avg_confidence is not None

    # Text should contain OCR extracted tokens
    extracted_clean = result.pages[0].raw_text.replace(" ", "")
    assert "SCANNED" in extracted_clean or "BILL" in extracted_clean


# =========================================================================
# D. Hybrid PDF Tests
# =========================================================================

@pytest.mark.asyncio
async def test_hybrid_pdf_extraction_page_decisions():
    """
    Verifies a 2-page hybrid PDF:
    Page 1 (digital text) is extracted digitally (DIGITAL_TEXT, confidence=None).
    Page 2 (scanned image) is rendered and OCR'd (OCR, confidence > 0).
    Overall document extraction method is HYBRID.
    """
    pdf_bytes = create_hybrid_pdf()

    pipeline = OcrPipeline()
    result = await pipeline.process_document(pdf_bytes, ".pdf", uuid4())

    assert result.page_count == 2
    assert result.processed_page_count == 2
    assert result.extraction_method == ExtractionMethod.HYBRID

    # Page 1: Digital
    p1 = result.pages[0]
    assert p1.page_number == 1
    assert p1.extraction_method == PageExtractionMethod.DIGITAL_TEXT
    assert p1.ocr_confidence is None
    assert "DIGI-INV-2026" in p1.raw_text

    # Page 2: OCR
    p2 = result.pages[1]
    assert p2.page_number == 2
    assert p2.extraction_method == PageExtractionMethod.OCR
    assert p2.ocr_confidence is not None
    assert p2.ocr_confidence > 0.0


# =========================================================================
# E. Image OCR Tests (PNG, JPEG, Grayscale)
# =========================================================================

@pytest.mark.asyncio
async def test_image_ocr_png():
    """Verifies OCR execution on a valid PNG image."""
    png_bytes = create_text_image("PNG INVOICE CONTAINER CARGO", width=600, height=150, format="PNG")

    pipeline = OcrPipeline()
    result = await pipeline.process_document(png_bytes, ".png", uuid4())

    assert result.page_count == 1
    assert result.processed_page_count == 1
    assert result.extraction_method == ExtractionMethod.OCR
    assert result.avg_confidence is not None
    assert result.avg_confidence > 0.0
    assert len(result.raw_text) > 0


@pytest.mark.asyncio
async def test_image_ocr_jpeg():
    """Verifies OCR execution on a valid JPEG image."""
    jpeg_bytes = create_text_image("JPEG PACKING SPECIFICATION", width=600, height=150, format="JPEG")

    pipeline = OcrPipeline()
    result = await pipeline.process_document(jpeg_bytes, ".jpeg", uuid4())

    assert result.page_count == 1
    assert result.processed_page_count == 1
    assert result.extraction_method == ExtractionMethod.OCR
    assert result.avg_confidence is not None


def test_image_preprocessor_grayscale_and_contrast():
    """Verifies image preprocessing with RGBA, RGB and Grayscale conversion."""
    rgba_img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
    processed = ImagePreprocessor.preprocess_for_ocr(rgba_img, check_orientation=False)

    assert processed.mode == "L"  # Converted to Grayscale
    assert processed.width == 200
    assert processed.height == 200


def test_image_preprocessor_rejects_oversized():
    """Verifies that images exceeding maximum dimension limits are rejected."""
    oversized = Image.new("RGB", (10001, 100), "white")
    with pytest.raises(ValueError, match="exceed maximum allowed limit"):
        ImagePreprocessor.validate_dimensions(oversized)


# =========================================================================
# F. Quality Assessment & Edge Case Tests
# =========================================================================

def test_quality_assessment_empty_document():
    """Verifies EMPTY quality status when character count is 0."""
    quality = QualityAssessmentService.evaluate_document_quality(
        total_pages=1,
        processed_pages=0,
        failed_pages=0,
        character_count=0,
        avg_confidence=None,
    )
    assert quality == ExtractionQualityStatus.EMPTY


def test_quality_assessment_low_confidence():
    """Verifies LOW_CONFIDENCE quality status when average confidence is below threshold."""
    quality = QualityAssessmentService.evaluate_document_quality(
        total_pages=1,
        processed_pages=1,
        failed_pages=0,
        character_count=100,
        avg_confidence=45.0,  # Below default 60.0%
        min_confidence=60.0,
    )
    assert quality == ExtractionQualityStatus.LOW_CONFIDENCE


def test_quality_assessment_partial_failure():
    """Verifies PARTIAL quality status when some pages fail."""
    quality = QualityAssessmentService.evaluate_document_quality(
        total_pages=3,
        processed_pages=2,
        failed_pages=1,
        character_count=200,
        avg_confidence=85.0,
    )
    assert quality == ExtractionQualityStatus.PARTIAL


def test_tesseract_diagnostics_availability():
    """Verifies Tesseract availability check and version reporting."""
    engine = TesseractEngine()
    is_avail, version_str, langs = engine.check_availability()
    assert is_avail is True
    assert "eng" in langs
    assert len(version_str) > 0


def test_tesseract_missing_language_raises_error(monkeypatch):
    """Verifies clear exception is raised if an unavailable language is requested."""
    engine = TesseractEngine(default_lang="fra_nonexistent")
    img = Image.new("RGB", (100, 100), "white")
    with pytest.raises(OcrEngineError, match="missing 'fra_nonexistent' language data"):
        engine.extract_text_and_confidence(img)
