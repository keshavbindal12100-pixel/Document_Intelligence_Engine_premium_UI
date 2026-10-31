import uuid

from backend.app.core.exceptions import EntityNotFoundException
from backend.app.models.document_template import DocumentTemplate
from backend.app.schemas.template import DocumentTemplateCreate, DocumentTemplateUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[DocumentTemplate]:
        stmt = (
            select(DocumentTemplate)
            .where(DocumentTemplate.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_template(
        self, workspace_id: uuid.UUID, template_in: DocumentTemplateCreate
    ) -> DocumentTemplate:
        template = DocumentTemplate(
            workspace_id=workspace_id,
            name=template_in.name,
            document_type=template_in.document_type,
            is_active=template_in.is_active,
            rules_config={"field_rules": template_in.field_rules},
        )
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def get_template(
        self, template_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> DocumentTemplate:
        stmt = select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        template = res.scalar_one_or_none()
        if not template:
            raise EntityNotFoundException("DocumentTemplate", template_id)
        return template

    async def update_template(
        self, template_id: uuid.UUID, workspace_id: uuid.UUID, update_in: DocumentTemplateUpdate
    ) -> DocumentTemplate:
        template = await self.get_template(template_id, workspace_id)
        if update_in.name is not None:
            template.name = update_in.name
        if update_in.document_type is not None:
            template.document_type = update_in.document_type
        if update_in.is_active is not None:
            template.is_active = update_in.is_active
        if update_in.field_rules is not None:
            template.rules_config = {"field_rules": update_in.field_rules}
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        template = await self.get_template(template_id, workspace_id)
        await self.db.delete(template)
        await self.db.flush()
