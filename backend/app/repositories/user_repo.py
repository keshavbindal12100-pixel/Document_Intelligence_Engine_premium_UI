import uuid

from backend.app.models.user import User, UserWorkspace
from backend.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_workspaces(self, user_id: uuid.UUID) -> User | None:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(User)
            .options(selectinload(User.workspace_memberships).selectinload(UserWorkspace.workspace))
            .where(User.id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
