import uuid

from backend.app.models.extracted_field import ExtractedField
from backend.app.repositories.base import BaseRepository
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class ExtractionRepository(BaseRepository[ExtractedField]):
    def __init__(self, db: AsyncSession):
        super().__init__(ExtractedField, db)

    async def list_by_document(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[ExtractedField]:
        stmt = select(ExtractedField).where(
            ExtractedField.document_id == document_id,
            ExtractedField.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_by_id_and_workspace(
        self, field_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> ExtractedField | None:
        stmt = select(ExtractedField).where(
            ExtractedField.id == field_id,
            ExtractedField.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_by_document(self, document_id: uuid.UUID, workspace_id: uuid.UUID) -> int:
        stmt = delete(ExtractedField).where(
            ExtractedField.document_id == document_id,
            ExtractedField.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        await self.db.flush()
        return res.rowcount

    async def batch_create(self, fields: list[ExtractedField]) -> list[ExtractedField]:
        for f in fields:
            self.db.add(f)
        await self.db.flush()
        for f in fields:
            await self.db.refresh(f)
        return fields
