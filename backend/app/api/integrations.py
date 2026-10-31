import uuid
from collections.abc import Sequence
from typing import Any

from backend.app.api.deps import require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.schemas.common import MessageResponse
from backend.app.schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationUpdate,
)
from backend.app.services.integration_service import IntegrationService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/integrations", tags=["Integrations & Webhooks"])


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    ws_context=Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> Sequence[IntegrationResponse]:
    """List integrations for the active workspace."""
    workspace, _ = ws_context
    service = IntegrationService(db)
    return await service.list_integrations(workspace.id, skip=skip, limit=limit)


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    integration_in: IntegrationCreate,
    ws_context=Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> IntegrationResponse:
    """Create a new integration or webhook subscription."""
    workspace, _ = ws_context
    service = IntegrationService(db)
    return await service.create_integration(workspace.id, integration_in)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> IntegrationResponse:
    """Get integration details."""
    workspace, _ = ws_context
    service = IntegrationService(db)
    return await service.get_integration(integration_id, workspace.id)


@router.put("/{integration_id}", response_model=IntegrationResponse)
@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: uuid.UUID,
    update_in: IntegrationUpdate,
    ws_context=Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> IntegrationResponse:
    """Update integration."""
    workspace, _ = ws_context
    service = IntegrationService(db)
    return await service.update_integration(integration_id, workspace.id, update_in)


@router.delete("/{integration_id}", response_model=MessageResponse)
async def delete_integration(
    integration_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete integration."""
    workspace, _ = ws_context
    service = IntegrationService(db)
    await service.delete_integration(integration_id, workspace.id)
    return MessageResponse(message="Integration deleted successfully.")


@router.post("/{integration_id}/test", response_model=dict[str, Any])
async def test_integration_webhook(
    integration_id: uuid.UUID,
    payload: dict[str, Any],
    ws_context=Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Test webhook delivery for an integration."""
    workspace, _ = ws_context
    service = IntegrationService(db)
    return await service.dispatch_webhook(integration_id, workspace.id, payload)
