import uuid
from typing import Any

from backend.app.models.extracted_field import FieldType
from pydantic import BaseModel, ConfigDict, model_validator


class ExtractedFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    field_name: str
    field_value: str | None = None
    field_type: FieldType | str = FieldType.STRING
    confidence: float | None = 0.0
    confidence_score: float = 0.0
    is_valid: bool = True
    is_verified: bool = False
    is_manually_corrected: bool = False
    is_human_corrected: bool = False
    source: str | None = None
    is_missing: bool = False
    normalized_value: Any | None = None
    validation_error: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if hasattr(data, "confidence") and not hasattr(data, "confidence_score"):
            data.confidence_score = data.confidence
        elif isinstance(data, dict):
            if "confidence_score" not in data and "confidence" in data:
                data["confidence_score"] = data["confidence"]
            if "confidence" not in data and "confidence_score" in data:
                data["confidence"] = data["confidence_score"]
        return data


class ExtractedFieldCorrection(BaseModel):
    field_name: str
    corrected_value: str
    field_id: uuid.UUID | None = None
    field_value: str | None = None
    is_valid: bool = True
    reason: str | None = None


class ValidationRuleResult(BaseModel):
    rule_name: str
    passed: bool
    details: str | None = None
    message: str | None = None


class ValidationResultResponse(BaseModel):
    status: str = "passed"
    is_valid: bool = True
    errors: list[str] = []
    warnings: list[str] = []
    rule_results: list[ValidationRuleResult] = []
    rules: list[ValidationRuleResult] = []


class DocumentExtractionSummary(BaseModel):
    document_id: uuid.UUID
    fields: list[ExtractedFieldResponse] = []
    confidence_avg: float = 1.0
    overall_confidence: float = 1.0
    total_fields: int = 0
    valid_fields: int = 0
    validation_status: str = "passed"


class DocumentExtractionResponse(BaseModel):
    document_id: uuid.UUID
    document_type: str = "unknown"
    classification_confidence: float = 0.0
    overall_confidence: float = 0.0
    total_fields: int = 0
    valid_fields: int = 0
    fields: dict[str, Any] = {}
    validation: Any | None = None
    raw_ocr_text: str = ""


class DocumentExtractionUpdateRequest(BaseModel):
    corrections: list[ExtractedFieldCorrection] = []
    fields: dict[str, Any] | None = None
    reason: str | None = None
    notes: str | None = None


class DocumentApprovalRequest(BaseModel):
    notes: str | None = None
    fields: dict[str, Any] | list[Any] | None = None


class DocumentRejectionRequest(BaseModel):
    reason: str
    notes: str | None = None


class DocumentReviewAction(BaseModel):
    action: str
    notes: str | None = None
    reason: str | None = None
    corrections: list[ExtractedFieldCorrection] = []
