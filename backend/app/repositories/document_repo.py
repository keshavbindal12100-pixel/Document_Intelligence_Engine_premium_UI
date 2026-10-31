import uuid
from typing import Any

from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.repositories.base import BaseRepository
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(Document, db)

    async def get_by_id_and_workspace(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_filtered(
        self,
        workspace_id: uuid.UUID,
        status: DocumentStatus | str | None = None,
        document_type: DocumentType | str | None = None,
        search: str | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        skip: int = 0,
        limit: int = 100,
        **kwargs: Any,
    ) -> tuple[list[Document], int]:
        stmt = select(Document).where(Document.workspace_id == workspace_id)
        count_stmt = select(func.count(Document.id)).where(Document.workspace_id == workspace_id)

        if status:
            stmt = stmt.where(Document.status == status)
            count_stmt = count_stmt.where(Document.status == status)
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
            count_stmt = count_stmt.where(Document.document_type == document_type)
        if min_confidence is not None:
            stmt = stmt.where(Document.confidence_score >= min_confidence)
            count_stmt = count_stmt.where(Document.confidence_score >= min_confidence)
        if max_confidence is not None:
            stmt = stmt.where(Document.confidence_score <= max_confidence)
            count_stmt = count_stmt.where(Document.confidence_score <= max_confidence)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Document.filename.ilike(search_pattern),
                    Document.original_filename.ilike(search_pattern),
                )
            )
            count_stmt = count_stmt.where(
                or_(
                    Document.filename.ilike(search_pattern),
                    Document.original_filename.ilike(search_pattern),
                )
            )

        total_res = await self.db.execute(count_stmt)
        total_count = total_res.scalar() or 0

        stmt = stmt.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())

        return items, total_count

    async def count_by_status(self, workspace_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(Document.status, func.count(Document.id))
            .where(Document.workspace_id == workspace_id)
            .group_by(Document.status)
        )
        res = await self.db.execute(stmt)
        return {str(row[0]): row[1] for row in res.all()}

    async def count_by_type(self, workspace_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(Document.document_type, func.count(Document.id))
            .where(Document.workspace_id == workspace_id)
            .group_by(Document.document_type)
        )
        res = await self.db.execute(stmt)
        return {str(row[0]): row[1] for row in res.all()}
