from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(val: Any) -> Decimal | None:
    """Safely convert numeric/string value to Decimal without float imprecision."""
    if val is None:
        return None
    try:
        clean_str = (
            str(val).replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
        )
        if not clean_str:
            return None
        return Decimal(clean_str).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


class ValidationEngine:
    """Production validation engine enforcing business logic, math integrity, and date chronology."""

    REQUIRED_INVOICE_FIELDS = ["vendor_name", "invoice_number", "total"]
    REQUIRED_FORM_FIELDS = ["name"]
    REQUIRED_PO_FIELDS = ["po_number", "vendor", "total"]
    REQUIRED_CONTRACT_FIELDS = ["parties", "effective_date"]
    REQUIRED_RECEIPT_FIELDS = ["merchant", "total"]

    def validate_invoice(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate Invoice data integrity with Decimal arithmetic and chronological checks."""
        errors: list[str] = []
        warnings: list[str] = []
        rule_results: list[dict[str, Any]] = []

        # 1. Required Fields Check
        for req in self.REQUIRED_INVOICE_FIELDS:
            f_val = fields.get(req, {}).get("value")
            is_miss = fields.get(req, {}).get("is_missing", f_val is None)
            if is_miss or not f_val:
                msg = f"Missing required invoice field: '{req}'"
                errors.append(msg)
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": False,
                        "severity": "ERROR",
                        "message": msg,
                    }
                )
            else:
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": True,
                        "severity": "INFO",
                        "message": f"Required field '{req}' is present.",
                    }
                )

        # 2. Financial Math Integrity: subtotal + tax - discount == total (Decimal)
        total_dec = to_decimal(
            fields.get("total", {}).get("normalized_value") or fields.get("total", {}).get("value")
        )
        subtotal_dec = to_decimal(
            fields.get("subtotal", {}).get("normalized_value")
            or fields.get("subtotal", {}).get("value")
        )
        tax_dec = to_decimal(
            fields.get("tax", {}).get("normalized_value") or fields.get("tax", {}).get("value")
        )
        discount_dec = to_decimal(
            fields.get("discount", {}).get("normalized_value")
            or fields.get("discount", {}).get("value")
        ) or Decimal("0.00")

        if total_dec is not None and subtotal_dec is not None:
            effective_tax = tax_dec or Decimal("0.00")
            expected_total = (subtotal_dec + effective_tax - discount_dec).quantize(Decimal("0.01"))
            actual_total = total_dec.quantize(Decimal("0.01"))

            diff = abs(expected_total - actual_total)
            if diff <= Decimal("0.02"):
                rule_results.append(
                    {
                        "rule_name": "financial_math_integrity",
                        "passed": True,
                        "severity": "INFO",
                        "message": f"Financial math matches: subtotal ({subtotal_dec}) + tax ({effective_tax}) - discount ({discount_dec}) = total ({actual_total}).",
                    }
                )
            else:
                msg = f"Financial calculation mismatch: Subtotal ({subtotal_dec}) + Tax ({effective_tax}) - Discount ({discount_dec}) = {expected_total}, but Total is {actual_total} (difference: {diff})."
                errors.append(msg)
                rule_results.append(
                    {
                        "rule_name": "financial_math_integrity",
                        "passed": False,
                        "severity": "ERROR",
                        "message": msg,
                    }
                )
        elif total_dec is None:
            rule_results.append(
                {
                    "rule_name": "financial_math_integrity",
                    "passed": False,
                    "severity": "ERROR",
                    "message": "Total amount is missing; cannot perform math integrity validation.",
                }
            )

        # 3. Date Sequence Check: invoice_date <= due_date
        inv_date_str = fields.get("invoice_date", {}).get("normalized_value")
        due_date_str = fields.get("due_date", {}).get("normalized_value")

        if inv_date_str and due_date_str:
            try:
                inv_dt = datetime.strptime(inv_date_str, "%Y-%m-%d")
                due_dt = datetime.strptime(due_date_str, "%Y-%m-%d")
                if inv_dt <= due_dt:
                    rule_results.append(
                        {
                            "rule_name": "date_sequence",
                            "passed": True,
                            "severity": "INFO",
                            "message": f"Date chronology valid: invoice date ({inv_date_str}) is on or before due date ({due_date_str}).",
                        }
                    )
                else:
                    msg = f"Invalid date sequence: invoice date ({inv_date_str}) is after due date ({due_date_str})."
                    errors.append(msg)
                    rule_results.append(
                        {
                            "rule_name": "date_sequence",
                            "passed": False,
                            "severity": "ERROR",
                            "message": msg,
                        }
                    )
            except Exception as e:
                warnings.append(f"Could not parse dates for sequence comparison: {e}")
        elif inv_date_str and not due_date_str:
            warnings.append("Due date is not specified.")
            rule_results.append(
                {
                    "rule_name": "date_sequence",
                    "passed": True,
                    "severity": "WARNING",
                    "message": "Due date is missing; skipping date sequence validation.",
                }
            )

        status = (
            "passed"
            if len(errors) == 0 and len(warnings) == 0
            else ("failed" if len(errors) > 0 else "warnings")
        )
        return {
            "status": status,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "rule_results": rule_results,
        }

    def validate_form(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate Form data integrity."""
        errors: list[str] = []
        warnings: list[str] = []
        rule_results: list[dict[str, Any]] = []

        # 1. Required Fields Check
        for req in self.REQUIRED_FORM_FIELDS:
            f_val = fields.get(req, {}).get("value")
            is_miss = fields.get(req, {}).get("is_missing", f_val is None)
            if is_miss or not f_val:
                msg = f"Missing required form field: '{req}'"
                errors.append(msg)
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": False,
                        "severity": "ERROR",
                        "message": msg,
                    }
                )
            else:
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": True,
                        "severity": "INFO",
                        "message": f"Required field '{req}' is present.",
                    }
                )

        # 2. Email format warning if present
        email_val = fields.get("email", {}).get("normalized_value")
        if email_val and "@" not in email_val:
            warnings.append(f"Email '{email_val}' does not contain an '@' sign.")

        status = (
            "passed"
            if len(errors) == 0 and len(warnings) == 0
            else ("failed" if len(errors) > 0 else "warnings")
        )
        return {
            "status": status,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "rule_results": rule_results,
        }

    def validate_purchase_order(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate Purchase Order data integrity."""
        errors: list[str] = []
        warnings: list[str] = []
        rule_results: list[dict[str, Any]] = []

        for req in self.REQUIRED_PO_FIELDS:
            f_val = fields.get(req, {}).get("value")
            is_miss = fields.get(req, {}).get("is_missing", f_val is None)
            if is_miss or not f_val:
                msg = f"Missing required purchase order field: '{req}'"
                errors.append(msg)
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": False,
                        "severity": "ERROR",
                        "message": msg,
                    }
                )
            else:
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": True,
                        "severity": "INFO",
                        "message": f"Field '{req}' present.",
                    }
                )

        status = "passed" if len(errors) == 0 else "failed"
        return {
            "status": status,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "rule_results": rule_results,
        }

    def validate_contract(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate Contract data integrity and dates."""
        errors: list[str] = []
        warnings: list[str] = []
        rule_results: list[dict[str, Any]] = []

        for req in self.REQUIRED_CONTRACT_FIELDS:
            f_val = fields.get(req, {}).get("value")
            is_miss = fields.get(req, {}).get("is_missing", f_val is None)
            if is_miss or not f_val:
                msg = f"Missing required contract field: '{req}'"
                errors.append(msg)
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": False,
                        "severity": "ERROR",
                        "message": msg,
                    }
                )
            else:
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": True,
                        "severity": "INFO",
                        "message": f"Field '{req}' present.",
                    }
                )

        eff_str = fields.get("effective_date", {}).get("normalized_value")
        exp_str = fields.get("expiry_date", {}).get("normalized_value")
        if eff_str and exp_str:
            try:
                eff_dt = datetime.strptime(eff_str, "%Y-%m-%d")
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
                if eff_dt <= exp_dt:
                    rule_results.append(
                        {
                            "rule_name": "contract_term_chronology",
                            "passed": True,
                            "severity": "INFO",
                            "message": "Effective date is on or before expiry date.",
                        }
                    )
                else:
                    msg = f"Effective date ({eff_str}) is after expiry date ({exp_str})."
                    errors.append(msg)
                    rule_results.append(
                        {
                            "rule_name": "contract_term_chronology",
                            "passed": False,
                            "severity": "ERROR",
                            "message": msg,
                        }
                    )
            except Exception as e:
                warnings.append(f"Could not parse contract dates: {e}")

        status = "passed" if len(errors) == 0 else "failed"
        return {
            "status": status,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "rule_results": rule_results,
        }

    def validate_receipt(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate Receipt data integrity."""
        errors: list[str] = []
        warnings: list[str] = []
        rule_results: list[dict[str, Any]] = []

        for req in self.REQUIRED_RECEIPT_FIELDS:
            f_val = fields.get(req, {}).get("value")
            is_miss = fields.get(req, {}).get("is_missing", f_val is None)
            if is_miss or not f_val:
                msg = f"Missing required receipt field: '{req}'"
                errors.append(msg)
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": False,
                        "severity": "ERROR",
                        "message": msg,
                    }
                )
            else:
                rule_results.append(
                    {
                        "rule_name": f"required_field_{req}",
                        "passed": True,
                        "severity": "INFO",
                        "message": f"Field '{req}' present.",
                    }
                )

        status = "passed" if len(errors) == 0 else "failed"
        return {
            "status": status,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "rule_results": rule_results,
        }

    def validate_document(self, document_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Route to appropriate validator based on document type."""
        doc_type_clean = (document_type or "invoice").lower().strip()
        if doc_type_clean == "purchase_order":
            return self.validate_purchase_order(fields)
        elif doc_type_clean == "contract":
            return self.validate_contract(fields)
        elif doc_type_clean == "receipt":
            return self.validate_receipt(fields)
        elif doc_type_clean == "form":
            return self.validate_form(fields)
        elif doc_type_clean == "invoice":
            return self.validate_invoice(fields)
        else:
            return self.validate_invoice(fields)


validation_engine = ValidationEngine()
