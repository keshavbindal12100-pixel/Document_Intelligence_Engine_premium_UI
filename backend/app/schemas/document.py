import uuid
from datetime import datetime
from typing import Any

from backend.app.models.document import DocumentStatus, DocumentType
from pydantic import BaseModel, ConfigDict, model_validator


class DocumentFilter(BaseModel):
    status: DocumentStatus | None = None
    document_type: DocumentType | None = None
    search: str | None = None
    page: int = 1
    size: int = 20
    page_size: int = 20
    min_confidence: float | None = None
    max_confidence: float | None = None
    upload_date_from: datetime | None = None
    upload_date_to: datetime | None = None
    vendor: str | None = None
    invoice_number: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"


class DocumentUpdate(BaseModel):
    file_name: str | None = None
    original_filename: str | None = None
    document_type: DocumentType | None = None
    status: DocumentStatus | None = None
    template_id: uuid.UUID | None = None
    metadata_json: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    file_name: str | None = None
    filename: str | None = None
    original_filename: str | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None
    file_size: int | None = None
    mime_type: str
    document_type: DocumentType
    status: DocumentStatus
    ocr_confidence: float | None = None
    confidence_score: float | None = None
    extracted_text: str | None = None
    metadata_json: dict[str, Any] | None = None
    processing_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "file_name" not in data and "original_filename" in data:
                data["file_name"] = data["original_filename"]
            if "file_size_bytes" not in data and "file_size" in data:
                data["file_size_bytes"] = data["file_size"]
            if "ocr_confidence" not in data and "confidence_score" in data:
                data["ocr_confidence"] = data["confidence_score"]
        return data
