import uuid
from collections.abc import Sequence

from backend.app.api.deps import require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.models.document_template import DocumentTemplate
from backend.app.schemas.common import MessageResponse
from backend.app.schemas.template import (
    DocumentTemplateCreate,
    DocumentTemplateResponse,
    DocumentTemplateUpdate,
)
from backend.app.services.template_service import TemplateService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/templates", tags=["Document Templates"])


@router.get("", response_model=list[DocumentTemplateResponse])
async def list_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    ws_context=Depends(require_permission(Permission.TEMPLATE_READ)),
    db: AsyncSession = Depends(get_db),
) -> Sequence[DocumentTemplate]:
    """List document templates for the active workspace."""
    workspace, _ = ws_context
    service = TemplateService(db)
    return await service.list_templates(workspace.id, skip=skip, limit=limit)


@router.post("", response_model=DocumentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_in: DocumentTemplateCreate,
    ws_context=Depends(require_permission(Permission.TEMPLATE_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> DocumentTemplate:
    """Create a new extraction template."""
    workspace, _ = ws_context
    service = TemplateService(db)
    return await service.create_template(workspace.id, template_in)


@router.get("/{template_id}", response_model=DocumentTemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.TEMPLATE_READ)),
    db: AsyncSession = Depends(get_db),
) -> DocumentTemplate:
    """Get extraction template details."""
    workspace, _ = ws_context
    service = TemplateService(db)
    return await service.get_template(template_id, workspace.id)


@router.put("/{template_id}", response_model=DocumentTemplateResponse)
@router.patch("/{template_id}", response_model=DocumentTemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    update_in: DocumentTemplateUpdate,
    ws_context=Depends(require_permission(Permission.TEMPLATE_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> DocumentTemplate:
    """Update extraction template."""
    workspace, _ = ws_context
    service = TemplateService(db)
    return await service.update_template(template_id, workspace.id, update_in)


@router.delete("/{template_id}", response_model=MessageResponse)
async def delete_template(
    template_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.TEMPLATE_DELETE)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete extraction template."""
    workspace, _ = ws_context
    service = TemplateService(db)
    await service.delete_template(template_id, workspace.id)
    return MessageResponse(message="Template deleted successfully.")
