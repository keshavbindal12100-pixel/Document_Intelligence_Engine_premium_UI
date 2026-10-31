from backend.app.api.deps import require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.schemas.analytics import DashboardMetricsResponse, QueueStatusResponse
from backend.app.services.analytics_service import AnalyticsService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics_endpoint(
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    """Retrieve aggregate KPIs and document distribution metrics for workspace dashboard."""
    workspace, _ = ws_context
    service = AnalyticsService(db)
    return await service.get_dashboard_metrics(workspace.id)


@router.get("/queue", response_model=QueueStatusResponse)
async def get_queue_status_endpoint(
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> QueueStatusResponse:
    """Retrieve real-time processing queue counts and pipeline health status."""
    workspace, _ = ws_context
    service = AnalyticsService(db)
    return await service.get_queue_status(workspace.id)
