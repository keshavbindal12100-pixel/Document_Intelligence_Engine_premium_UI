import uuid

from backend.app.models.integration import Integration
from backend.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class IntegrationRepository(BaseRepository[Integration]):
    def __init__(self, db: AsyncSession):
        super().__init__(Integration, db)

    async def get_by_id_and_workspace(
        self, integration_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Integration | None:
        stmt = select(Integration).where(
            Integration.id == integration_id,
            Integration.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Integration]:
        stmt = (
            select(Integration)
            .where(Integration.workspace_id == workspace_id)
            .order_by(Integration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
