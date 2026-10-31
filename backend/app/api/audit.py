import math
import uuid

from backend.app.api.deps import require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.schemas.audit import AuditLogFilter, AuditLogResponse
from backend.app.schemas.common import PaginatedResponse
from backend.app.services.audit_service import AuditService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ws_context=Depends(require_permission(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuditLogResponse]:
    """Retrieve audit trail logs for active workspace."""
    workspace, _ = ws_context
    service = AuditService(db)
    filters = AuditLogFilter(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    items, total = await service.list_logs(workspace.id, filters)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[AuditLogResponse](
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
