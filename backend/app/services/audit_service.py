import uuid
from collections.abc import Sequence
from typing import Any

from backend.app.models.audit_log import AuditLog
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.schemas.audit import AuditLogFilter
from sqlalchemy.ext.asyncio import AsyncSession


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_repo = AuditRepository(db)

    async def log_action(
        self,
        workspace_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: uuid.UUID | None = None,
        changes: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Record an audit trail event."""
        log = AuditLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self.audit_repo.create(log)

    async def list_logs(
        self, workspace_id: uuid.UUID, filters: AuditLogFilter
    ) -> tuple[Sequence[AuditLog], int]:
        """Query audit trail with filters."""
        skip = (filters.page - 1) * filters.page_size
        return await self.audit_repo.list_filtered(
            workspace_id=workspace_id,
            action=filters.action,
            entity_type=filters.entity_type,
            entity_id=filters.entity_id,
            user_id=filters.user_id,
            skip=skip,
            limit=filters.page_size,
        )
