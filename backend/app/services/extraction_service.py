import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.core.exceptions import EntityNotFoundException, ValidationException
from backend.app.models.audit_log import AuditLog
from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.models.extracted_field import ExtractedField, FieldType
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.extraction_repo import ExtractionRepository
from backend.app.schemas.extraction import (
    DocumentApprovalRequest,
    DocumentExtractionResponse,
    DocumentExtractionSummary,
    DocumentExtractionUpdateRequest,
    DocumentRejectionRequest,
    DocumentReviewAction,
    ExtractedFieldCorrection,
    ExtractedFieldResponse,
    ValidationResultResponse,
    ValidationRuleResult,
)
from backend.app.services.classifier import document_classifier
from backend.app.services.extractor import hybrid_extractor
from backend.app.services.validator import validation_engine
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.extraction_repo = ExtractionRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.audit_repo = AuditRepository(db)

    async def classify_and_extract_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        ocr_text: str,
        target_document_type: str | None = None,
    ) -> DocumentExtractionResponse:
        """Classify document OCR text, perform structured hybrid extraction, and run validation engine."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        # 1. Classification
        classification = document_classifier.classify(ocr_text)
        detected_type_str = target_document_type or classification["document_type"]

        # Map to DocumentType enum
        doc_type_enum = DocumentType.UNKNOWN
        if detected_type_str == "invoice":
            doc_type_enum = DocumentType.INVOICE
        elif detected_type_str == "purchase_order":
            doc_type_enum = DocumentType.PURCHASE_ORDER
        elif detected_type_str == "form":
            doc_type_enum = DocumentType.FORM

        doc.document_type = doc_type_enum

        # 2. Hybrid Extraction
        extracted_dict = hybrid_extractor.extract_document(
            text=ocr_text,
            document_type=detected_type_str,
        )

        # 3. Validation Engine Execution
        validation_output = validation_engine.validate_document(
            document_type=detected_type_str,
            fields=extracted_dict,
        )

        # 4. Clean existing fields if any (idempotency)
        await self.extraction_repo.delete_by_document(document_id, workspace_id)

        # 5. Save ExtractedField rows
        saved_fields_map: dict[str, ExtractedField] = {}
        field_records: list[ExtractedField] = []

        for f_name, f_data in extracted_dict.items():
            f_val = str(f_data["value"]) if f_data["value"] is not None else None
            norm_val = f_data.get("normalized_value")
            f_type_str = f_data.get("field_type", FieldType.STRING.value)
            f_conf = float(f_data.get("confidence", 0.0))
            is_miss = bool(f_data.get("is_missing", f_val is None))

            # Store metadata (source, missing status) in bounding_box JSON payload
            meta_payload = {
                "source": f_data.get("source", "extracted"),
                "is_missing": is_miss,
            }

            field_type_enum = FieldType.STRING
            try:
                field_type_enum = FieldType(f_type_str)
            except ValueError:
                field_type_enum = FieldType.STRING

            field_obj = ExtractedField(
                id=uuid.uuid4(),
                document_id=document_id,
                workspace_id=workspace_id,
                field_name=f_name,
                field_value=f_val,
                normalized_value=norm_val,
                field_type=field_type_enum,
                confidence=f_conf,
                bounding_box=meta_payload,
                is_valid=not is_miss,
                is_manually_corrected=False,
            )
            field_records.append(field_obj)
            saved_fields_map[f_name] = field_obj

        if field_records:
            await self.extraction_repo.batch_create(field_records)

        # 6. Compute overall confidence score & store metadata
        total_fields = len(field_records)
        valid_fields = sum(1 for f in field_records if f.is_valid)
        field_confs = [
            f.confidence
            for f in field_records
            if not (f.bounding_box or {}).get("is_missing", False)
        ]
        avg_field_conf = sum(field_confs) / len(field_confs) if field_confs else 0.0

        overall_conf = round((classification["confidence"] * 0.4) + (avg_field_conf * 0.6), 4)

        # 7. Review Routing based on confidence & validation
        thresholds = (doc.metadata_json or {}).get(
            "confidence_thresholds",
            {"auto_process": 0.85, "optional_review": 0.80},
        )
        auto_thresh = float(thresholds.get("auto_process", 0.85))

        if overall_conf >= auto_thresh and validation_output["is_valid"]:
            doc.status = DocumentStatus.COMPLETED
        else:
            doc.status = DocumentStatus.REVIEW_REQUIRED

        doc.confidence_score = overall_conf
        meta = dict(doc.metadata_json or {})
        meta["classification"] = classification
        meta["validation"] = validation_output
        meta["extraction_summary"] = {
            "total_fields": total_fields,
            "valid_fields": valid_fields,
            "document_type": detected_type_str,
            "classification_confidence": classification["confidence"],
            "validation_status": validation_output["status"],
            "is_valid": validation_output["is_valid"],
        }
        doc.metadata_json = meta
        await self.doc_repo.update(doc)
        await self.db.commit()

        # 8. Trigger Automated Workflows for Lifecycle Events
        try:
            from backend.app.models.workflow import WorkflowTriggerType
            from backend.app.services.workflow_service import WorkflowService

            wf_service = WorkflowService(self.db)
            await wf_service.execute_matching_workflows(
                workspace_id=workspace_id,
                trigger_type=WorkflowTriggerType.ON_DOCUMENT_EXTRACTED,
                document_id=document_id,
            )
            if doc.status == DocumentStatus.REVIEW_REQUIRED or overall_conf < auto_thresh:
                await wf_service.execute_matching_workflows(
                    workspace_id=workspace_id,
                    trigger_type=WorkflowTriggerType.ON_LOW_CONFIDENCE,
                    document_id=document_id,
                )
        except Exception as wf_err:
            logger.warning("Workflow execution on extraction completed with warning: %s", wf_err)

        # Build response dict
        response_fields: dict[str, ExtractedFieldResponse] = {}
        for k, f in saved_fields_map.items():
            resp = ExtractedFieldResponse.model_validate(f)
            resp.source = (f.bounding_box or {}).get("source", "extracted")
            resp.is_missing = (f.bounding_box or {}).get("is_missing", False)
            response_fields[k] = resp

        val_response = ValidationResultResponse(
            status=validation_output["status"],
            is_valid=validation_output["is_valid"],
            errors=validation_output["errors"],
            warnings=validation_output["warnings"],
            rule_results=[ValidationRuleResult(**r) for r in validation_output["rule_results"]],
        )

        return DocumentExtractionResponse(
            document_id=document_id,
            document_type=detected_type_str,
            classification_confidence=classification["confidence"],
            overall_confidence=overall_conf,
            total_fields=total_fields,
            valid_fields=valid_fields,
            validation=val_response,
            fields=response_fields,
        )

    async def get_document_extraction(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> DocumentExtractionResponse:
        """Fetch all extracted fields and classification data for a document."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        fields = await self.extraction_repo.list_by_document(document_id, workspace_id)
        total_fields = len(fields)
        valid_fields = sum(1 for f in fields if f.is_valid)

        classification_meta = (doc.metadata_json or {}).get("classification", {})
        class_conf = classification_meta.get("confidence", 0.0)
        validation_meta = (doc.metadata_json or {}).get("validation", None)
        raw_ocr_text = (doc.metadata_json or {}).get("ocr_result", {}).get("full_text", "")

        val_response: ValidationResultResponse | None = None
        if validation_meta:
            val_response = ValidationResultResponse(
                status=validation_meta.get("status", "passed"),
                is_valid=validation_meta.get("is_valid", True),
                errors=validation_meta.get("errors", []),
                warnings=validation_meta.get("warnings", []),
                rule_results=[
                    ValidationRuleResult(**r) for r in validation_meta.get("rule_results", [])
                ],
            )

        response_fields: dict[str, ExtractedFieldResponse] = {}
        for f in fields:
            resp = ExtractedFieldResponse.model_validate(f)
            resp.source = (f.bounding_box or {}).get("source", "extracted")
            resp.is_missing = (f.bounding_box or {}).get("is_missing", False)
            response_fields[f.field_name] = resp

        return DocumentExtractionResponse(
            document_id=document_id,
            document_type=doc.document_type.value.lower() if doc.document_type else "unknown",
            classification_confidence=class_conf,
            overall_confidence=doc.confidence_score or 0.0,
            total_fields=total_fields,
            valid_fields=valid_fields,
            validation=val_response,
            fields=response_fields,
            raw_ocr_text=raw_ocr_text,
        )

    async def update_document_extraction(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        payload: DocumentExtractionUpdateRequest,
        user_id: uuid.UUID | None = None,
    ) -> DocumentExtractionResponse:
        """Update or manually correct extracted fields on a document and create audit logs."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        existing_fields = await self.extraction_repo.list_by_document(document_id, workspace_id)
        field_by_name = {f.field_name: f for f in existing_fields}
        field_by_id = {f.id: f for f in existing_fields}

        reason_text = payload.reason or "Manual human correction"

        # 1. Update from corrections list
        if payload.corrections:
            for corr in payload.corrections:
                target_field: ExtractedField | None = None
                if corr.field_id and corr.field_id in field_by_id:
                    target_field = field_by_id[corr.field_id]
                elif corr.field_name and corr.field_name in field_by_name:
                    target_field = field_by_name[corr.field_name]

                if target_field:
                    old_v = target_field.field_value
                    new_v = corr.field_value
                    target_field.field_value = new_v
                    target_field.normalized_value = new_v
                    target_field.is_valid = corr.is_valid
                    target_field.confidence = 1.0
                    target_field.is_manually_corrected = True
                    target_field.corrected_by_id = user_id
                    target_field.bounding_box = {
                        "source": "manual_correction",
                        "is_missing": False,
                    }
                    await self.extraction_repo.update(target_field)

                    # Create AuditLog record
                    audit = AuditLog(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        user_id=user_id,
                        action="FIELD_CORRECTED",
                        entity_type="EXTRACTED_FIELD",
                        entity_id=str(target_field.id),
                        changes={
                            "field_name": target_field.field_name,
                            "old_value": old_v,
                            "new_value": new_v,
                            "reason": corr.reason or reason_text,
                            "document_id": str(document_id),
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                    await self.audit_repo.create(audit)

        # 2. Update from fields dict
        if payload.fields:
            for k, val in payload.fields.items():
                val_str = str(val) if val is not None else None
                if k in field_by_name:
                    field = field_by_name[k]
                    old_v = field.field_value
                    field.field_value = val_str
                    field.normalized_value = val
                    field.is_valid = val is not None
                    field.confidence = 1.0
                    field.is_manually_corrected = True
                    field.corrected_by_id = user_id
                    field.bounding_box = {
                        "source": "manual_correction",
                        "is_missing": val is None,
                    }
                    await self.extraction_repo.update(field)

                    audit = AuditLog(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        user_id=user_id,
                        action="FIELD_CORRECTED",
                        entity_type="EXTRACTED_FIELD",
                        entity_id=str(field.id),
                        changes={
                            "field_name": k,
                            "old_value": old_v,
                            "new_value": val_str,
                            "reason": reason_text,
                            "document_id": str(document_id),
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                    await self.audit_repo.create(audit)
                else:
                    new_field = ExtractedField(
                        id=uuid.uuid4(),
                        document_id=document_id,
                        workspace_id=workspace_id,
                        field_name=k,
                        field_value=val_str,
                        normalized_value=val,
                        field_type=FieldType.STRING,
                        confidence=1.0,
                        bounding_box={
                            "source": "manual_correction",
                            "is_missing": val is None,
                        },
                        is_valid=val is not None,
                        is_manually_corrected=True,
                        corrected_by_id=user_id,
                    )
                    created_field = await self.extraction_repo.create(new_field)

                    audit = AuditLog(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        user_id=user_id,
                        action="FIELD_ADDED",
                        entity_type="EXTRACTED_FIELD",
                        entity_id=str(created_field.id),
                        changes={
                            "field_name": k,
                            "old_value": None,
                            "new_value": val_str,
                            "reason": reason_text,
                            "document_id": str(document_id),
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                    await self.audit_repo.create(audit)

        # 3. Re-run validation on updated fields
        refreshed_fields = await self.extraction_repo.list_by_document(document_id, workspace_id)
        current_dict: dict[str, Any] = {
            f.field_name: {
                "value": f.field_value,
                "normalized_value": f.normalized_value,
                "is_missing": (f.bounding_box or {}).get("is_missing", f.field_value is None),
            }
            for f in refreshed_fields
        }
        val_output = validation_engine.validate_document(
            document_type=doc.document_type.value if doc.document_type else "invoice",
            fields=current_dict,
        )

        meta = dict(doc.metadata_json or {})
        meta["validation"] = val_output
        doc.metadata_json = meta
        await self.doc_repo.update(doc)
        await self.db.commit()

        return await self.get_document_extraction(document_id, workspace_id)

    async def approve_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        approval_in: DocumentApprovalRequest,
    ) -> Document:
        """Approve document after human review and record audit log."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        # Apply any field updates passed with approval
        if getattr(approval_in, "fields", None):
            await self.update_document_extraction(
                document_id=document_id,
                workspace_id=workspace_id,
                payload=DocumentExtractionUpdateRequest(
                    fields=approval_in.fields,
                    reason="Updated on approval",
                ),
                user_id=user_id,
            )

        doc.status = DocumentStatus.COMPLETED
        doc.processing_error = None
        updated_doc = await self.doc_repo.update(doc)

        # Audit log for approval
        audit = AuditLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            action="DOCUMENT_APPROVED",
            entity_type="DOCUMENT",
            entity_id=str(document_id),
            changes={
                "notes": approval_in.notes,
                "status": "completed",
                "document_id": str(document_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        await self.audit_repo.create(audit)
        await self.db.commit()

        # Trigger Automated Workflows for Document Approval
        try:
            from backend.app.models.workflow import WorkflowTriggerType
            from backend.app.services.workflow_service import WorkflowService

            wf_service = WorkflowService(self.db)
            await wf_service.execute_matching_workflows(
                workspace_id=workspace_id,
                trigger_type=WorkflowTriggerType.ON_DOCUMENT_APPROVED,
                document_id=document_id,
            )
        except Exception as wf_err:
            logger.warning(
                "Workflow execution on document approval completed with warning: %s", wf_err
            )

        return updated_doc

    async def reject_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        rejection_in: DocumentRejectionRequest,
    ) -> Document:
        """Reject document and record audit log with reason."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        doc.status = DocumentStatus.REJECTED
        doc.processing_error = rejection_in.reason
        updated_doc = await self.doc_repo.update(doc)

        # Audit log for rejection
        audit = AuditLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            action="DOCUMENT_REJECTED",
            entity_type="DOCUMENT",
            entity_id=str(document_id),
            changes={
                "reason": rejection_in.reason,
                "notes": rejection_in.notes,
                "status": "rejected",
                "document_id": str(document_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        await self.audit_repo.create(audit)
        await self.db.commit()

        # Trigger Automated Workflows for Document Rejection
        try:
            from backend.app.models.workflow import WorkflowTriggerType
            from backend.app.services.workflow_service import WorkflowService

            wf_service = WorkflowService(self.db)
            await wf_service.execute_matching_workflows(
                workspace_id=workspace_id,
                trigger_type=WorkflowTriggerType.ON_DOCUMENT_REJECTED,
                document_id=document_id,
                context={
                    "rejection_reason": rejection_in.reason,
                    "rejection_notes": rejection_in.notes,
                },
            )
        except Exception as wf_err:
            logger.warning(
                "Workflow execution on document rejection completed with warning: %s", wf_err
            )

        return updated_doc

    async def get_document_extractions(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> DocumentExtractionSummary:
        """Fetch all extracted fields and summary metrics for a document."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        fields = await self.extraction_repo.list_by_document(document_id, workspace_id)
        field_responses = [ExtractedFieldResponse.model_validate(f) for f in fields]

        total_fields = len(fields)
        valid_fields = sum(1 for f in fields if f.is_valid)
        avg_confidence = (
            sum(f.confidence for f in fields) / total_fields if total_fields > 0 else 0.0
        )

        return DocumentExtractionSummary(
            document_id=document_id,
            overall_confidence=round(doc.confidence_score or avg_confidence, 4),
            total_fields=total_fields,
            valid_fields=valid_fields,
            fields=field_responses,
        )

    async def correct_field(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        correction: ExtractedFieldCorrection,
    ) -> ExtractedField:
        """Manually correct an extracted field during human review with audit tracking."""
        if not correction.field_id:
            raise ValidationException("field_id is required for correction")
        field = await self.extraction_repo.get_by_id_and_workspace(
            correction.field_id, workspace_id
        )
        if not field or field.document_id != document_id:
            raise EntityNotFoundException("ExtractedField", correction.field_id)

        old_val = field.field_value
        field.field_value = correction.field_value
        field.normalized_value = correction.field_value
        field.is_valid = correction.is_valid
        field.is_manually_corrected = True
        field.corrected_by_id = user_id
        field.validation_error = None
        field.bounding_box = {
            "source": "manual_correction",
            "is_missing": False,
        }

        updated_field = await self.extraction_repo.update(field)

        # Record audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            action="FIELD_CORRECTED",
            entity_type="EXTRACTED_FIELD",
            entity_id=str(field.id),
            changes={
                "field_name": field.field_name,
                "old_value": old_val,
                "new_value": correction.field_value,
                "reason": correction.reason or "Manual correction",
                "document_id": str(document_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        await self.audit_repo.create(audit)
        await self.db.commit()
        return updated_field

    async def review_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        review: DocumentReviewAction,
    ) -> Document:
        """Approve or reject a document after human review with optional corrections."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)

        action_upper = review.action.upper()
        if action_upper not in ["APPROVE", "REJECT"]:
            raise ValidationException("Review action must be 'APPROVE' or 'REJECT'")

        if review.corrections:
            for corr in review.corrections:
                await self.correct_field(document_id, workspace_id, user_id, corr)

        if action_upper == "APPROVE":
            return await self.approve_document(
                document_id=document_id,
                workspace_id=workspace_id,
                user_id=user_id,
                approval_in=DocumentApprovalRequest(notes=review.notes),
            )
        else:
            return await self.reject_document(
                document_id=document_id,
                workspace_id=workspace_id,
                user_id=user_id,
                rejection_in=DocumentRejectionRequest(
                    reason=review.notes or "Rejected by human reviewer."
                ),
            )
