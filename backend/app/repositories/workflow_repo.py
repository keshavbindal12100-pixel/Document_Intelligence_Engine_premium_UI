import uuid

from backend.app.models.workflow import Workflow, WorkflowTriggerType
from backend.app.models.workflow_execution import WorkflowExecution
from backend.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, db: AsyncSession):
        super().__init__(Workflow, db)

    async def get_by_id_and_workspace(
        self, workflow_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Workflow | None:
        stmt = select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Workflow]:
        stmt = (
            select(Workflow)
            .where(Workflow.workspace_id == workspace_id)
            .order_by(Workflow.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_by_trigger_type(
        self,
        workspace_id: uuid.UUID,
        trigger_type: WorkflowTriggerType | str,
        is_active: bool = True,
    ) -> list[Workflow]:
        trigger_str = trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type)
        try:
            trigger_enum = WorkflowTriggerType(trigger_str)
        except Exception:
            trigger_enum = trigger_str

        stmt = (
            select(Workflow)
            .where(
                Workflow.workspace_id == workspace_id,
                (Workflow.trigger_type == trigger_str) | (Workflow.trigger_type == trigger_enum),
                Workflow.is_active == is_active,
            )
            .order_by(Workflow.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())


class WorkflowExecutionRepository(BaseRepository[WorkflowExecution]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowExecution, db)

    async def get_by_id_and_workspace(
        self, execution_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkflowExecution | None:
        stmt = select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workspace_id == workspace_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_workflow(
        self, workflow_id: uuid.UUID, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[WorkflowExecution]:
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.workspace_id == workspace_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_by_document(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[WorkflowExecution]:
        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.document_id == document_id,
                WorkflowExecution.workspace_id == workspace_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
