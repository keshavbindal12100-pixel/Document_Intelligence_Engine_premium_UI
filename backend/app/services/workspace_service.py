import uuid
from collections.abc import Sequence

from backend.app.core.exceptions import (
    EntityAlreadyExistsException,
    EntityNotFoundException,
)
from backend.app.core.permissions import WorkspaceRole
from backend.app.models.user import UserWorkspace
from backend.app.models.workspace import Workspace
from backend.app.repositories.user_repo import UserRepository
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)
        self.user_repo = UserRepository(db)

    async def create_workspace(
        self, user_id: uuid.UUID, workspace_in: WorkspaceCreate
    ) -> Workspace:
        """Create a new workspace and assign creating user as ADMIN."""
        base_slug = workspace_in.slug or slugify(workspace_in.name)
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}" if not workspace_in.slug else base_slug

        existing = await self.workspace_repo.get_by_slug(slug)
        if existing:
            raise EntityAlreadyExistsException("Workspace slug", slug)

        workspace = Workspace(
            name=workspace_in.name,
            slug=slug,
            description=workspace_in.description,
            created_by_id=user_id,
        )
        workspace = await self.workspace_repo.create(workspace)

        # Assign creator as ADMIN
        await self.workspace_repo.add_member(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceRole.ADMIN,
        )

        return workspace

    async def get_workspace(self, workspace_id: uuid.UUID) -> Workspace:
        """Fetch workspace by ID."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise EntityNotFoundException("Workspace", workspace_id)
        return workspace

    async def list_user_workspaces(self, user_id: uuid.UUID) -> Sequence[Workspace]:
        """List all workspaces a user is a member of."""
        return await self.workspace_repo.list_for_user(user_id)

    async def update_workspace(
        self, workspace_id: uuid.UUID, update_in: WorkspaceUpdate
    ) -> Workspace:
        """Update workspace metadata."""
        workspace = await self.get_workspace(workspace_id)
        if update_in.name is not None:
            workspace.name = update_in.name
        if update_in.description is not None:
            workspace.description = update_in.description
        return await self.workspace_repo.update(workspace)

    async def add_member_by_email(
        self,
        workspace_id: uuid.UUID,
        email: str,
        role: WorkspaceRole = WorkspaceRole.VIEWER,
    ) -> UserWorkspace:
        """Add a member to workspace by email."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise EntityNotFoundException("User with email", email)

        existing_membership = await self.workspace_repo.get_membership(workspace_id, user.id)
        if existing_membership:
            raise EntityAlreadyExistsException("User membership in this workspace", email)

        membership = await self.workspace_repo.add_member(workspace_id, user.id, role)
        membership.user = user
        return membership

    async def update_member_role(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole
    ) -> UserWorkspace:
        """Update a member's role in the workspace."""
        membership = await self.workspace_repo.get_membership(workspace_id, user_id)
        if not membership:
            raise EntityNotFoundException("Workspace member", user_id)
        membership.role = role
        await self.db.flush()
        await self.db.refresh(membership)
        return membership

    async def remove_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove a member from the workspace."""
        success = await self.workspace_repo.remove_member(workspace_id, user_id)
        if not success:
            raise EntityNotFoundException("Workspace member", user_id)

    async def list_members(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[UserWorkspace]:
        """List all members of a workspace."""
        return await self.workspace_repo.list_members(workspace_id, skip=skip, limit=limit)
