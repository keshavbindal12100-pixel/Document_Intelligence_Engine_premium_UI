import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class AuditLogFilter(BaseModel):
    document_id: uuid.UUID | str | None = None
    entity_id: str | None = None
    entity_type: str | None = None
    user_id: uuid.UUID | None = None
    action: str | None = None
    page: int = 1
    size: int = 50
    page_size: int = 50

    @model_validator(mode="before")
    @classmethod
    def sync_size(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "page_size" in data and "size" not in data:
                data["size"] = data["page_size"]
            elif "size" in data and "page_size" not in data:
                data["page_size"] = data["size"]
        return data


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    entity_type: str | None = None
    entity_id: str | None = None
    document_id: str | uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    action: str
    changes: dict[str, Any] | None = None
    details: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if hasattr(data, "changes") and not getattr(data, "details", None):
            data.details = data.changes
        if hasattr(data, "entity_id") and not getattr(data, "document_id", None):
            data.document_id = data.entity_id
        elif isinstance(data, dict):
            if "details" not in data and "changes" in data:
                data["details"] = data["changes"]
            if "document_id" not in data and "entity_id" in data:
                data["document_id"] = data["entity_id"]
        return data
