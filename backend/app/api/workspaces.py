import uuid
from collections.abc import Sequence

from backend.app.api.deps import get_current_user, require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.common import MessageResponse
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from backend.app.services.workspace_service import WorkspaceService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=list[WorkspaceResponse])
async def list_my_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Sequence[Workspace]:
    """List all workspaces the current user is a member of."""
    service = WorkspaceService(db)
    return await service.list_user_workspaces(current_user.id)


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Create a new workspace."""
    service = WorkspaceService(db)
    return await service.create_workspace(current_user.id, workspace_in)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKSPACE_READ)),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Get workspace details."""
    workspace, _ = ws_context
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    update_in: WorkspaceUpdate,
    ws_context=Depends(require_permission(Permission.WORKSPACE_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Update workspace details."""
    service = WorkspaceService(db)
    return await service.update_workspace(workspace_id, update_in)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKSPACE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List all members of the workspace."""
    service = WorkspaceService(db)
    return await service.list_members(workspace_id)


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member(
    workspace_id: uuid.UUID,
    member_in: WorkspaceMemberAdd,
    ws_context=Depends(require_permission(Permission.WORKSPACE_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    """Add a user as member of the workspace."""
    service = WorkspaceService(db)
    if member_in.user_email:
        return await service.add_member_by_email(workspace_id, member_in.user_email, member_in.role)
    elif member_in.user_id:
        return await service.workspace_repo.add_member(
            workspace_id, member_in.user_id, member_in.role
        )
    else:
        raise HTTPException(status_code=400, detail="Either user_id or user_email must be provided")


@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse)
async def update_workspace_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    update_in: WorkspaceMemberUpdate,
    ws_context=Depends(require_permission(Permission.WORKSPACE_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
):
    """Update role for an existing workspace member."""
    service = WorkspaceService(db)
    return await service.update_member_role(workspace_id, user_id, update_in.role)


@router.delete("/{workspace_id}/members/{user_id}", response_model=MessageResponse)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKSPACE_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove member from workspace."""
    service = WorkspaceService(db)
    await service.remove_member(workspace_id, user_id)
    return MessageResponse(message="Member removed successfully.")
