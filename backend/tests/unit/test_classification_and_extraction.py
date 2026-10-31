from backend.app.services.classifier import document_classifier
from backend.app.services.extractor import hybrid_extractor
from backend.app.services.normalizer import normalizer
from backend.tests.fixtures.sample_documents import (
    CONTRACT_SAMPLE_TEXT,
    INVOICE_BRITISH_POUND_TEXT,
    INVOICE_EURO_FORMAT_TEXT,
    INVOICE_MISSING_FIELDS_TEXT,
    MINIMAL_FORM_TEXT,
    NOISY_OCR_INVOICE_TEXT,
    PURCHASE_ORDER_TEXT,
    RECEIPT_SAMPLE_TEXT,
    STANDARD_FORM_TEXT,
    STANDARD_INVOICE_TEXT,
)


def test_document_classification():
    """Verify document classification across invoices, forms, and purchase orders."""
    # 1. Standard Invoice
    res_inv = document_classifier.classify(STANDARD_INVOICE_TEXT)
    assert res_inv["document_type"] == "invoice"
    assert res_inv["confidence"] >= 0.85

    # 2. Purchase Order
    res_po = document_classifier.classify(PURCHASE_ORDER_TEXT)
    assert res_po["document_type"] == "purchase_order"
    assert res_po["confidence"] >= 0.85

    # 3. Form
    res_form = document_classifier.classify(STANDARD_FORM_TEXT)
    assert res_form["document_type"] == "form"
    assert res_form["confidence"] >= 0.80

    # 4. Contract
    res_contract = document_classifier.classify(CONTRACT_SAMPLE_TEXT)
    assert res_contract["document_type"] == "contract"
    assert res_contract["confidence"] >= 0.80

    # 5. Receipt
    res_receipt = document_classifier.classify(RECEIPT_SAMPLE_TEXT)
    assert res_receipt["document_type"] == "receipt"
    assert res_receipt["confidence"] >= 0.80

    # 6. Unknown / Empty
    res_empty = document_classifier.classify("")
    assert res_empty["document_type"] == "unknown"
    assert res_empty["confidence"] == 0.0


def test_normalizer_dates():
    """Verify date normalizer handles various formats into ISO 8601 YYYY-MM-DD."""
    assert normalizer.normalize_date("2026-03-15") == "2026-03-15"
    assert normalizer.normalize_date("15/03/2026") == "2026-03-15"
    assert normalizer.normalize_date("03/15/2026") == "2026-03-15"
    assert normalizer.normalize_date("March 15, 2026") == "2026-03-15"
    assert normalizer.normalize_date("15-Mar-2026") == "2026-03-15"
    assert normalizer.normalize_date("15.03.2026") == "2026-03-15"
    assert normalizer.normalize_date("InvalidDate") is None
    assert normalizer.normalize_date(None) is None


def test_normalizer_currency():
    """Verify currency normalizer maps symbols and strings to standard 3-letter ISO codes."""
    assert normalizer.normalize_currency("$1,250.00")[0] == "USD"
    assert normalizer.normalize_currency("1.200,00 €")[0] == "EUR"
    assert normalizer.normalize_currency("£850.00")[0] == "GBP"
    assert normalizer.normalize_currency("Total in CAD: 500")[0] == "CAD"
    assert normalizer.normalize_currency("Price: AUD 300")[0] == "AUD"
    assert normalizer.normalize_currency("₹ 15,000")[0] == "INR"
    assert normalizer.normalize_currency("¥50,000")[0] == "JPY"
    assert normalizer.normalize_currency("UnknownString")[0] is None


def test_normalizer_amount():
    """Verify amount normalizer handles US and European decimal notations."""
    assert normalizer.normalize_amount("$1,250.00") == 1250.00
    assert normalizer.normalize_amount("1.250,50 €") == 1250.50
    assert normalizer.normalize_amount("£850.00") == 850.00
    assert normalizer.normalize_amount("1428,00") == 1428.00
    assert normalizer.normalize_amount("450") == 450.00
    assert normalizer.normalize_amount("0.00") == 0.00
    assert normalizer.normalize_amount("invalid") is None
    assert normalizer.normalize_amount(None) is None


def test_normalizer_phone():
    """Verify phone normalizer standardizes human phone numbers."""
    assert normalizer.normalize_phone("(555) 342-8890") == "+15553428890"
    assert normalizer.normalize_phone("+1-555-882-1920") == "+15558821920"
    assert normalizer.normalize_phone("555.342.8890") == "+15553428890"
    assert normalizer.normalize_phone(None) is None


def test_standard_invoice_extraction():
    """Verify full field extraction accuracy on standard invoice."""
    fields = hybrid_extractor.extract_invoice(STANDARD_INVOICE_TEXT)

    assert fields["vendor_name"]["value"] == "ACME CORPORATION"
    assert fields["invoice_number"]["value"] == "INV-2026-8891"
    assert fields["invoice_date"]["normalized_value"] == "2026-03-15"
    assert fields["due_date"]["normalized_value"] == "2026-04-15"
    assert fields["currency"]["normalized_value"] == "USD"
    assert fields["subtotal"]["normalized_value"] == 1250.00
    assert fields["tax"]["normalized_value"] == 125.00
    assert fields["discount"]["normalized_value"] == 50.00
    assert fields["total"]["normalized_value"] == 1325.00

    # Line items check
    line_items = fields["line_items"]["value"]
    assert line_items is not None
    assert len(line_items) == 2
    assert line_items[0]["quantity"] == 2.0
    assert line_items[0]["unit_price"] == 250.00
    assert line_items[0]["total"] == 500.00

    # Check sources and confidences
    assert fields["invoice_number"]["source"] == "keyword_anchor"
    assert fields["invoice_number"]["confidence"] >= 0.90
    assert fields["total"]["confidence"] >= 0.90
    assert fields["total"]["is_missing"] is False


def test_invoice_with_missing_fields_explicit_handling():
    """Verify missing fields are explicitly flagged without hallucinating values."""
    fields = hybrid_extractor.extract_invoice(INVOICE_MISSING_FIELDS_TEXT)

    assert fields["vendor_name"]["value"] == "VERTEX DIGITAL SERVICES"
    assert fields["invoice_number"]["value"] == "90422"
    assert fields["invoice_date"]["normalized_value"] == "2025-12-05"
    assert fields["total"]["normalized_value"] == 450.00

    # Explicitly missing fields
    assert fields["due_date"]["is_missing"] is True
    assert fields["due_date"]["value"] is None
    assert fields["due_date"]["confidence"] == 0.0

    assert fields["tax"]["is_missing"] is True
    assert fields["tax"]["value"] is None

    assert fields["discount"]["is_missing"] is True
    assert fields["discount"]["value"] is None

    assert fields["line_items"]["is_missing"] is True
    assert fields["line_items"]["value"] is None


def test_euro_invoice_extraction():
    """Verify European layout with comma decimals and DD/MM/YYYY dates."""
    fields = hybrid_extractor.extract_invoice(INVOICE_EURO_FORMAT_TEXT)

    assert fields["vendor_name"]["value"] == "BERLIN LOGISTICS GMBH"
    assert fields["invoice_number"]["value"] == "EU-99381"
    assert fields["invoice_date"]["normalized_value"] == "2025-08-24"
    assert fields["due_date"]["normalized_value"] == "2025-09-15"
    assert fields["currency"]["normalized_value"] == "EUR"
    assert fields["subtotal"]["normalized_value"] == 1200.00
    assert fields["tax"]["normalized_value"] == 228.00
    assert fields["total"]["normalized_value"] == 1428.00


def test_british_pound_invoice_extraction():
    """Verify UK layout with £ symbol and Month name dates."""
    fields = hybrid_extractor.extract_invoice(INVOICE_BRITISH_POUND_TEXT)

    assert "OXFORD SCIENTIFIC" in (fields["vendor_name"]["value"] or "")
    assert fields["invoice_number"]["value"] == "UK-77102"
    assert fields["invoice_date"]["normalized_value"] == "2025-10-10"
    assert fields["due_date"]["normalized_value"] == "2025-11-10"
    assert fields["currency"]["normalized_value"] == "GBP"
    assert fields["subtotal"]["normalized_value"] == 850.00
    assert fields["tax"]["normalized_value"] == 170.00
    assert fields["discount"]["normalized_value"] == 20.00
    assert fields["total"]["normalized_value"] == 1000.00


def test_noisy_ocr_invoice_extraction():
    """Verify extraction resilience against noisy OCR text."""
    fields = hybrid_extractor.extract_invoice(NOISY_OCR_INVOICE_TEXT)

    assert fields["invoice_number"]["value"] == "INV-99014"
    assert fields["invoice_date"]["normalized_value"] == "2026-01-20"
    assert fields["due_date"]["normalized_value"] == "2026-02-20"
    assert fields["subtotal"]["normalized_value"] == 2000.00
    assert fields["tax"]["normalized_value"] == 200.00
    assert fields["total"]["normalized_value"] == 2200.00


def test_form_extraction():
    """Verify field extraction for medical and registration forms."""
    fields = hybrid_extractor.extract_form(STANDARD_FORM_TEXT)

    assert "Emily R. Thorne" in (fields["name"]["value"] or "")
    assert fields["email"]["normalized_value"] == "emily.thorne@hospital.org"
    assert fields["phone"]["normalized_value"] == "+15553428890"
    assert fields["form_id"]["value"] == "FORM-MED-2026-004"
    assert fields["date"]["normalized_value"] == "2026-05-12"
    assert "742 Evergreen Terrace" in (fields["address"]["value"] or "")

    # Selected options
    opts = fields["selected_options"]["value"]
    assert opts is not None
    assert len(opts) == 2
    assert any("medical data" in o for o in opts)
    assert any("telehealth" in o for o in opts)


def test_minimal_form_extraction():
    """Verify minimal form extraction."""
    fields = hybrid_extractor.extract_form(MINIMAL_FORM_TEXT)

    assert "Michael Vance" in (fields["name"]["value"] or "")
    assert fields["email"]["normalized_value"] == "mvance@techsummit.io"
    assert fields["phone"]["normalized_value"] == "+15558821920"
    assert fields["form_id"]["value"] == "EVT-992"
    assert fields["date"]["normalized_value"] == "2026-06-15"


def test_purchase_order_extraction():
    """Verify purchase order extraction per PRD Section 7."""
    fields = hybrid_extractor.extract_purchase_order(PURCHASE_ORDER_TEXT)

    assert fields["po_number"]["value"] == "PO-2026-4401"
    assert fields["date"]["normalized_value"] == "2026-02-10"
    assert fields["total"]["normalized_value"] == 2970.00
    assert "Precision Steel" in (fields["vendor"]["value"] or "")


def test_contract_extraction():
    """Verify contract metadata extraction per PRD Section 8."""
    fields = hybrid_extractor.extract_contract(CONTRACT_SAMPLE_TEXT)

    assert fields["effective_date"]["normalized_value"] == "2026-01-01"
    assert fields["expiry_date"]["normalized_value"] == "2027-01-01"
    assert fields["contract_value"]["normalized_value"] == 150000.00
    assert "New York" in (fields["governing_jurisdiction"]["value"] or "")


def test_receipt_extraction():
    """Verify receipt extraction per PRD Section 8."""
    fields = hybrid_extractor.extract_receipt(RECEIPT_SAMPLE_TEXT)

    assert "METRO CAFE" in (fields["merchant"]["value"] or "")
    assert fields["date"]["normalized_value"] == "2026-04-10"
    assert fields["tax"]["normalized_value"] == 0.95
    assert fields["total"]["normalized_value"] == 10.95
    assert "Visa" in (fields["payment_method"]["value"] or "")


def test_public_invoice_layout_extracts_separate_line_total_and_due():
    """Common invoice PDFs put the label and amount on adjacent lines."""
    fields = hybrid_extractor.extract_invoice(
        "TAX INVOICE\nInvoice #: INV-2026-1042\nDue Date:\n24 May 2026\n"
        "Subtotal:\n50,000.00\nTax / GST (18%):\n9,000.00\n"
        "Total Amount Payable:\n59,000.00"
    )

    assert fields["invoice_number"]["value"] == "INV-2026-1042"
    assert fields["due_date"]["normalized_value"] == "2026-05-24"
    assert fields["subtotal"]["normalized_value"] == 50000.00
    assert fields["tax"]["normalized_value"] == 9000.00
    assert fields["total"]["normalized_value"] == 59000.00
