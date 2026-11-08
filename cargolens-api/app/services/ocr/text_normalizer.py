import re
from typing import Optional


class TextNormalizer:
    """
    Normalizes extracted document text safely.
    Removes control characters while strictly preserving all currency symbols, numbers,
    punctuation, invoice codes, and meaningful line breaks.
    """

    # Matches non-printable ASCII control characters except \t and \n
    _CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    # Matches 3 or more consecutive newlines
    _EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")

    @classmethod
    def normalize_text(cls, text: Optional[str]) -> str:
        """
        Cleans and normalizes raw extracted text.
        Preserves reading order, numbers, decimals, currency symbols, and punctuation.
        """
        if not text:
            return ""

        # 1. Standardize line endings to \n
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Strip non-printable control characters
        normalized = cls._CONTROL_CHAR_RE.sub("", normalized)

        # 3. Clean line-by-line whitespace
        lines = [line.rstrip() for line in normalized.split("\n")]
        cleaned = "\n".join(lines)

        # 4. Collapse excessive consecutive blank lines (limit to max 2)
        cleaned = cls._EXCESSIVE_NEWLINES_RE.sub("\n\n", cleaned)

        return cleaned.strip()

    @classmethod
    def count_alphanumeric_characters(cls, text: Optional[str]) -> int:
        """Counts only alphanumeric characters to assess meaningful content."""
        if not text:
            return 0
        return sum(1 for c in text if c.isalnum())

    @classmethod
    def is_meaningful_text(cls, text: Optional[str], min_length: int = 15) -> bool:
        """
        Determines whether text extracted digitally contains sufficient meaningful content
        or whether the page appears to be scanned/blank.
        """
        if not text:
            return False
        clean = cls.normalize_text(text)
        alphanumeric_count = cls.count_alphanumeric_characters(clean)
        return alphanumeric_count >= min_length
