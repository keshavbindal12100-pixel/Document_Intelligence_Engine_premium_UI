import uuid
from collections.abc import Sequence
from typing import Any

from backend.app.api.deps import require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.models.workflow import Workflow
from backend.app.models.workflow_execution import WorkflowExecution
from backend.app.schemas.common import MessageResponse
from backend.app.schemas.workflow import (
    WorkflowCreate,
    WorkflowExecutionResponse,
    WorkflowResponse,
    WorkflowUpdate,
)
from backend.app.services.workflow_service import WorkflowService
from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/workflows", tags=["Workflows & Automation"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    ws_context=Depends(require_permission(Permission.WORKFLOW_READ)),
    db: AsyncSession = Depends(get_db),
) -> Sequence[Workflow]:
    """List all automation workflows for the active workspace."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.list_workflows(workspace.id, skip=skip, limit=limit)


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_in: WorkflowCreate,
    ws_context=Depends(require_permission(Permission.WORKFLOW_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    """Create a new automation workflow with trigger, conditions, and action steps."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.create_workflow(workspace.id, workflow_in)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKFLOW_READ)),
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    """Get full details for a single workflow."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.get_workflow(workflow_id, workspace.id)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    update_in: WorkflowUpdate,
    ws_context=Depends(require_permission(Permission.WORKFLOW_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    """Update workflow configuration (trigger, conditions, actions, active flag)."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.update_workflow(workflow_id, workspace.id, update_in)


@router.delete("/{workflow_id}", response_model=MessageResponse)
async def delete_workflow(
    workflow_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKFLOW_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a workflow and all its execution history."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    await service.delete_workflow(workflow_id, workspace.id)
    return MessageResponse(message="Workflow deleted successfully.")


# ---------------------------------------------------------------------------
# Test / Dry-run
# ---------------------------------------------------------------------------


@router.post("/{workflow_id}/test", response_model=dict[str, Any])
async def test_workflow_endpoint(
    workflow_id: uuid.UUID,
    test_context: dict[str, Any],
    ws_context=Depends(require_permission(Permission.WORKFLOW_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Dry-run: evaluate conditions and show what actions WOULD execute — zero side effects."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.test_workflow(workflow_id, workspace.id, test_context)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def trigger_workflow_execution(
    workflow_id: uuid.UUID,
    document_id: uuid.UUID | None = Query(None),
    ws_context=Depends(require_permission(Permission.WORKFLOW_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecution:
    """Synchronously execute a workflow and return the completed execution record."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.trigger_execution(
        workflow_id=workflow_id,
        workspace_id=workspace.id,
        document_id=document_id,
    )


@router.post("/{workflow_id}/dispatch", response_model=dict[str, Any])
async def dispatch_workflow_async_endpoint(
    workflow_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    document_id: uuid.UUID | None = Query(None),
    custom_context: dict[str, Any] | None = None,
    ws_context=Depends(require_permission(Permission.WORKFLOW_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Async dispatch: queue workflow via Celery if available, BackgroundTasks otherwise."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.dispatch_workflow_async(
        workflow_id=workflow_id,
        workspace_id=workspace.id,
        document_id=document_id,
        custom_context=custom_context,
        background_tasks=background_tasks,
    )


# ---------------------------------------------------------------------------
# Execution history + Retry + Stats  (NEW)
# ---------------------------------------------------------------------------


@router.get("/{workflow_id}/executions", response_model=list[WorkflowExecutionResponse])
async def list_workflow_executions(
    workflow_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    ws_context=Depends(require_permission(Permission.WORKFLOW_READ)),
    db: AsyncSession = Depends(get_db),
) -> Sequence[WorkflowExecution]:
    """List all past execution records for a workflow (newest first)."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.list_executions(
        workflow_id=workflow_id,
        workspace_id=workspace.id,
        skip=skip,
        limit=limit,
    )


@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_execution_detail(
    workflow_id: uuid.UUID,
    execution_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKFLOW_READ)),
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecution:
    """Get full detail (logs, status, timing) for a single workflow execution."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.get_execution(execution_id, workspace.id)


@router.post(
    "/{workflow_id}/executions/{execution_id}/retry",
    response_model=WorkflowExecutionResponse,
)
async def retry_failed_execution(
    workflow_id: uuid.UUID,
    execution_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKFLOW_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecution:
    """Retry a previously FAILED or CANCELLED execution with the same document context."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.retry_execution(execution_id, workspace.id)


@router.get("/{workflow_id}/stats", response_model=dict[str, Any])
async def get_workflow_stats(
    workflow_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.WORKFLOW_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return aggregated execution stats: total runs, success rate, avg duration, etc."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.get_execution_stats(workflow_id, workspace.id)


# ---------------------------------------------------------------------------
# Bulk execute  (NEW)
# ---------------------------------------------------------------------------


@router.post("/bulk-execute", response_model=list[dict[str, Any]])
async def bulk_execute_workflows_endpoint(
    workflow_ids: list[uuid.UUID],
    document_id: uuid.UUID | None = Query(None),
    custom_context: dict[str, Any] | None = None,
    ws_context=Depends(require_permission(Permission.WORKFLOW_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Execute multiple specified workflows in sequence and return a summary of each."""
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.bulk_execute_workflows(
        workspace_id=workspace.id,
        workflow_ids=workflow_ids,
        document_id=document_id,
        custom_context=custom_context,
    )


# ---------------------------------------------------------------------------
# Scheduled trigger  (NEW)
# ---------------------------------------------------------------------------


@router.post("/trigger/scheduled", response_model=list[dict[str, Any]])
async def fire_scheduled_workflows(
    background_tasks: BackgroundTasks,
    ws_context=Depends(require_permission(Permission.WORKFLOW_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Fire all active SCHEDULED workflows for this workspace.
    Call this endpoint from a cron job / APScheduler every N minutes.
    """
    workspace, _ = ws_context
    service = WorkflowService(db)
    return await service.fire_scheduled_workflows(workspace.id, background_tasks)


# ---------------------------------------------------------------------------
# Event trigger (fire by event name)  (NEW)
# ---------------------------------------------------------------------------


@router.post("/trigger/event", response_model=list[dict[str, Any]])
async def fire_event_trigger(
    trigger_type: str = Query(..., description="e.g. ON_DOCUMENT_UPLOADED, ON_DOCUMENT_EXTRACTED"),
    document_id: uuid.UUID | None = Query(None),
    ws_context=Depends(require_permission(Permission.WORKFLOW_EXECUTE)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Manually fire all workflows that match a given trigger event type.
    Useful for testing event-driven automation or triggering from external systems.
    """
    workspace, _ = ws_context
    service = WorkflowService(db)
    executions = await service.execute_matching_workflows(
        workspace_id=workspace.id,
        trigger_type=trigger_type,
        document_id=document_id,
    )
    return [
        {
            "execution_id": str(ex.id),
            "workflow_id": str(ex.workflow_id),
            "status": ex.status.value,
            "error": ex.error_message,
        }
        for ex in executions
    ]
