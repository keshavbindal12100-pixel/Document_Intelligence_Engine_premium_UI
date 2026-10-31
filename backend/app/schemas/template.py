import uuid
from datetime import datetime
from typing import Any

from backend.app.models.document import DocumentType
from pydantic import BaseModel


class DocumentTemplateCreate(BaseModel):
    name: str
    document_type: DocumentType | str
    field_rules: list[dict[str, Any]] = []
    is_active: bool = True


class DocumentTemplateUpdate(BaseModel):
    name: str | None = None
    document_type: DocumentType | str | None = None
    field_rules: list[dict[str, Any]] | None = None
    is_active: bool | None = None


class DocumentTemplateResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    document_type: DocumentType | str
    field_rules: list[dict[str, Any]] | None = None
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
