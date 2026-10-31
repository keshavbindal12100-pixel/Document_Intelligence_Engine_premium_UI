import uuid

from backend.app.models.audit_log import AuditLog
from backend.app.repositories.base import BaseRepository
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class AuditRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AuditLog, db)

    async def list_filtered(
        self,
        workspace_id: uuid.UUID,
        entity_id: str | uuid.UUID | None = None,
        document_id: str | uuid.UUID | None = None,
        entity_type: str | None = None,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog).where(AuditLog.workspace_id == workspace_id)
        count_stmt = select(func.count(AuditLog.id)).where(AuditLog.workspace_id == workspace_id)

        target_entity_id = entity_id or document_id
        if target_entity_id:
            target_str = str(target_entity_id)
            stmt = stmt.where(AuditLog.entity_id == target_str)
            count_stmt = count_stmt.where(AuditLog.entity_id == target_str)

        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
            count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)

        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
            count_stmt = count_stmt.where(AuditLog.user_id == user_id)

        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)

        total_res = await self.db.execute(count_stmt)
        total_count = total_res.scalar() or 0

        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())

        return items, total_count
