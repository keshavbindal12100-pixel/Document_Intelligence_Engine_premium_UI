import uuid

from backend.app.core.permissions import WorkspaceRole
from backend.app.models.user import UserWorkspace
from backend.app.models.workspace import Workspace
from backend.app.repositories.base import BaseRepository
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, db: AsyncSession):
        super().__init__(Workspace, db)

    async def get_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.slug == slug)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def add_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole
    ) -> UserWorkspace:
        membership = await self.get_membership(workspace_id, user_id)
        if membership:
            membership.role = role
        else:
            membership = UserWorkspace(workspace_id=workspace_id, user_id=user_id, role=role)
            self.db.add(membership)
        await self.db.flush()
        return membership

    async def get_membership(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> UserWorkspace | None:
        stmt = select(UserWorkspace).where(
            UserWorkspace.workspace_id == workspace_id,
            UserWorkspace.user_id == user_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_role(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceRole | None:
        membership = await self.get_membership(workspace_id, user_id)
        return membership.role if membership else None

    async def remove_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = delete(UserWorkspace).where(
            UserWorkspace.workspace_id == workspace_id,
            UserWorkspace.user_id == user_id,
        )
        res = await self.db.execute(stmt)
        await self.db.flush()
        return res.rowcount > 0

    async def list_members(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[UserWorkspace]:
        stmt = (
            select(UserWorkspace)
            .where(UserWorkspace.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_for_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .join(UserWorkspace, Workspace.id == UserWorkspace.workspace_id)
            .where(UserWorkspace.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
