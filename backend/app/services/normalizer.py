import re

from dateutil import parser as date_parser


class ValueNormalizer:
    def normalize_whitespace(self, text: str | None) -> str | None:
        if not text:
            return None
        s = re.sub(r"\s+", " ", str(text)).strip()
        return s if s else None

    def normalize_amount(self, text: str | None) -> float | None:
        if not text:
            return None
        raw = str(text).strip()
        match = re.search(r"[-+]?\d[\d.,]*", raw)
        if not match:
            return None
        val_str = match.group(0)

        if "," in val_str and "." in val_str:
            if val_str.rfind(",") > val_str.rfind("."):
                val_str = val_str.replace(".", "").replace(",", ".")
            else:
                val_str = val_str.replace(",", "")
        elif "," in val_str and "." not in val_str:
            parts = val_str.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                val_str = val_str.replace(",", ".")
            else:
                val_str = val_str.replace(",", "")

        try:
            return float(val_str)
        except ValueError:
            return None

    def normalize_currency(self, text: str | None) -> tuple[str | None, str | None]:
        if not text:
            return (None, None)
        txt = str(text).upper()
        if re.search(r"\bEUR\b", txt) or "€" in txt:
            return ("EUR", "€")
        if re.search(r"\bGBP\b", txt) or "£" in txt:
            return ("GBP", "£")
        if re.search(r"\bCAD\b", txt):
            return ("CAD", "$")
        if re.search(r"\bAUD\b", txt):
            return ("AUD", "$")
        if re.search(r"\bINR\b", txt) or "₹" in txt or re.search(r"\bRS\b", txt):
            return ("INR", "₹")
        if re.search(r"\bJPY\b", txt) or "¥" in txt:
            return ("JPY", "¥")
        if "$" in txt or re.search(r"\bUSD\b", txt):
            return ("USD", "$")
        return (None, None)

    def normalize_date(self, text: str | None) -> str | None:
        if not text:
            return None
        s = str(text).strip()
        if not re.search(r"\d", s) or "Invalid" in s:
            return None
        try:
            dt = date_parser.parse(s, dayfirst=False)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    def normalize_phone(self, text: str | None) -> str | None:
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", str(text))
        if not digits:
            return None
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return f"+{digits}"


normalizer = ValueNormalizer()
