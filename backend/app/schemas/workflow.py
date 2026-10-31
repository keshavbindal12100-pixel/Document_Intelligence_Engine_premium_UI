import uuid
from datetime import datetime
from typing import Any

from backend.app.models.workflow import WorkflowTriggerType
from backend.app.models.workflow_execution import ExecutionStatus
from pydantic import BaseModel


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    trigger_type: WorkflowTriggerType | str
    is_active: bool = True
    conditions: dict[str, Any] = {}
    actions: list[dict[str, Any]] = []


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: WorkflowTriggerType | str | None = None
    is_active: bool | None = None
    conditions: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None = None
    trigger_type: WorkflowTriggerType | str
    is_active: bool
    conditions: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class WorkflowExecutionResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID | None = None
    status: ExecutionStatus | str
    execution_logs: list[dict[str, Any]] | None = []
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True
