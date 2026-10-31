import uuid
from datetime import datetime

from backend.app.core.permissions import WorkspaceRole
from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    created_by_id: uuid.UUID | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class WorkspaceMemberAdd(BaseModel):
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    role: WorkspaceRole = WorkspaceRole.VIEWER


class WorkspaceMemberUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: WorkspaceRole

    class Config:
        from_attributes = True
