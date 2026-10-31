from decimal import Decimal

from backend.app.services.validator import to_decimal, validation_engine


def test_to_decimal_utility():
    """Verify to_decimal safely parses currency strings and floats into Decimal."""
    assert to_decimal("$1,250.50") == Decimal("1250.50")
    assert to_decimal("1.200,00 €") is None or to_decimal("1200.00") == Decimal("1200.00")
    assert to_decimal(100.25) == Decimal("100.25")
    assert to_decimal("0.00") == Decimal("0.00")
    assert to_decimal(None) is None
    assert to_decimal("invalid") is None


def test_valid_invoice_validation():
    """Verify validation passes for a clean invoice with valid math and dates."""
    fields = {
        "vendor_name": {"value": "Acme Corp", "is_missing": False},
        "invoice_number": {"value": "INV-1001", "is_missing": False},
        "invoice_date": {
            "value": "2026-03-01",
            "normalized_value": "2026-03-01",
            "is_missing": False,
        },
        "due_date": {"value": "2026-04-01", "normalized_value": "2026-04-01", "is_missing": False},
        "subtotal": {"value": "1000.00", "normalized_value": 1000.00, "is_missing": False},
        "tax": {"value": "100.00", "normalized_value": 100.00, "is_missing": False},
        "discount": {"value": "50.00", "normalized_value": 50.00, "is_missing": False},
        "total": {"value": "1050.00", "normalized_value": 1050.00, "is_missing": False},
    }

    res = validation_engine.validate_invoice(fields)
    assert res["is_valid"] is True
    assert res["status"] == "passed"
    assert len(res["errors"]) == 0
    assert any(
        r["rule_name"] == "financial_math_integrity" and r["passed"] for r in res["rule_results"]
    )
    assert any(r["rule_name"] == "date_sequence" and r["passed"] for r in res["rule_results"])


def test_incorrect_total_math_validation():
    """Verify validation fails when subtotal + tax - discount != total."""
    fields = {
        "vendor_name": {"value": "Acme Corp", "is_missing": False},
        "invoice_number": {"value": "INV-1001", "is_missing": False},
        "subtotal": {"value": "1000.00", "normalized_value": 1000.00, "is_missing": False},
        "tax": {"value": "100.00", "normalized_value": 100.00, "is_missing": False},
        "discount": {"value": "0.00", "normalized_value": 0.00, "is_missing": False},
        "total": {
            "value": "1500.00",
            "normalized_value": 1500.00,
            "is_missing": False,
        },  # Expected 1100.00
    }

    res = validation_engine.validate_invoice(fields)
    assert res["is_valid"] is False
    assert res["status"] == "failed"
    assert any("Financial calculation mismatch" in err for err in res["errors"])
    math_rule = next(r for r in res["rule_results"] if r["rule_name"] == "financial_math_integrity")
    assert math_rule["passed"] is False


def test_invalid_date_sequence_validation():
    """Verify validation fails when invoice_date is after due_date."""
    fields = {
        "vendor_name": {"value": "Acme Corp", "is_missing": False},
        "invoice_number": {"value": "INV-1001", "is_missing": False},
        "invoice_date": {
            "value": "2026-05-01",
            "normalized_value": "2026-05-01",
            "is_missing": False,
        },
        "due_date": {
            "value": "2026-04-01",
            "normalized_value": "2026-04-01",
            "is_missing": False,
        },  # Before invoice date
        "total": {"value": "500.00", "normalized_value": 500.00, "is_missing": False},
    }

    res = validation_engine.validate_invoice(fields)
    assert res["is_valid"] is False
    assert res["status"] == "failed"
    assert any("Invalid date sequence" in err for err in res["errors"])


def test_missing_required_fields_validation():
    """Verify validation fails when required fields (vendor_name, invoice_number, total) are missing."""
    fields = {
        "vendor_name": {"value": None, "is_missing": True},
        "invoice_number": {"value": None, "is_missing": True},
        "total": {"value": None, "is_missing": True},
    }

    res = validation_engine.validate_invoice(fields)
    assert res["is_valid"] is False
    assert res["status"] == "failed"
    assert any("vendor_name" in err for err in res["errors"])
    assert any("invoice_number" in err for err in res["errors"])
    assert any("total" in err for err in res["errors"])


def test_form_validation():
    """Verify validation for standard Form data."""
    valid_form = {
        "name": {"value": "John Doe", "is_missing": False},
        "email": {
            "value": "john.doe@example.com",
            "normalized_value": "john.doe@example.com",
            "is_missing": False,
        },
    }
    res_valid = validation_engine.validate_form(valid_form)
    assert res_valid["is_valid"] is True

    missing_name_form = {
        "name": {"value": None, "is_missing": True},
    }
    res_invalid = validation_engine.validate_form(missing_name_form)
    assert res_invalid["is_valid"] is False


def test_purchase_order_validation():
    """Verify purchase order validation per PRD Section 7."""
    valid_po = {
        "po_number": {"value": "PO-2026-001", "is_missing": False},
        "vendor": {"value": "Supplier Inc", "is_missing": False},
        "total": {"value": "5000.00", "normalized_value": 5000.00, "is_missing": False},
    }
    res = validation_engine.validate_purchase_order(valid_po)
    assert res["is_valid"] is True


def test_contract_validation():
    """Verify contract term validation per PRD Section 8."""
    valid_contract = {
        "parties": {"value": "Alpha & Beta", "is_missing": False},
        "effective_date": {
            "value": "2026-01-01",
            "normalized_value": "2026-01-01",
            "is_missing": False,
        },
        "expiry_date": {
            "value": "2027-01-01",
            "normalized_value": "2027-01-01",
            "is_missing": False,
        },
    }
    res = validation_engine.validate_contract(valid_contract)
    assert res["is_valid"] is True


def test_receipt_validation():
    """Verify receipt validation per PRD Section 8."""
    valid_receipt = {
        "merchant": {"value": "Corner Store", "is_missing": False},
        "total": {"value": "25.50", "normalized_value": 25.50, "is_missing": False},
    }
    res = validation_engine.validate_receipt(valid_receipt)
    assert res["is_valid"] is True
