import uuid
from datetime import datetime
from typing import Any

from backend.app.models.integration import IntegrationType
from pydantic import BaseModel


class IntegrationCreate(BaseModel):
    name: str
    type: IntegrationType | str
    config: dict[str, Any] = {}
    is_active: bool = True


class IntegrationUpdate(BaseModel):
    name: str | None = None
    type: IntegrationType | str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    type: IntegrationType | str
    config: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class IntegrationTestRequest(BaseModel):
    integration_id: uuid.UUID


class IntegrationTestResponse(BaseModel):
    success: bool
    message: str
    status_code: int | None = None
