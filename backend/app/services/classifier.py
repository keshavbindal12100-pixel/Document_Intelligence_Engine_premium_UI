import re
from typing import Any, TypedDict


class ClassificationRule(TypedDict):
    primary_keywords: list[str]
    secondary_keywords: list[str]
    base_weight: float


class DocumentClassifier:
    """Production-grade keyword & regex heuristic document classifier."""

    CLASSIFICATION_RULES: dict[str, ClassificationRule] = {
        "invoice": {
            "primary_keywords": [
                r"\btax\s+invoice\b",
                r"\binvoice\b",
                r"\bbill\s+to\b",
                r"\binvoice\s+(?:no|num|number|#)\b",
                r"\bamount\s+due\b",
                r"\btotal\s+due\b",
                r"\bsubtotal\b",
                r"\bpayment\s+terms\b",
                r"\bremit\s+to\b",
            ],
            "secondary_keywords": [
                r"\bdue\s+date\b",
                r"\bunit\s+price\b",
                r"\bitem\s+description\b",
                r"\bqty\b",
                r"\bquantity\b",
                r"\bvat\b",
                r"\bgst\b",
                r"\bbalance\s+due\b",
            ],
            "base_weight": 1.2,
        },
        "purchase_order": {
            "primary_keywords": [
                r"\bpurchase\s+order\b",
                r"\bp\.?o\.?\s+(?:number|no|#)\b",
                r"\bpo\s+date\b",
                r"\brequisition\s+(?:no|#)\b",
                r"\bvendor\s+p\.?o\.?\b",
            ],
            "secondary_keywords": [
                r"\bship\s+to\b",
                r"\border\s+date\b",
                r"\bbuyer\b",
                r"\bshipping\s+method\b",
                r"\bdelivery\s+terms\b",
                r"\bdeliver\s+to\b",
            ],
            "base_weight": 1.3,
        },
        "form": {
            "primary_keywords": [
                r"\bapplication\s+form\b",
                r"\bregistration\s+form\b",
                r"\bintake\s+form\b",
                r"\bpatient\s+information\b",
                r"\bcontact\s+information\s+form\b",
                r"\bquestionnaire\b",
                r"\bform\s+id\b",
            ],
            "secondary_keywords": [
                r"\bdate\s+of\s+birth\b",
                r"\bd\.?o\.?b\.?\b",
                r"\bapplicant\s+name\b",
                r"\bsignature\s*(?::|__)\b",
                r"\bemergency\s+contact\b",
                r"\bmarital\s+status\b",
                r"\bgender\b",
                r"\bterms\s+and\s+conditions\s+agreement\b",
                r"\[\s*[xX✓]\s*\]",
            ],
            "base_weight": 1.1,
        },
        "contract": {
            "primary_keywords": [
                r"\bcontract\b",
                r"\bagreement\b",
                r"\bmaster\s+services\s+agreement\b",
                r"\bnon-disclosure\s+agreement\b",
                r"\bterms\s+of\s+service\b",
                r"\blegal\s+agreement\b",
            ],
            "secondary_keywords": [
                r"\bparties\b",
                r"\beffective\s+date\b",
                r"\bexpiry\s+date\b",
                r"\bexpiration\s+date\b",
                r"\bgoverning\s+law\b",
                r"\bjurisdiction\b",
                r"\bconfidentiality\b",
                r"\bindemnification\b",
                r"\btermination\b",
            ],
            "base_weight": 1.2,
        },
        "receipt": {
            "primary_keywords": [
                r"\breceipt\b",
                r"\bsales\s+receipt\b",
                r"\bpayment\s+receipt\b",
                r"\bmerchant\b",
                r"\bpos\s+terminal\b",
            ],
            "secondary_keywords": [
                r"\bcard\s+number\b",
                r"\bauth\s+code\b",
                r"\bchange\s+due\b",
                r"\bcash\b",
                r"\bvisa\b|\bmastercard\b|\bamex\b",
                r"\btotal\s+paid\b",
            ],
            "base_weight": 1.1,
        },
    }

    def classify(self, text: str) -> dict[str, Any]:
        """Classify OCR text into a recognized document type with confidence scoring."""
        if not text or len(text.strip()) == 0:
            return {
                "document_type": "unknown",
                "confidence": 0.0,
                "scores": dict.fromkeys(self.CLASSIFICATION_RULES, 0.0),
            }

        text_lower = text.lower()
        scores: dict[str, float] = {}

        for doc_type, rules in self.CLASSIFICATION_RULES.items():
            primary_matches = sum(
                1 for pat in rules["primary_keywords"] if re.search(pat, text_lower) is not None
            )
            secondary_matches = sum(
                1 for pat in rules["secondary_keywords"] if re.search(pat, text_lower) is not None
            )

            # Scoring algorithm: primary keywords carry higher weight
            raw_score = (primary_matches * 2.5 + secondary_matches * 1.0) * float(
                rules["base_weight"]
            )
            scores[doc_type] = raw_score

        # Determine highest scoring category
        best_type, max_score = max(scores.items(), key=lambda item: item[1])

        if max_score <= 0.5:
            return {
                "document_type": "unknown",
                "confidence": 0.0,
                "scores": {k: round(v, 2) for k, v in scores.items()},
            }

        # Calibration: scale max score into a probability [0.50, 0.99]
        total_score = sum(scores.values())
        dominance_ratio = max_score / total_score if total_score > 0 else 0.5
        calibrated_confidence = min(
            0.99, round(0.60 + (dominance_ratio * 0.35) + min(0.04, max_score * 0.005), 2)
        )

        return {
            "document_type": best_type,
            "confidence": calibrated_confidence,
            "scores": {k: round(v, 2) for k, v in scores.items()},
        }


document_classifier = DocumentClassifier()
