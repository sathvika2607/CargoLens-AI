import logging
from typing import Tuple, Optional
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

from app.config import settings

logger = logging.getLogger("cargolens.ocr.preprocessor")


class ImagePreprocessor:
    """
    Implements conservative image preprocessing for scanned customs documents and images.
    Preserves small text, decimal points, invoice codes, and currency symbols.
    """

    @classmethod
    def validate_dimensions(cls, img: Image.Image) -> None:
        """Enforces configured maximum image dimension constraints."""
        max_dim = settings.MAX_IMAGE_DIMENSION
        if img.width > max_dim or img.height > max_dim:
            raise ValueError(
                f"Image dimensions ({img.width}x{img.height}) exceed maximum allowed limit of {max_dim}px"
            )

    @classmethod
    def detect_and_correct_orientation(cls, img: Image.Image) -> Tuple[Image.Image, int]:
        """
        Uses Tesseract Orientation and Script Detection (OSD) to correct rotated documents.
        Safely falls back to 0 degrees if OSD fails (e.g. low-text, drawings, or unsupported formats).
        """
        try:
            # Run OSD on a grayscale copy
            gray_for_osd = img.convert("L")
            # Tesseract OSD
            osd_data = pytesseract.image_to_osd(gray_for_osd, output_type=pytesseract.Output.DICT)
            rotate_angle = osd_data.get("rotate", 0)
            conf = osd_data.get("orientation_conf", 0.0)

            # Only rotate if confidence is above threshold and angle is non-zero
            if rotate_angle in (90, 180, 270) and conf >= 5.0:
                logger.info(f"OSD detected {rotate_angle} deg rotation (confidence: {conf}). Correcting orientation.")
                # PIL rotates counter-clockwise; Tesseract reports clockwise correction needed
                corrected = img.rotate(360 - rotate_angle, expand=True)
                return corrected, rotate_angle
        except Exception as e:
            # OSD failure is common on non-standard, sparse, or graphic pages; ignore gracefully
            logger.debug(f"Tesseract OSD check bypassed or inconclusive: {e}")

        return img, 0

    @classmethod
    def preprocess_for_ocr(cls, img: Image.Image, check_orientation: bool = True) -> Image.Image:
        """
        Performs conservative preprocessing:
        1. Dimension validation
        2. Orientation correction via OSD (optional)
        3. Color conversion to high-fidelity grayscale
        4. Moderate contrast enhancement
        Avoids harsh thresholding to preserve small decimal dots and punctuation.
        """
        cls.validate_dimensions(img)

        # 1. Orientation check
        processed = img
        if check_orientation:
            processed, _ = cls.detect_and_correct_orientation(processed)

        # 2. Convert to RGB if palette (P) or RGBA to ensure clean grayscale conversion
        if processed.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", processed.size, (255, 255, 255))
            if processed.mode == "P":
                processed = processed.convert("RGBA")
            if processed.mode in ("RGBA", "LA"):
                background.paste(processed, mask=processed.split()[-1])
            processed = background
        elif processed.mode != "RGB" and processed.mode != "L":
            processed = processed.convert("RGB")

        # 3. High quality Grayscale conversion
        gray = processed.convert("L")

        # 4. Moderate contrast enhancement (factor ~1.3)
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.3)

        return enhanced
