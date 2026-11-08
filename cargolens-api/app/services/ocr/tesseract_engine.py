import os
import shutil
import logging
from typing import Tuple, Optional, List
from PIL import Image
import pytesseract

from app.config import settings

logger = logging.getLogger("cargolens.ocr.tesseract")


class OcrEngineError(RuntimeError):
    """Raised when the OCR engine binary or requested language pack is missing or fails."""
    pass


class TesseractEngine:
    """
    Manages Tesseract OCR execution, executable discovery, language pack verification,
    and confidence extraction.
    """

    def __init__(
        self,
        cmd: Optional[str] = None,
        tessdata_prefix: Optional[str] = None,
        default_lang: Optional[str] = None,
    ):
        self.cmd = cmd or settings.TESSERACT_CMD
        self.tessdata_prefix = tessdata_prefix or settings.TESSDATA_PREFIX
        self.default_lang = default_lang or settings.OCR_LANGUAGE

        self._configure_pytesseract()

    def _configure_pytesseract(self) -> None:
        """Resolves Tesseract command path and sets environment variables."""
        resolved_cmd = None

        # 1. Check explicitly configured path
        if self.cmd and os.path.exists(self.cmd) and os.path.isfile(self.cmd):
            resolved_cmd = self.cmd
        else:
            # 2. Check PATH
            which_cmd = shutil.which("tesseract")
            if which_cmd:
                resolved_cmd = which_cmd
            elif os.name == "nt":
                # 3. Check common Windows standard install path
                default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                if os.path.exists(default_win_path):
                    resolved_cmd = default_win_path

        if resolved_cmd:
            pytesseract.pytesseract.tesseract_cmd = resolved_cmd

        if self.tessdata_prefix and os.path.isdir(self.tessdata_prefix):
            os.environ["TESSDATA_PREFIX"] = self.tessdata_prefix

    def check_availability(self) -> Tuple[bool, str, List[str]]:
        """
        Validates whether Tesseract executable and requested language data are available.
        Returns: (is_available, version_string, list_of_languages)
        """
        try:
            version = pytesseract.get_tesseract_version()
            langs = pytesseract.get_languages()
            has_lang = self.default_lang in langs
            return (has_lang, str(version), langs)
        except Exception as e:
            logger.warning(f"Tesseract availability check failed: {e}")
            return (False, f"Unavailable: {str(e)}", [])

    def extract_text_and_confidence(
        self,
        image: Image.Image,
        lang: Optional[str] = None,
    ) -> Tuple[str, Optional[float]]:
        """
        Executes Tesseract OCR on a PIL Image.
        Returns extracted text and average OCR confidence (0.0 to 100.0).
        If image is blank or has no valid text tokens, confidence is None.
        """
        ocr_lang = lang or self.default_lang

        # Verify engine availability
        is_avail, version_info, available_langs = self.check_availability()
        if not is_avail:
            raise OcrEngineError(
                f"Tesseract OCR is not available or missing '{ocr_lang}' language data. "
                f"Available languages: {available_langs}. Version: {version_info}"
            )

        try:
            # Extract detailed word-level data including confidences
            data = pytesseract.image_to_data(
                image,
                lang=ocr_lang,
                output_type=pytesseract.Output.DICT,
            )

            # Reconstruct lines and calculate word confidences
            valid_confidences = []
            words = []
            current_line_words = []
            last_line_num = -1

            n_boxes = len(data.get("text", []))
            for i in range(n_boxes):
                text_word = data["text"][i].strip()
                conf_val = float(data["conf"][i])
                line_num = data["line_num"][i]

                if text_word:
                    # Valid confidence from Tesseract is 0..100 (-1 means not a word)
                    if conf_val >= 0:
                        valid_confidences.append(conf_val)

                    if last_line_num != -1 and line_num != last_line_num:
                        if current_line_words:
                            words.append(" ".join(current_line_words))
                            current_line_words = []

                    current_line_words.append(text_word)
                    last_line_num = line_num

            if current_line_words:
                words.append(" ".join(current_line_words))

            extracted_text = "\n".join(words).strip()

            avg_conf: Optional[float] = None
            if valid_confidences:
                avg_conf = round(sum(valid_confidences) / len(valid_confidences), 2)

            return extracted_text, avg_conf
        except Exception as e:
            if isinstance(e, OcrEngineError):
                raise
            raise OcrEngineError(f"Tesseract OCR extraction failed: {str(e)}") from e
