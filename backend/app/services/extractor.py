import logging
import re
from typing import Any

from backend.app.models.extracted_field import FieldType
from backend.app.services.normalizer import normalizer

logger = logging.getLogger(__name__)

nlp: Any = None
try:
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = None
except ImportError:
    nlp = None


class HybridExtractor:
    """Production hybrid extraction engine combining Regex, spaCy NER, Anchor matching, and Templates."""

    # Anchor patterns for Invoices
    INVOICE_ANCHORS = {
        "invoice_number": [
            r"(?i)\b(?:invoice\s+(?:number|num|no|id|#)|invoice\s*#|1nvoice\s+(?:number|num|no|id|#)?|bill\s+(?:number|no|id|#))\s*[:#.]\s*([A-Za-z0-9\-_/]+)",
            r"(?i)\b(?:tax\s+invoice)\s+(?:no|num|number|#)?\s*[:#.]?\s*(INV-[A-Za-z0-9\-_/]+|[A-Za-z]{2,}\d+[\w\-]*)",
            r"(?i)\b(?:invoice\s*#)\s*([A-Za-z0-9\-_/]+)",
            r"(?i)\b(?:inv\b|inv\.)\s*[:#.]\s*([A-Za-z0-9\-_/]+)",
            r"(?i)\b(?:invoice\s+id)\s*[:#.]\s*([A-Za-z0-9\-_/]+)",
        ],
        "invoice_date": [
            r"(?i)\b(?:invoice\s+date|bill\s+date|date\s+of\s+issue|issued\s+date|lnvoice\s+date|\bdate)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:due|po|terms|total|inv|remit)|$|\n)",
        ],
        "due_date": [
            r"(?im)^\s*due\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:total|amount|terms)|$|\n)",
            r"(?i)\b(?:due\s+date|payment\s+due|pay\s+by)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:total|amount|terms)|$|\n)",
        ],
        "total": [
            r"(?i)\b(?:grand\s+total|total\s+amount\s+(?:payable|due)|total\s+amount|total\s+due|amount\s+due|balance\s+due|tot@l(?:\s+amount)?)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
            r"(?i)(?<!sub)(?<!sub-)(?<!sub\s)\btotal\s*[:.]\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
        "subtotal": [
            r"(?i)\b(?:sub-total|sub\s+total|subtotal|net\s+amount)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
        "tax": [
            r"(?i)\b(?:sales\s+tax|vat|gst|\btax)\s*(?:\([^)]*\))?\s*[:=]\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
        "discount": [
            r"(?i)\b(?:discount|rebate|savings)\s*[:=.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
    }

    # Anchor patterns for Forms
    FORM_ANCHORS = {
        "name": [
            r"(?i)\b(?:full\s+name|applicant\s+name|patient\s+name|\bname)\s*[:_.]\s*([A-Za-z\s.'-]+?)(?=\s+(?:email|phone|date|dob|address)|$|\n)",
        ],
        "email": [
            r"(?i)\b(?:email\s+address|e-mail|\bemail)\s*[:_.]\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        ],
        "phone": [
            r"(?i)\b(?:phone\s+number|telephone|contact\s+no|mobile|\bphone|\btel)\s*[:_.]\s*([+()0-9\s\-]{7,20})",
        ],
        "address": [
            r"(?i)\b(?:residential\s+address|street\s+address|mailing\s+address|\baddress)\s*[:_.]\s*([A-Za-z0-9\s,.'#-]+?)(?=\s+(?:city|state|zip|phone|email|date)|$|\n\n)",
        ],
        "form_id": [
            r"(?i)\b(?:form\s+id|form\s+number|document\s+id|reference\s+no)\s*[:#.]\s*([A-Za-z0-9\-_/]+)",
        ],
        "date": [
            r"(?i)\b(?:submission\s+date|date\s+signed|date\s+of\s+birth|dob|\bdate)\s*[:_.]\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:signature|status|name)|$|\n)",
        ],
    }

    # Anchor patterns for Purchase Orders
    PO_ANCHORS = {
        "po_number": [
            r"(?i)\b(?:po\s+(?:number|num|no|id|#)|p\.?o\.?\s*#|purchase\s+order\s+(?:number|no|#)?|requisition\s+(?:no|#)?)\s*[:#.]\s*([A-Za-z0-9\-_/]+)",
        ],
        "vendor": [
            r"(?i)\b(?:vendor|supplier|seller)\s*[:.]\s*([A-Za-z0-9\s.,'&-]+?)(?=\s+(?:ship|order|date|buyer|item)|$|\n)",
        ],
        "buyer": [
            r"(?i)\b(?:buyer|purchaser|requisitioner|contact|purchased\s+by)\s*[:.]\s*([A-Za-z0-9\s.,'&-]+?)(?=\s+(?:ship|delivery|date|vendor|item)|$|\n)",
        ],
        "date": [
            r"(?i)\b(?:po\s+date|order\s+date|date\s+issued|requisition\s+date|\bdate)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:delivery|ship|due|terms|vendor|buyer)|$|\n)",
        ],
        "delivery_information": [
            r"(?i)\b(?:ship\s+to|deliver\s+to|shipping\s+method|delivery\s+terms|delivery\s+address)\s*[:.]?\s*([A-Za-z0-9\s,.'#-]+?)(?=\s+(?:vendor|date|buyer|item|subtotal|total)|$|\n\n)",
        ],
        "total": [
            r"(?i)\b(?:total\s+amount|order\s+total|po\s+total|total\s+due|grand\s+total)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
            r"(?i)(?<!sub)(?<!sub-)(?<!sub\s)\btotal\s*[:.]\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
        "subtotal": [
            r"(?i)\b(?:sub-total|sub\s+total|subtotal|net\s+amount)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
        "tax": [
            r"(?i)\b(?:sales\s+tax|vat|gst|\btax)\s*(?:\([^)]*\))?\s*[:=]\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
    }

    # Anchor patterns for Contracts
    CONTRACT_ANCHORS = {
        "parties": [
            r"(?i)\b(?:between|parties|by\s+and\s+between)\s*[:.]?\s*([A-Za-z0-9\s,.'&()-]+?)(?=\s+(?:and\s+[A-Z]|effective|dated)|$|\n)",
        ],
        "effective_date": [
            r"(?i)\b(?:effective\s+date|commencement\s+date|start\s+date|dated\s+as\s+of)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:expiry|expiration|term|between)|$|\n)",
        ],
        "expiry_date": [
            r"(?i)\b(?:expiry\s+date|expiration\s+date|end\s+date|termination\s+date)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:renewal|governing|value)|$|\n)",
        ],
        "renewal_date": [
            r"(?i)\b(?:renewal\s+date|auto-renewal\s+notice|renewal\s+term)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:value|governing|jurisdiction)|$|\n)",
        ],
        "contract_value": [
            r"(?i)\b(?:contract\s+value|total\s+value|contract\s+amount|fee|total\s+compensation)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+(?:eur|usd|gbp)|\s+[A-Za-z]|$|\n)",
        ],
        "payment_terms": [
            r"(?i)\b(?:payment\s+terms|terms\s+of\s+payment|remittance)\s*[:.]?\s*([A-Za-z0-9\s.,'-]+?)(?=\s+(?:governing|jurisdiction|expiry)|$|\n)",
        ],
        "governing_jurisdiction": [
            r"(?i)\b(?:governing\s+law|jurisdiction|governed\s+by\s+the\s+laws\s+of)\s*[:.]?\s*([A-Za-z0-9\s.,'-]+?)(?=\s+(?:key|clauses|parties)|$|\n)",
        ],
    }

    # Anchor patterns for Receipts
    RECEIPT_ANCHORS = {
        "merchant": [
            r"(?i)\b(?:merchant|store|shop|retailer|vendor)\s*[:.]\s*([A-Za-z0-9\s.,'-]+?)(?=\s+(?:date|receipt|tel|tax|total)|$|\n)",
        ],
        "date": [
            r"(?i)\b(?:receipt\s+date|transaction\s+date|purchase\s+date|\bdate)\s*[:.]?\s*([A-Za-z0-9\s,\-\./]+?)(?=\s+(?:time|cashier|total|items)|$|\n)",
        ],
        "tax": [
            r"(?i)\b(?:sales\s+tax|vat|gst|\btax)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+[A-Za-z]|$|\n)",
        ],
        "total": [
            r"(?i)\b(?:total\s+amount|total\s+paid|balance|grand\s+total|amount\s+paid)\s*[:.]?\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+[A-Za-z]|$|\n)",
            r"(?i)(?<!sub)(?<!sub-)(?<!sub\s)\btotal\s*[:.]\s*([$€£¥₹]?\s*[\d][\d.,\s]*?)(?=\s*[€$£¥₹]|\s+[A-Za-z]|$|\n)",
        ],
        "payment_method": [
            r"(?i)\b(?:payment\s+method|paid\s+by|tender|card\s+type)\s*[:.]?\s*([A-Za-z0-9\s\-]+?)(?=\s+(?:auth|card|total)|$|\n)",
        ],
    }

    def _extract_by_regex_anchors(
        self, text: str, anchor_dict: dict[str, list[str]]
    ) -> dict[str, dict[str, Any]]:
        """Extract fields by scanning regex anchors against text lines and blocks."""
        results: dict[str, dict[str, Any]] = {}

        for field_name, patterns in anchor_dict.items():
            matched = False
            for pat in patterns:
                match = re.search(pat, text)
                if match:
                    raw_val = match.group(1).strip()
                    if raw_val and len(raw_val) > 0:
                        results[field_name] = {
                            "value": raw_val,
                            "confidence": 0.95,
                            "source": "keyword_anchor",
                        }
                        matched = True
                        break
            if not matched:
                # Check line by line for colon-separated pairs, including labels
                # whose value is printed on the following line in many PDFs.
                lines = text.split("\n")
                for line_index, line in enumerate(lines):
                    clean_line = line.strip()
                    if ":" in clean_line:
                        k, v = clean_line.split(":", 1)
                        norm_k = re.sub(r"[^\w\s]", "", k.lower()).strip()
                        if field_name == "total" and any(
                            x in norm_k for x in ["subtotal", "sub total", "sub-total"]
                        ):
                            continue
                        field_aliases = {
                            "total": ("total", "grand total", "total amount payable"),
                            "due_date": ("due date", "due", "payment due", "pay by"),
                        }.get(field_name, (field_name.replace("_", " "),))
                        label_matches = (
                            norm_k in field_aliases
                            if field_name == "due_date"
                            else any(alias in norm_k for alias in field_aliases)
                        )
                        if label_matches:
                            value = v.strip()
                            if not value and line_index + 1 < len(lines):
                                value = lines[line_index + 1].strip()
                            if not value:
                                continue
                            results[field_name] = {
                                "value": value,
                                "confidence": 0.88,
                                "source": "keyword_anchor",
                            }
                            matched = True
                            break

        return results

    def _extract_with_spacy(self, text: str) -> dict[str, list[str]]:
        """Extract Named Entities using spaCy (ORG, PERSON, DATE, MONEY, GPE)."""
        entities: dict[str, list[str]] = {
            "ORG": [],
            "PERSON": [],
            "DATE": [],
            "MONEY": [],
            "GPE": [],
        }
        if nlp is None:
            return entities

        try:
            doc = nlp(text[:10000])
            for ent in doc.ents:
                if ent.label_ in entities:
                    entities[ent.label_].append(ent.text.strip())
        except Exception as exc:
            logger.warning("spaCy NER execution warning: %s", exc)

        return entities

    # Lines that are purely a "Vendor:"/"Supplier:" style label with no value on
    # the same line (the actual name sits on the following line).
    _VENDOR_LABEL_ONLY_RE = re.compile(
        r"^(?:vendor\s*/?\s*supplier|vendor|supplier|seller|billed?\s*from|sold\s*by|from|company\s*name)\s*:?\s*$",
        re.I,
    )
    # Lines where the label and the value share the same line, e.g. "Vendor: Acme Corp".
    _VENDOR_LABEL_VALUE_RE = re.compile(
        r"^(?:vendor|supplier|seller|billed?\s*from|sold\s*by|from|company\s*name)\s*[:\-]\s*(.+)$",
        re.I,
    )
    _VENDOR_SKIP_KEYWORDS_RE = re.compile(
        r"\b(?:invoice|tax|bill|date|total|page|receipt|order|1nvoice)\b", re.I
    )

    def _extract_vendor_name(
        self, text: str, spacy_entities: dict[str, list[str]]
    ) -> dict[str, Any] | None:
        """Extract vendor / company name from document header or spaCy ORG entities."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        idx = 0
        while idx < min(len(lines), 6):
            line = lines[idx]

            # Case: "Vendor: Acme Corp" - label and value on the same line.
            value_match = self._VENDOR_LABEL_VALUE_RE.match(line)
            if value_match:
                candidate = value_match.group(1).strip()
                if 2 < len(candidate) < 60:
                    return {
                        "value": candidate,
                        "confidence": 0.90,
                        "source": "header_layout",
                    }

            # Case: "Vendor / Supplier:" on its own line - the real name is on
            # the next non-empty line, not the label itself.
            if self._VENDOR_LABEL_ONLY_RE.match(line):
                if idx + 1 < len(lines):
                    candidate = lines[idx + 1]
                    if 2 < len(candidate) < 60 and not self._VENDOR_SKIP_KEYWORDS_RE.search(
                        candidate
                    ):
                        return {
                            "value": candidate,
                            "confidence": 0.90,
                            "source": "header_layout",
                        }
                idx += 1
                continue

            if not self._VENDOR_SKIP_KEYWORDS_RE.search(line) and 2 < len(line) < 60:
                return {
                    "value": line,
                    "confidence": 0.90,
                    "source": "header_layout",
                }

            idx += 1

        if spacy_entities.get("ORG"):
            first_org = spacy_entities["ORG"][0]
            return {
                "value": first_org,
                "confidence": 0.85,
                "source": "spacy_ner",
            }

        return None

    def _extract_currency(self, text: str, total_val: str | None) -> tuple[str | None, str | None]:
        """Identify currency symbol and 3-letter ISO code."""
        if total_val:
            iso, sym = normalizer.normalize_currency(total_val)
            if iso:
                return iso, sym

        return normalizer.normalize_currency(text)

    def _extract_invoice_line_items(self, text: str) -> list[dict[str, Any]]:
        """Parse structured invoice / order line item rows."""
        items: list[dict[str, Any]] = []
        lines = text.split("\n")

        row_pattern = re.compile(
            r"^(?P<desc>[A-Za-z0-9\s\-_/&]+?)\s+(?P<qty>\d+(?:\.\d+)?)\s+[$€£¥₹]?(?P<price>[\d,.]+(?:\.\d{2}|,\d{2})?)\s+[$€£¥₹]?(?P<total>[\d,.]+(?:\.\d{2}|,\d{2})?)$"
        )

        for line in lines:
            clean = line.strip()
            match = row_pattern.match(clean)
            if match:
                desc = match.group("desc").strip()
                qty = normalizer.normalize_amount(match.group("qty")) or 1.0
                price = normalizer.normalize_amount(match.group("price")) or 0.0
                total = normalizer.normalize_amount(match.group("total")) or (qty * price)

                items.append(
                    {
                        "description": desc,
                        "quantity": qty,
                        "unit_price": price,
                        "total": total,
                    }
                )

        return items

    def _extract_selected_options(self, text: str) -> list[str]:
        """Extract checked checkboxes or selected option labels."""
        selected: list[str] = []
        checkbox_pattern = re.compile(
            r"(?:\[[xX✓]\]|\([xX✓]\)|☑)\s*([A-Za-z0-9\s\-]+?)(?=\s*(?:\[|\(|$|\n))"
        )
        for match in checkbox_pattern.finditer(text):
            opt = match.group(1).strip()
            if opt:
                selected.append(opt)
        return selected

    def extract_invoice(
        self, text: str, template_rules: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Extract standard Invoice schema fields deterministically."""
        spacy_ents = self._extract_with_spacy(text)
        anchors = self._extract_by_regex_anchors(text, self.INVOICE_ANCHORS)
        fields: dict[str, dict[str, Any]] = {}

        # 1. Vendor Name
        vendor = self._extract_vendor_name(text, spacy_ents)
        if vendor:
            fields["vendor_name"] = {
                "value": vendor["value"],
                "normalized_value": normalizer.normalize_whitespace(vendor["value"]),
                "confidence": vendor["confidence"],
                "source": vendor["source"],
                "field_type": FieldType.STRING.value,
                "is_missing": False,
            }
        else:
            fields["vendor_name"] = {
                "value": None,
                "normalized_value": None,
                "confidence": 0.0,
                "source": "missing",
                "field_type": FieldType.STRING.value,
                "is_missing": True,
            }

        # 2. Invoice Number
        inv_no = anchors.get("invoice_number")
        if inv_no:
            fields["invoice_number"] = {
                "value": inv_no["value"],
                "normalized_value": normalizer.normalize_whitespace(inv_no["value"]),
                "confidence": inv_no["confidence"],
                "source": inv_no["source"],
                "field_type": FieldType.STRING.value,
                "is_missing": False,
            }
        else:
            stand_match = re.search(r"\b(INV-[0-9]{3,10}|#\s*\d{4,10})\b", text, re.I)
            if stand_match:
                clean_inv = re.sub(r"\s+", "", stand_match.group(1))
                fields["invoice_number"] = {
                    "value": clean_inv,
                    "normalized_value": clean_inv,
                    "confidence": 0.85,
                    "source": "regex_pattern",
                    "field_type": FieldType.STRING.value,
                    "is_missing": False,
                }
            else:
                fields["invoice_number"] = {
                    "value": None,
                    "normalized_value": None,
                    "confidence": 0.0,
                    "source": "missing",
                    "field_type": FieldType.STRING.value,
                    "is_missing": True,
                }

        # 3. Invoice Date
        inv_date = anchors.get("invoice_date")
        raw_date = (
            inv_date["value"]
            if inv_date
            else (spacy_ents["DATE"][0] if spacy_ents.get("DATE") else None)
        )
        norm_date = normalizer.normalize_date(raw_date)
        fields["invoice_date"] = {
            "value": raw_date,
            "normalized_value": norm_date,
            "confidence": inv_date["confidence"] if inv_date else (0.75 if norm_date else 0.0),
            "source": inv_date["source"] if inv_date else ("spacy_ner" if raw_date else "missing"),
            "field_type": FieldType.DATE.value,
            "is_missing": raw_date is None or norm_date is None,
        }

        # 4. Due Date
        due_date = anchors.get("due_date")
        raw_due = due_date["value"] if due_date else None
        norm_due = normalizer.normalize_date(raw_due)
        fields["due_date"] = {
            "value": raw_due,
            "normalized_value": norm_due,
            "confidence": due_date["confidence"] if due_date else 0.0,
            "source": due_date["source"] if due_date else "missing",
            "field_type": FieldType.DATE.value,
            "is_missing": raw_due is None,
        }

        # 5. Total Amount & Currency
        total = anchors.get("total")
        raw_total = total["value"] if total else None
        norm_total = normalizer.normalize_amount(raw_total)
        iso_curr, sym_curr = self._extract_currency(text, raw_total)

        fields["total"] = {
            "value": raw_total,
            "normalized_value": norm_total,
            "confidence": total["confidence"] if total else 0.0,
            "source": total["source"] if total else "missing",
            "field_type": FieldType.CURRENCY.value,
            "is_missing": raw_total is None,
        }

        fields["currency"] = {
            "value": iso_curr or sym_curr,
            "normalized_value": iso_curr,
            "confidence": 0.95 if iso_curr else 0.0,
            "source": "regex" if iso_curr else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": iso_curr is None,
        }

        # 6. Subtotal, Tax, Discount
        for f_name in ["subtotal", "tax", "discount"]:
            item = anchors.get(f_name)
            raw_v = item["value"] if item else None
            norm_v = normalizer.normalize_amount(raw_v)
            fields[f_name] = {
                "value": raw_v,
                "normalized_value": norm_v,
                "confidence": item["confidence"] if item else 0.0,
                "source": item["source"] if item else "missing",
                "field_type": FieldType.CURRENCY.value,
                "is_missing": raw_v is None,
            }

        # 7. Line Items & Aggregates
        line_items = self._extract_invoice_line_items(text)
        fields["line_items"] = {
            "value": line_items if line_items else None,
            "normalized_value": line_items if line_items else None,
            "confidence": 0.90 if line_items else 0.0,
            "source": "table_heuristic" if line_items else "missing",
            "field_type": FieldType.JSON.value,
            "is_missing": len(line_items) == 0,
        }

        if line_items:
            fields["quantity"] = {
                "value": line_items[0]["quantity"],
                "normalized_value": line_items[0]["quantity"],
                "confidence": 0.90,
                "source": "line_items",
                "field_type": FieldType.FLOAT.value,
                "is_missing": False,
            }
            fields["unit_price"] = {
                "value": line_items[0]["unit_price"],
                "normalized_value": line_items[0]["unit_price"],
                "confidence": 0.90,
                "source": "line_items",
                "field_type": FieldType.CURRENCY.value,
                "is_missing": False,
            }
        else:
            fields["quantity"] = {
                "value": None,
                "normalized_value": None,
                "confidence": 0.0,
                "source": "missing",
                "field_type": FieldType.FLOAT.value,
                "is_missing": True,
            }
            fields["unit_price"] = {
                "value": None,
                "normalized_value": None,
                "confidence": 0.0,
                "source": "missing",
                "field_type": FieldType.CURRENCY.value,
                "is_missing": True,
            }

        return fields

    def extract_form(
        self, text: str, template_rules: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Extract standard Form schema fields deterministically."""
        spacy_ents = self._extract_with_spacy(text)
        anchors = self._extract_by_regex_anchors(text, self.FORM_ANCHORS)
        fields: dict[str, dict[str, Any]] = {}

        # 1. Name
        name_item = anchors.get("name")
        raw_name = (
            name_item["value"]
            if name_item
            else (spacy_ents["PERSON"][0] if spacy_ents.get("PERSON") else None)
        )
        fields["name"] = {
            "value": raw_name,
            "normalized_value": normalizer.normalize_whitespace(raw_name),
            "confidence": name_item["confidence"] if name_item else (0.80 if raw_name else 0.0),
            "source": name_item["source"]
            if name_item
            else ("spacy_ner" if raw_name else "missing"),
            "field_type": FieldType.STRING.value,
            "is_missing": raw_name is None,
        }

        # 2. Email
        email_item = anchors.get("email")
        raw_email = email_item["value"] if email_item else None
        if not raw_email:
            match = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", text)
            if match:
                raw_email = match.group(1)
        fields["email"] = {
            "value": raw_email,
            "normalized_value": raw_email.lower().strip() if raw_email else None,
            "confidence": 0.98 if raw_email else 0.0,
            "source": "regex" if raw_email else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_email is None,
        }

        # 3. Phone
        phone_item = anchors.get("phone")
        raw_phone = phone_item["value"] if phone_item else None
        if not raw_phone:
            match = re.search(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
            if match:
                raw_phone = match.group(0)
        norm_phone = normalizer.normalize_phone(raw_phone)
        fields["phone"] = {
            "value": raw_phone,
            "normalized_value": norm_phone,
            "confidence": 0.95 if raw_phone else 0.0,
            "source": "regex" if raw_phone else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_phone is None,
        }

        # 4. Address
        addr_item = anchors.get("address")
        raw_addr = addr_item["value"] if addr_item else None
        fields["address"] = {
            "value": raw_addr,
            "normalized_value": normalizer.normalize_whitespace(raw_addr),
            "confidence": addr_item["confidence"] if addr_item else 0.0,
            "source": addr_item["source"] if addr_item else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_addr is None,
        }

        # 5. Form ID
        form_id_item = anchors.get("form_id")
        raw_form_id = form_id_item["value"] if form_id_item else None
        fields["form_id"] = {
            "value": raw_form_id,
            "normalized_value": normalizer.normalize_whitespace(raw_form_id),
            "confidence": form_id_item["confidence"] if form_id_item else 0.0,
            "source": form_id_item["source"] if form_id_item else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_form_id is None,
        }

        # 6. Date
        date_item = anchors.get("date")
        raw_date = (
            date_item["value"]
            if date_item
            else (spacy_ents["DATE"][0] if spacy_ents.get("DATE") else None)
        )
        norm_date = normalizer.normalize_date(raw_date)
        fields["date"] = {
            "value": raw_date,
            "normalized_value": norm_date,
            "confidence": date_item["confidence"] if date_item else (0.75 if norm_date else 0.0),
            "source": date_item["source"]
            if date_item
            else ("spacy_ner" if raw_date else "missing"),
            "field_type": FieldType.DATE.value,
            "is_missing": raw_date is None or norm_date is None,
        }

        # 7. Selected Options (Checkboxes)
        selected_opts = self._extract_selected_options(text)
        fields["selected_options"] = {
            "value": selected_opts if selected_opts else None,
            "normalized_value": selected_opts if selected_opts else None,
            "confidence": 0.95 if selected_opts else 0.0,
            "source": "checkbox_heuristic" if selected_opts else "missing",
            "field_type": FieldType.JSON.value,
            "is_missing": len(selected_opts) == 0,
        }

        # 8. Custom Fields
        fields["custom_fields"] = {
            "value": {},
            "normalized_value": {},
            "confidence": 1.0,
            "source": "system",
            "field_type": FieldType.JSON.value,
            "is_missing": False,
        }

        return fields

    def extract_purchase_order(
        self, text: str, template_rules: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Extract Purchase Order fields (PO number, vendor, buyer, date, items, total)."""
        spacy_ents = self._extract_with_spacy(text)
        anchors = self._extract_by_regex_anchors(text, self.PO_ANCHORS)
        fields: dict[str, dict[str, Any]] = {}

        # 1. PO Number
        po_no = anchors.get("po_number")
        fields["po_number"] = {
            "value": po_no["value"] if po_no else None,
            "normalized_value": normalizer.normalize_whitespace(po_no["value"]) if po_no else None,
            "confidence": po_no["confidence"] if po_no else 0.0,
            "source": po_no["source"] if po_no else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": po_no is None,
        }

        # 2. Vendor
        vendor = anchors.get("vendor") or (
            {"value": spacy_ents["ORG"][0], "confidence": 0.85, "source": "spacy_ner"}
            if spacy_ents.get("ORG")
            else None
        )
        fields["vendor"] = {
            "value": vendor["value"] if vendor else None,
            "normalized_value": normalizer.normalize_whitespace(vendor["value"])
            if vendor
            else None,
            "confidence": vendor["confidence"] if vendor else 0.0,
            "source": vendor["source"] if vendor else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": vendor is None,
        }

        # 3. Buyer
        buyer = anchors.get("buyer") or (
            {"value": spacy_ents["PERSON"][0], "confidence": 0.85, "source": "spacy_ner"}
            if spacy_ents.get("PERSON")
            else None
        )
        fields["buyer"] = {
            "value": buyer["value"] if buyer else None,
            "normalized_value": normalizer.normalize_whitespace(buyer["value"]) if buyer else None,
            "confidence": buyer["confidence"] if buyer else 0.0,
            "source": buyer["source"] if buyer else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": buyer is None,
        }

        # 4. Date
        po_date = anchors.get("date")
        raw_date = (
            po_date["value"]
            if po_date
            else (spacy_ents["DATE"][0] if spacy_ents.get("DATE") else None)
        )
        norm_date = normalizer.normalize_date(raw_date)
        fields["date"] = {
            "value": raw_date,
            "normalized_value": norm_date,
            "confidence": po_date["confidence"] if po_date else (0.75 if norm_date else 0.0),
            "source": po_date["source"] if po_date else ("spacy_ner" if raw_date else "missing"),
            "field_type": FieldType.DATE.value,
            "is_missing": raw_date is None or norm_date is None,
        }

        # 5. Delivery Info
        deliv = anchors.get("delivery_information")
        fields["delivery_information"] = {
            "value": deliv["value"] if deliv else None,
            "normalized_value": normalizer.normalize_whitespace(deliv["value"]) if deliv else None,
            "confidence": deliv["confidence"] if deliv else 0.0,
            "source": deliv["source"] if deliv else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": deliv is None,
        }

        # 6. Total Amount
        total = anchors.get("total")
        raw_total = total["value"] if total else None
        norm_total = normalizer.normalize_amount(raw_total)
        fields["total"] = {
            "value": raw_total,
            "normalized_value": norm_total,
            "confidence": total["confidence"] if total else 0.0,
            "source": total["source"] if total else "missing",
            "field_type": FieldType.CURRENCY.value,
            "is_missing": raw_total is None,
        }

        # 7. Line items
        line_items = self._extract_invoice_line_items(text)
        fields["line_items"] = {
            "value": line_items if line_items else None,
            "normalized_value": line_items if line_items else None,
            "confidence": 0.90 if line_items else 0.0,
            "source": "table_heuristic" if line_items else "missing",
            "field_type": FieldType.JSON.value,
            "is_missing": len(line_items) == 0,
        }

        return fields

    def extract_contract(
        self, text: str, template_rules: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Extract Contract metadata (parties, dates, value, terms, jurisdiction)."""
        spacy_ents = self._extract_with_spacy(text)
        anchors = self._extract_by_regex_anchors(text, self.CONTRACT_ANCHORS)
        fields: dict[str, dict[str, Any]] = {}

        # 1. Parties
        parties_item = anchors.get("parties")
        parties_val = (
            parties_item["value"]
            if parties_item
            else (", ".join(spacy_ents["ORG"][:2]) if len(spacy_ents.get("ORG", [])) >= 2 else None)
        )
        fields["parties"] = {
            "value": parties_val,
            "normalized_value": normalizer.normalize_whitespace(parties_val),
            "confidence": parties_item["confidence"]
            if parties_item
            else (0.80 if parties_val else 0.0),
            "source": parties_item["source"]
            if parties_item
            else ("spacy_ner" if parties_val else "missing"),
            "field_type": FieldType.STRING.value,
            "is_missing": parties_val is None,
        }

        # 2. Effective Date
        eff_date = anchors.get("effective_date")
        raw_eff = (
            eff_date["value"]
            if eff_date
            else (spacy_ents["DATE"][0] if spacy_ents.get("DATE") else None)
        )
        fields["effective_date"] = {
            "value": raw_eff,
            "normalized_value": normalizer.normalize_date(raw_eff),
            "confidence": eff_date["confidence"] if eff_date else (0.75 if raw_eff else 0.0),
            "source": eff_date["source"] if eff_date else ("spacy_ner" if raw_eff else "missing"),
            "field_type": FieldType.DATE.value,
            "is_missing": raw_eff is None,
        }

        # 3. Expiry Date
        exp_date = anchors.get("expiry_date")
        raw_exp = exp_date["value"] if exp_date else None
        fields["expiry_date"] = {
            "value": raw_exp,
            "normalized_value": normalizer.normalize_date(raw_exp),
            "confidence": exp_date["confidence"] if exp_date else 0.0,
            "source": exp_date["source"] if exp_date else "missing",
            "field_type": FieldType.DATE.value,
            "is_missing": raw_exp is None,
        }

        # 4. Renewal Date
        ren_date = anchors.get("renewal_date")
        raw_ren = ren_date["value"] if ren_date else None
        fields["renewal_date"] = {
            "value": raw_ren,
            "normalized_value": normalizer.normalize_date(raw_ren),
            "confidence": ren_date["confidence"] if ren_date else 0.0,
            "source": ren_date["source"] if ren_date else "missing",
            "field_type": FieldType.DATE.value,
            "is_missing": raw_ren is None,
        }

        # 5. Contract Value
        val_item = anchors.get("contract_value")
        raw_val = val_item["value"] if val_item else None
        fields["contract_value"] = {
            "value": raw_val,
            "normalized_value": normalizer.normalize_amount(raw_val),
            "confidence": val_item["confidence"] if val_item else 0.0,
            "source": val_item["source"] if val_item else "missing",
            "field_type": FieldType.CURRENCY.value,
            "is_missing": raw_val is None,
        }

        # 6. Payment Terms
        terms_item = anchors.get("payment_terms")
        raw_terms = terms_item["value"] if terms_item else None
        fields["payment_terms"] = {
            "value": raw_terms,
            "normalized_value": normalizer.normalize_whitespace(raw_terms),
            "confidence": terms_item["confidence"] if terms_item else 0.0,
            "source": terms_item["source"] if terms_item else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_terms is None,
        }

        # 7. Governing Jurisdiction
        jur_item = anchors.get("governing_jurisdiction")
        raw_jur = jur_item["value"] if jur_item else None
        fields["governing_jurisdiction"] = {
            "value": raw_jur,
            "normalized_value": normalizer.normalize_whitespace(raw_jur),
            "confidence": jur_item["confidence"] if jur_item else 0.0,
            "source": jur_item["source"] if jur_item else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_jur is None,
        }

        return fields

    def extract_receipt(
        self, text: str, template_rules: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Extract Receipt fields (merchant, date, items, tax, total, payment method)."""
        spacy_ents = self._extract_with_spacy(text)
        anchors = self._extract_by_regex_anchors(text, self.RECEIPT_ANCHORS)
        fields: dict[str, dict[str, Any]] = {}

        # 1. Merchant
        merch = anchors.get("merchant") or self._extract_vendor_name(text, spacy_ents)
        fields["merchant"] = {
            "value": merch["value"] if merch else None,
            "normalized_value": normalizer.normalize_whitespace(merch["value"]) if merch else None,
            "confidence": merch["confidence"] if merch else 0.0,
            "source": merch["source"] if merch else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": merch is None,
        }

        # 2. Date
        r_date = anchors.get("date")
        raw_date = (
            r_date["value"]
            if r_date
            else (spacy_ents["DATE"][0] if spacy_ents.get("DATE") else None)
        )
        norm_date = normalizer.normalize_date(raw_date)
        fields["date"] = {
            "value": raw_date,
            "normalized_value": norm_date,
            "confidence": r_date["confidence"] if r_date else (0.75 if norm_date else 0.0),
            "source": r_date["source"] if r_date else ("spacy_ner" if raw_date else "missing"),
            "field_type": FieldType.DATE.value,
            "is_missing": raw_date is None or norm_date is None,
        }

        # 3. Tax
        tax_item = anchors.get("tax")
        raw_tax = tax_item["value"] if tax_item else None
        fields["tax"] = {
            "value": raw_tax,
            "normalized_value": normalizer.normalize_amount(raw_tax),
            "confidence": tax_item["confidence"] if tax_item else 0.0,
            "source": tax_item["source"] if tax_item else "missing",
            "field_type": FieldType.CURRENCY.value,
            "is_missing": raw_tax is None,
        }

        # 4. Total
        tot_item = anchors.get("total")
        raw_tot = tot_item["value"] if tot_item else None
        fields["total"] = {
            "value": raw_tot,
            "normalized_value": normalizer.normalize_amount(raw_tot),
            "confidence": tot_item["confidence"] if tot_item else 0.0,
            "source": tot_item["source"] if tot_item else "missing",
            "field_type": FieldType.CURRENCY.value,
            "is_missing": raw_tot is None,
        }

        # 5. Payment Method
        pm_item = anchors.get("payment_method")
        raw_pm = pm_item["value"] if pm_item else None
        fields["payment_method"] = {
            "value": raw_pm,
            "normalized_value": normalizer.normalize_whitespace(raw_pm),
            "confidence": pm_item["confidence"] if pm_item else 0.0,
            "source": pm_item["source"] if pm_item else "missing",
            "field_type": FieldType.STRING.value,
            "is_missing": raw_pm is None,
        }

        # 6. Items
        line_items = self._extract_invoice_line_items(text)
        fields["line_items"] = {
            "value": line_items if line_items else None,
            "normalized_value": line_items if line_items else None,
            "confidence": 0.90 if line_items else 0.0,
            "source": "table_heuristic" if line_items else "missing",
            "field_type": FieldType.JSON.value,
            "is_missing": len(line_items) == 0,
        }

        return fields

    def extract_document(
        self,
        text: str,
        document_type: str = "invoice",
        template_rules: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Extract structured data based on detected or target document type."""
        doc_type_clean = (document_type or "invoice").lower().strip()
        if doc_type_clean == "purchase_order":
            return self.extract_purchase_order(text, template_rules=template_rules)
        elif doc_type_clean == "contract":
            return self.extract_contract(text, template_rules=template_rules)
        elif doc_type_clean == "receipt":
            return self.extract_receipt(text, template_rules=template_rules)
        elif doc_type_clean == "form":
            return self.extract_form(text, template_rules=template_rules)
        elif doc_type_clean == "invoice":
            return self.extract_invoice(text, template_rules=template_rules)
        else:
            inv_fields = self.extract_invoice(text, template_rules=template_rules)
            form_fields = self.extract_form(text, template_rules=template_rules)
            return {**inv_fields, **form_fields}


hybrid_extractor = HybridExtractor()
