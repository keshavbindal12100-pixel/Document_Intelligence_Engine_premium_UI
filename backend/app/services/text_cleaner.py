import re
import unicodedata
from typing import Any


class TextCleaner:
    """Production text cleaning and normalization for OCR outputs."""

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Apply comprehensive text normalization pipeline."""
        if not raw_text:
            return ""

        # 1. Unicode Normalization (NFKC converts ligatures, compatibility characters)
        text = unicodedata.normalize("NFKC", raw_text)

        # 2. Normalize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Remove non-printable control characters (preserving \n and \t)
        text = "".join(
            ch for ch in text if ch in "\n\t" or not unicodedata.category(ch).startswith("C")
        )

        # 4. Fix hyphenation across line breaks: "deve-\nlopment" -> "development"
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

        # 5. Coalesce multiple horizontal whitespace (spaces, tabs) into single space
        text = re.sub(r"[ \t]+", " ", text)

        # 6. Remove trailing/leading spaces on each line
        lines = [line.strip() for line in text.split("\n")]

        # 7. Collapse more than 2 consecutive newlines into 2 newlines (preserve paragraphs)
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    @staticmethod
    def get_text_statistics(text: str) -> dict[str, Any]:
        """Compute basic structural metrics of cleaned text."""
        if not text:
            return {
                "character_count": 0,
                "word_count": 0,
                "line_count": 0,
                "is_empty": True,
            }

        words = text.split()
        lines = [line for line in text.split("\n") if line.strip()]

        return {
            "character_count": len(text),
            "word_count": len(words),
            "line_count": len(lines),
            "is_empty": len(words) == 0,
        }


text_cleaner = TextCleaner()
