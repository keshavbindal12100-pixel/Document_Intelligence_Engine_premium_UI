import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from backend.app.models.document import Document, DocumentStatus
from backend.app.services.validator import to_decimal

logger = logging.getLogger(__name__)
UTC = UTC


# ---------------------------------------------------------------------------
# Condition Evaluator
# ---------------------------------------------------------------------------


class ConditionEvaluator:
    """Evaluates flexible workflow conditions against document extraction data and metadata."""

    ALIAS_MAP: dict[str, str] = {
        "vendorname": "vendor_name",
        "vendor": "vendor_name",
        "supplier": "vendor_name",
        "invoicenumber": "invoice_number",
        "invoiceno": "invoice_number",
        "ponumber": "po_number",
        "invoicedate": "invoice_date",
        "duedate": "due_date",
        "total": "total",
        "totalamount": "total",
        "amount": "total",
        "subtotal": "subtotal",
        "netamount": "subtotal",
        "tax": "tax",
        "taxamount": "tax",
        "gst": "tax",
        "vat": "tax",
        "documentid": "id",
        "docid": "id",
        "confidence": "confidence_score",
        "confidencescore": "confidence_score",
        "status": "status",
        "documenttype": "document_type",
        "doctype": "document_type",
        "filename": "filename",
        "filesize": "file_size",
    }

    @classmethod
    def _extract_field_value(cls, context: dict[str, Any], field_path: str) -> Any:
        """Resolve dotted or aliased field paths from execution context."""
        clean_key = field_path.strip()
        norm_key = cls.ALIAS_MAP.get(clean_key.lower().replace("_", ""), clean_key)

        if norm_key in context:
            val = context[norm_key]
            if isinstance(val, dict) and "value" in val:
                return val.get("normalized_value", val.get("value"))
            return val

        # Case-insensitive direct check
        for k, v in context.items():
            if k.lower() == clean_key.lower() or k.lower().replace(
                "_", ""
            ) == clean_key.lower().replace("_", ""):
                if isinstance(v, dict) and "value" in v:
                    return v.get("normalized_value", v.get("value"))
                return v

        # Dotted nested path
        parts = clean_key.split(".")
        curr: Any = context
        for part in parts:
            if isinstance(curr, dict):
                matched = False
                for ck, cv in curr.items():
                    if ck.lower() == part.lower():
                        curr = cv
                        matched = True
                        break
                if not matched:
                    return None
            else:
                return None
        return curr

    @classmethod
    def evaluate_rule(cls, context: dict[str, Any], rule: dict[str, Any]) -> bool:
        """Evaluate a single condition rule dict."""
        field_name = rule.get("field")
        if not field_name:
            return True

        operator = str(rule.get("operator", "==")).lower().strip()
        target_val = rule.get("value")
        actual_val = cls._extract_field_value(context, field_name)

        # Numeric comparisons
        actual_dec = to_decimal(actual_val)
        target_dec = to_decimal(target_val)

        if actual_dec is not None and target_dec is not None:
            ops = {
                ">": actual_dec > target_dec,
                "gt": actual_dec > target_dec,
                ">=": actual_dec >= target_dec,
                "gte": actual_dec >= target_dec,
                "<": actual_dec < target_dec,
                "lt": actual_dec < target_dec,
                "<=": actual_dec <= target_dec,
                "lte": actual_dec <= target_dec,
                "==": actual_dec == target_dec,
                "eq": actual_dec == target_dec,
                "equals": actual_dec == target_dec,
                "!=": actual_dec != target_dec,
                "ne": actual_dec != target_dec,
                "not_equals": actual_dec != target_dec,
            }
            if operator in ops:
                return ops[operator]

        # String / generic comparisons
        actual_str = str(actual_val).lower().strip() if actual_val is not None else ""
        target_str = str(target_val).lower().strip() if target_val is not None else ""

        str_ops: dict[str, bool] = {
            "==": actual_str == target_str,
            "eq": actual_str == target_str,
            "equals": actual_str == target_str,
            "!=": actual_str != target_str,
            "ne": actual_str != target_str,
            "not_equals": actual_str != target_str,
            "contains": target_str in actual_str,
            "in_text": target_str in actual_str,
            "not_contains": target_str not in actual_str,
            "starts_with": actual_str.startswith(target_str),
            "ends_with": actual_str.endswith(target_str),
            "is_null": actual_val is None or actual_str == "",
            "is_missing": actual_val is None or actual_str == "",
            "empty": actual_val is None or actual_str == "",
            "is_not_null": actual_val is not None and actual_str != "",
            "present": actual_val is not None and actual_str != "",
            "not_empty": actual_val is not None and actual_str != "",
        }
        if operator in str_ops:
            return str_ops[operator]

        if operator in ["in"]:
            if isinstance(target_val, list):
                return actual_val in target_val or actual_str in [
                    str(x).lower().strip() for x in target_val
                ]
            return actual_str in target_str

        if operator in ["not in", "not_in"]:
            if isinstance(target_val, list):
                return actual_val not in target_val and actual_str not in [
                    str(x).lower().strip() for x in target_val
                ]
            return actual_str not in target_str

        return False

    @classmethod
    def evaluate(
        cls, context: dict[str, Any], conditions: dict[str, Any] | None
    ) -> tuple[bool, str]:
        """Evaluate workflow conditions (AND / OR / compound / single rule)."""
        if not conditions:
            return True, "No conditions specified; evaluated to True."

        # Compound: 'rules' list with combinator
        if "rules" in conditions and isinstance(conditions["rules"], list):
            sub_rules = conditions["rules"]
            combinator = (
                str(conditions.get("combinator") or conditions.get("operator") or "and")
                .lower()
                .strip()
            )
            if combinator in ["or", "any"]:
                for r in sub_rules:
                    if cls.evaluate_rule(context, r):
                        return (
                            True,
                            f"Rule '{r.get('field')} {r.get('operator')} {r.get('value')}' matched (OR).",
                        )
                return False, "No rule matched (OR combinator)."
            else:
                for r in sub_rules:
                    if not cls.evaluate_rule(context, r):
                        return (
                            False,
                            f"Rule '{r.get('field')} {r.get('operator')} {r.get('value')}' failed (AND).",
                        )
                return True, "All rules passed (AND combinator)."

        if "all" in conditions:
            for r in conditions["all"]:
                if not cls.evaluate_rule(context, r):
                    return (
                        False,
                        f"Rule '{r.get('field')} {r.get('operator')} {r.get('value')}' failed (ALL).",
                    )
            return True, "All conditions passed."

        if "any" in conditions:
            for r in conditions["any"]:
                if cls.evaluate_rule(context, r):
                    return (
                        True,
                        f"Rule '{r.get('field')} {r.get('operator')} {r.get('value')}' matched (ANY).",
                    )
            return False, "No 'any' condition matched."

        if "field" in conditions:
            passed = cls.evaluate_rule(context, conditions)
            return (
                passed,
                f"Rule '{conditions.get('field')} {conditions.get('operator')} {conditions.get('value')}' = {passed}.",
            )

        return True, "Conditions passed."


# ---------------------------------------------------------------------------
# Variable Substitutor
# ---------------------------------------------------------------------------


class VariableSubstitutor:
    """Replaces {{variable}} placeholders in strings, dicts, and lists from context."""

    ALIAS_MAP: dict[str, str] = {
        "vendorname": "vendor_name",
        "vendor": "vendor_name",
        "supplier": "vendor_name",
        "invoicenumber": "invoice_number",
        "invoiceno": "invoice_number",
        "ponumber": "po_number",
        "invoicedate": "invoice_date",
        "duedate": "due_date",
        "total": "total",
        "totalamount": "total",
        "amount": "total",
        "subtotal": "subtotal",
        "netamount": "subtotal",
        "tax": "tax",
        "taxamount": "tax",
        "documentid": "id",
        "docid": "id",
        "document.id": "id",
        "workspaceid": "workspace_id",
        "workspace.id": "workspace_id",
        "confidence": "confidence_score",
        "confidencescore": "confidence_score",
    }

    @classmethod
    def _resolve_key(cls, context: dict[str, Any], key_name: str) -> str:
        clean = key_name.strip()
        lookup = cls.ALIAS_MAP.get(clean.lower().replace("_", ""), clean)
        val: Any = context.get(lookup) or context.get(clean)
        if val is None:
            for k, v in context.items():
                if k.lower() == clean.lower() or k.lower().replace(
                    "_", ""
                ) == clean.lower().replace("_", ""):
                    val = v
                    break
        if isinstance(val, dict) and "value" in val:
            val = val.get("normalized_value") or val.get("value")
        return str(val) if val is not None else ""

    @classmethod
    def substitute_string(cls, template_str: str, context: dict[str, Any]) -> str:
        if not template_str or "{{" not in template_str:
            return template_str
        return re.sub(
            r"\{\{\s*([A-Za-z0-9_.:-]+)\s*\}\}",
            lambda m: cls._resolve_key(context, m.group(1)),
            template_str,
        )

    @classmethod
    def substitute_data(cls, data: Any, context: dict[str, Any]) -> Any:
        if isinstance(data, str):
            return cls.substitute_string(data, context)
        if isinstance(data, dict):
            return {k: cls.substitute_data(v, context) for k, v in data.items()}
        if isinstance(data, list):
            return [cls.substitute_data(item, context) for item in data]
        return data


# ---------------------------------------------------------------------------
# Workflow Engine
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Production workflow engine executing actions against document context."""

    # ---- HTTP helper -------------------------------------------------------

    @classmethod
    async def execute_http_request_with_retry(
        cls,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_body: Any | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> dict[str, Any]:
        """HTTP request with exponential backoff on 5xx and network errors."""
        headers = headers or {}
        method_upper = method.upper().strip()
        attempt = 0
        last_error = ""
        last_status_code = 500

        while attempt < max_retries:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method_upper,
                        url=url,
                        headers=headers,
                        json=json_body if method_upper in ["POST", "PUT", "PATCH"] else None,
                    )
                    last_status_code = response.status_code
                    if response.status_code >= 500 and attempt < max_retries:
                        await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
                        continue
                    resp_text = response.text[:2000] if response.text else ""
                    return {
                        "status_code": response.status_code,
                        "success": response.is_success,
                        "attempts": attempt,
                        "response_body": resp_text,
                        "error": None
                        if response.is_success
                        else f"HTTP {response.status_code}: {resp_text}",
                    }
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
                last_error = f"{type(exc).__name__}: {str(exc)}"
                if attempt < max_retries:
                    await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
            except Exception as exc:
                last_error = f"Unexpected error: {str(exc)}"
                break

        return {
            "status_code": last_status_code,
            "success": False,
            "attempts": attempt,
            "response_body": None,
            "error": last_error or f"Failed after {attempt} attempts",
        }

    # ---- Individual action handlers ----------------------------------------

    @classmethod
    async def _action_http_request(cls, params: dict[str, Any]) -> dict[str, Any]:
        url = params.get("url") or params.get("endpoint")
        if not url:
            raise ValueError("URL / endpoint parameter is required for HTTP request action.")
        method = params.get("method", "POST")
        headers = dict(params.get("headers", {}))
        body = params.get("body") or params.get("request_mapping")
        timeout = float(params.get("timeout", 10.0))
        retries = int(params.get("retries", 3))

        # Inject auth headers
        auth_cfg = params.get("auth") or {}
        if auth_cfg.get("type") == "BEARER_TOKEN" and auth_cfg.get("token"):
            headers["Authorization"] = f"Bearer {auth_cfg['token']}"
        elif auth_cfg.get("type") == "API_KEY" and auth_cfg.get("key"):
            headers[auth_cfg.get("header_name", "X-API-Key")] = auth_cfg["key"]
        elif auth_cfg.get("type") == "BASIC" and auth_cfg.get("username"):
            import base64

            creds = base64.b64encode(
                f"{auth_cfg['username']}:{auth_cfg.get('password', '')}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"

        return await cls.execute_http_request_with_retry(
            method=method,
            url=url,
            headers=headers,
            json_body=body,
            timeout=timeout,
            max_retries=retries,
        )

    @classmethod
    async def _action_notification(
        cls, params: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Send notification (Slack webhook, email stub, or generic alert)."""
        channel = params.get("channel", "default")
        message = VariableSubstitutor.substitute_string(
            params.get("message", "Workflow notification triggered."), context
        )
        subject = VariableSubstitutor.substitute_string(
            params.get("subject", "Document Intelligence Notification"), context
        )
        notification_type = str(params.get("notification_type", "GENERIC")).upper()

        result: dict[str, Any] = {
            "sent": True,
            "channel": channel,
            "message": message,
            "subject": subject,
            "notification_type": notification_type,
        }

        # If a webhook URL is configured for Slack/Teams, actually dispatch it
        webhook_url = params.get("webhook_url") or params.get("slack_webhook_url")
        if webhook_url:
            slack_body = {
                "text": f"*{subject}*\n{message}",
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*{subject}*"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"_Triggered at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}_",
                            }
                        ],
                    },
                ],
            }
            http_res = await cls.execute_http_request_with_retry(
                method="POST", url=webhook_url, json_body=slack_body, timeout=8.0, max_retries=2
            )
            result["webhook_dispatched"] = http_res["success"]
            result["webhook_response"] = http_res

        # Email stub (logs intent; real SMTP integration via config)
        if notification_type in ["EMAIL", "EMAIL_NOTIFICATION"] or params.get("to_email"):
            to_email = params.get("to_email") or params.get("recipients", [])
            result["email_stub"] = {
                "to": to_email,
                "subject": subject,
                "body": message,
                "note": "Email delivery requires SMTP integration. Configure SMTP in workspace integrations.",
            }

        return result

    @classmethod
    async def _action_update_document(
        cls, params: dict[str, Any], doc: Document | None
    ) -> dict[str, Any]:
        """Update document status and/or metadata."""
        if not doc:
            return {"updated": False, "reason": "No document in context."}

        target_status = params.get("status")
        meta_updates = params.get("metadata", {})
        tag_add = params.get("add_tag")
        tag_remove = params.get("remove_tag")

        if target_status:
            status_map = {
                "completed": DocumentStatus.COMPLETED,
                "review_required": DocumentStatus.REVIEW_REQUIRED,
                "reviewrequired": DocumentStatus.REVIEW_REQUIRED,
                "processing": DocumentStatus.PROCESSING,
                "queued": DocumentStatus.QUEUED,
                "uploaded": DocumentStatus.UPLOADED,
                "failed": DocumentStatus.FAILED,
                "rejected": DocumentStatus.REJECTED,
            }
            target_str = str(target_status).lower().strip()
            if target_str in status_map:
                doc.status = status_map[target_str]
            else:
                try:
                    doc.status = DocumentStatus(target_status)
                except ValueError:
                    pass

        doc_meta = dict(doc.metadata_json or {})
        if meta_updates:
            doc_meta.update(meta_updates)
        if tag_add:
            tags = doc_meta.get("tags", [])
            if tag_add not in tags:
                tags.append(tag_add)
            doc_meta["tags"] = tags
        if tag_remove:
            tags = doc_meta.get("tags", [])
            doc_meta["tags"] = [t for t in tags if t != tag_remove]
        doc.metadata_json = doc_meta

        return {
            "updated": True,
            "target_status": str(target_status),
            "metadata_updated": bool(meta_updates),
        }

    @classmethod
    async def _action_auto_approve(
        cls, params: dict[str, Any], doc: Document | None
    ) -> dict[str, Any]:
        """Automatically approve document if confidence threshold is met."""
        if not doc:
            return {"approved": False, "reason": "No document in context."}

        min_confidence = float(params.get("min_confidence", 0.85))
        current_conf = doc.confidence_score or 0.0

        if current_conf >= min_confidence:
            doc.status = DocumentStatus.COMPLETED
            doc.processing_error = None
            doc_meta = dict(doc.metadata_json or {})
            doc_meta["auto_approved"] = {
                "at": datetime.now(UTC).isoformat(),
                "confidence": current_conf,
                "threshold": min_confidence,
            }
            doc.metadata_json = doc_meta
            return {"approved": True, "confidence": current_conf, "threshold": min_confidence}
        else:
            doc.status = DocumentStatus.REVIEW_REQUIRED
            return {
                "approved": False,
                "reason": f"Confidence {current_conf:.2f} below threshold {min_confidence:.2f}",
                "confidence": current_conf,
                "threshold": min_confidence,
            }

    @classmethod
    async def _action_auto_reject(
        cls, params: dict[str, Any], doc: Document | None
    ) -> dict[str, Any]:
        """Automatically reject document if confidence is below threshold."""
        if not doc:
            return {"rejected": False, "reason": "No document in context."}

        max_confidence = float(params.get("max_confidence", 0.50))
        reason = params.get("reason", "Automatically rejected due to low confidence score.")
        current_conf = doc.confidence_score or 0.0

        if current_conf <= max_confidence:
            doc.status = DocumentStatus.REJECTED
            doc.processing_error = reason
            doc_meta = dict(doc.metadata_json or {})
            doc_meta["auto_rejected"] = {
                "at": datetime.now(UTC).isoformat(),
                "confidence": current_conf,
                "threshold": max_confidence,
                "reason": reason,
            }
            doc.metadata_json = doc_meta
            return {
                "rejected": True,
                "confidence": current_conf,
                "threshold": max_confidence,
                "reason": reason,
            }
        else:
            return {
                "rejected": False,
                "reason": f"Confidence {current_conf:.2f} above rejection threshold {max_confidence:.2f}",
            }

    @classmethod
    async def _action_require_approval(
        cls, params: dict[str, Any], doc: Document | None
    ) -> dict[str, Any]:
        """Flag document for manual approval by a specified role."""
        approval_role = params.get("role", "MANAGER")
        reason = params.get("reason", "Manager approval required based on workflow rule.")
        due_hours = int(params.get("due_in_hours", 24))

        if doc:
            doc.status = DocumentStatus.REVIEW_REQUIRED
            doc_meta = dict(doc.metadata_json or {})
            doc_meta["required_approval"] = {
                "role": approval_role,
                "reason": reason,
                "requested_at": datetime.now(UTC).isoformat(),
                "due_in_hours": due_hours,
            }
            doc.metadata_json = doc_meta

        return {
            "approval_required": True,
            "role": approval_role,
            "reason": reason,
            "due_in_hours": due_hours,
        }

    @classmethod
    async def _action_archive(cls, params: dict[str, Any], doc: Document | None) -> dict[str, Any]:
        """Mark document as archived in metadata."""
        archive_reason = params.get("reason", "Archived by automated workflow.")
        if doc:
            doc_meta = dict(doc.metadata_json or {})
            doc_meta["is_archived"] = True
            doc_meta["archived_at"] = datetime.now(UTC).isoformat()
            doc_meta["archive_reason"] = archive_reason
            doc.metadata_json = doc_meta
            doc.status = DocumentStatus.COMPLETED
        return {"archived": True, "reason": archive_reason}

    @classmethod
    async def _action_erp_export(
        cls, params: dict[str, Any], doc: Document | None, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Export extracted fields to an ERP system via REST API."""
        erp_url = params.get("erp_url") or params.get("url")
        if not erp_url:
            return {"exported": False, "reason": "erp_url not configured in action params."}

        # Build ERP payload from extracted fields in context
        field_keys = params.get(
            "fields",
            [
                "invoice_number",
                "vendor_name",
                "total",
                "tax",
                "subtotal",
                "invoice_date",
                "due_date",
                "currency",
                "po_number",
            ],
        )
        extracted_fields: dict[str, Any] = {}
        for key in field_keys:
            val = context.get(key)
            if isinstance(val, dict):
                val = val.get("normalized_value") or val.get("value")
            if val is not None:
                extracted_fields[key] = val

        erp_body = {
            "source": "document_intelligence_engine",
            "document_id": context.get("document_id") or (str(doc.id) if doc else None),
            "document_type": context.get("document_type", "unknown"),
            "workspace_id": context.get("workspace_id"),
            "extracted_fields": extracted_fields,
            "export_timestamp": datetime.now(UTC).isoformat(),
        }

        # Merge with custom mapping if provided
        custom_mapping = params.get("request_mapping", {})
        if custom_mapping:
            mapped = VariableSubstitutor.substitute_data(custom_mapping, context)
            erp_body.update(mapped)

        headers = dict(params.get("headers", {}))
        auth = params.get("auth", {})
        if auth.get("type") == "BEARER_TOKEN" and auth.get("token"):
            headers["Authorization"] = f"Bearer {auth['token']}"
        elif auth.get("type") == "API_KEY" and auth.get("key"):
            headers[auth.get("header_name", "X-API-Key")] = auth["key"]

        http_res = await cls.execute_http_request_with_retry(
            method=params.get("method", "POST"),
            url=erp_url,
            headers=headers,
            json_body=erp_body,
            timeout=float(params.get("timeout", 15.0)),
            max_retries=int(params.get("retries", 3)),
        )

        if doc and http_res["success"]:
            doc_meta = dict(doc.metadata_json or {})
            doc_meta["erp_export"] = {
                "exported_at": datetime.now(UTC).isoformat(),
                "erp_url": erp_url,
                "status_code": http_res["status_code"],
                "fields_exported": list(extracted_fields.keys()),
            }
            doc.metadata_json = doc_meta

        return {
            "exported": http_res["success"],
            "erp_url": erp_url,
            "fields_exported": list(extracted_fields.keys()),
            "http_result": http_res,
        }

    @classmethod
    async def _action_conditional_branch(
        cls,
        params: dict[str, Any],
        context: dict[str, Any],
        doc: Document | None,
    ) -> dict[str, Any]:
        """Execute a sub-set of actions based on a nested condition (IF/ELSE branching)."""
        condition = params.get("condition", {})
        if_actions: list[dict[str, Any]] = params.get("if_actions", [])
        else_actions: list[dict[str, Any]] = params.get("else_actions", [])

        branch_passed, eval_msg = ConditionEvaluator.evaluate(context, condition)
        actions_to_run = if_actions if branch_passed else else_actions

        branch_results: list[dict[str, Any]] = []
        for act in actions_to_run:
            sub_res = await workflow_engine.execute_action(act, context, doc)
            branch_results.append(sub_res)

        return {
            "branch_taken": "if" if branch_passed else "else",
            "condition_result": branch_passed,
            "condition_message": eval_msg,
            "actions_executed": len(branch_results),
            "branch_results": branch_results,
        }

    @classmethod
    async def _action_log(cls, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Log a custom message to the execution log."""
        message = VariableSubstitutor.substitute_string(
            params.get("message", "Workflow log entry."), context
        )
        level = str(params.get("level", "INFO")).upper()
        logger.log(
            logging.WARNING
            if level == "WARNING"
            else logging.ERROR
            if level == "ERROR"
            else logging.INFO,
            "[Workflow Log] %s",
            message,
        )
        return {"logged": True, "level": level, "message": message}

    @classmethod
    async def _action_set_metadata(
        cls, params: dict[str, Any], doc: Document | None, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Set arbitrary metadata key-value pairs on the document."""
        if not doc:
            return {"updated": False, "reason": "No document in context."}
        doc_meta = dict(doc.metadata_json or {})
        fields_to_set: dict[str, Any] = params.get("fields", {})
        for key, val_template in fields_to_set.items():
            resolved = VariableSubstitutor.substitute_data(val_template, context)
            doc_meta[key] = resolved
        doc.metadata_json = doc_meta
        return {"updated": True, "fields_set": list(fields_to_set.keys())}

    # ---- Main dispatcher ---------------------------------------------------

    @classmethod
    async def execute_action(
        cls,
        action: dict[str, Any],
        context: dict[str, Any],
        doc: Document | None = None,
    ) -> dict[str, Any]:
        """Dispatch and execute a single workflow action step by type."""
        action_type = str(action.get("type", "")).upper().strip()
        step_name = action.get("name", action_type)
        action_params = VariableSubstitutor.substitute_data(action.get("params", {}), context)

        result: dict[str, Any] = {
            "step_name": step_name,
            "action_type": action_type,
            "executed_at": datetime.now(UTC).isoformat(),
            "status": "COMPLETED",
            "output": None,
            "error": None,
        }

        try:
            # --- HTTP / Webhook actions ---
            if action_type in [
                "REST_API_REQUEST",
                "WEBHOOK",
                "HTTP_REQUEST",
                "POST_WEBHOOK",
                "API_CALL",
            ]:
                result["output"] = await cls._action_http_request(action_params)
                if not result["output"]["success"]:
                    result["status"] = "FAILED"
                    result["error"] = result["output"]["error"]

            # --- Notification actions ---
            elif action_type in [
                "NOTIFICATION",
                "SLACK_NOTIFICATION",
                "EMAIL_NOTIFICATION",
                "ALERT",
                "TEAMS_NOTIFICATION",
            ]:
                result["output"] = await cls._action_notification(action_params, context)

            # --- Document status & metadata updates ---
            elif action_type in [
                "DATABASE_UPDATE",
                "UPDATE_DOCUMENT",
                "UPDATE_STATUS",
                "SET_STATUS",
            ]:
                result["output"] = await cls._action_update_document(action_params, doc)

            # --- Auto-approve ---
            elif action_type in ["AUTO_APPROVE", "APPROVE", "AUTO_COMPLETE"]:
                result["output"] = await cls._action_auto_approve(action_params, doc)

            # --- Auto-reject ---
            elif action_type in ["AUTO_REJECT", "REJECT_LOW_CONFIDENCE"]:
                result["output"] = await cls._action_auto_reject(action_params, doc)

            # --- Require manual approval ---
            elif action_type in [
                "REQUIRE_APPROVAL",
                "REQUEST_APPROVAL",
                "FLAG_FOR_REVIEW",
                "APPROVAL",
            ]:
                result["output"] = await cls._action_require_approval(action_params, doc)

            # --- Archive ---
            elif action_type in ["ARCHIVE", "ARCHIVE_DOCUMENT"]:
                result["output"] = await cls._action_archive(action_params, doc)

            # --- ERP Export ---
            elif action_type in ["ERP_EXPORT", "EXPORT_TO_ERP", "SEND_TO_ERP"]:
                result["output"] = await cls._action_erp_export(action_params, doc, context)
                if result["output"] and not result["output"].get("exported"):
                    result["status"] = "FAILED"
                    result["error"] = result["output"].get("reason") or "ERP export failed"

            # --- Conditional branch (IF/ELSE) ---
            elif action_type in ["CONDITIONAL", "IF_ELSE", "BRANCH", "CONDITIONAL_BRANCH"]:
                result["output"] = await cls._action_conditional_branch(action_params, context, doc)

            # --- Log ---
            elif action_type in ["LOG", "LOG_MESSAGE", "AUDIT_LOG"]:
                result["output"] = await cls._action_log(action_params, context)

            # --- Set metadata ---
            elif action_type in ["SET_METADATA", "UPDATE_METADATA", "TAG_DOCUMENT"]:
                result["output"] = await cls._action_set_metadata(action_params, doc, context)

            # --- No-op / unknown ---
            else:
                logger.warning("Unknown action type '%s' — executing as no-op.", action_type)
                result["output"] = {
                    "message": f"Action type '{action_type}' is not registered. Treated as no-op.",
                    "registered_types": [
                        "REST_API_REQUEST",
                        "WEBHOOK",
                        "HTTP_REQUEST",
                        "NOTIFICATION",
                        "SLACK_NOTIFICATION",
                        "EMAIL_NOTIFICATION",
                        "UPDATE_DOCUMENT",
                        "AUTO_APPROVE",
                        "AUTO_REJECT",
                        "REQUIRE_APPROVAL",
                        "ARCHIVE",
                        "ERP_EXPORT",
                        "CONDITIONAL",
                        "LOG",
                        "SET_METADATA",
                    ],
                }

        except Exception as exc:
            result["status"] = "FAILED"
            result["error"] = str(exc)
            logger.error("Action '%s' (%s) failed: %s", step_name, action_type, exc, exc_info=True)

        return result


workflow_engine = WorkflowEngine()
