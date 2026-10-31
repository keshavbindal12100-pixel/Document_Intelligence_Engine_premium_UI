import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from backend.app.core.exceptions import EntityNotFoundException, ValidationException
from backend.app.models.document import Document
from backend.app.models.workflow import Workflow, WorkflowTriggerType
from backend.app.models.workflow_execution import ExecutionStatus, WorkflowExecution
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.extraction_repo import ExtractionRepository
from backend.app.repositories.workflow_repo import WorkflowExecutionRepository, WorkflowRepository
from backend.app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from backend.app.services.workflow_engine import (
    ConditionEvaluator,
    VariableSubstitutor,
    workflow_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
UTC = UTC


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow_repo = WorkflowRepository(db)
        self.execution_repo = WorkflowExecutionRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.extraction_repo = ExtractionRepository(db)

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    async def create_workflow(
        self, workspace_id: uuid.UUID, workflow_in: WorkflowCreate
    ) -> Workflow:
        """Create a new automation workflow."""
        workflow = Workflow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            name=workflow_in.name,
            description=workflow_in.description,
            is_active=workflow_in.is_active,
            trigger_type=workflow_in.trigger_type,
            conditions=workflow_in.conditions,
            actions=workflow_in.actions,
        )
        return await self.workflow_repo.create(workflow)

    async def get_workflow(self, workflow_id: uuid.UUID, workspace_id: uuid.UUID) -> Workflow:
        wf = await self.workflow_repo.get_by_id_and_workspace(workflow_id, workspace_id)
        if not wf:
            raise EntityNotFoundException("Workflow", workflow_id)
        return wf

    async def list_workflows(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[Workflow]:
        return await self.workflow_repo.list_by_workspace(workspace_id, skip=skip, limit=limit)

    async def update_workflow(
        self,
        workflow_id: uuid.UUID,
        workspace_id: uuid.UUID,
        update_in: WorkflowUpdate,
    ) -> Workflow:
        workflow = await self.get_workflow(workflow_id, workspace_id)
        if update_in.name is not None:
            workflow.name = update_in.name
        if update_in.description is not None:
            workflow.description = update_in.description
        if update_in.is_active is not None:
            workflow.is_active = update_in.is_active
        if update_in.trigger_type is not None:
            workflow.trigger_type = update_in.trigger_type
        if update_in.conditions is not None:
            workflow.conditions = update_in.conditions
        if update_in.actions is not None:
            workflow.actions = update_in.actions
        return await self.workflow_repo.update(workflow)

    async def delete_workflow(self, workflow_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        workflow = await self.get_workflow(workflow_id, workspace_id)
        await self.workflow_repo.delete(workflow)

    # -------------------------------------------------------------------------
    # Context Builder
    # -------------------------------------------------------------------------

    async def _build_document_context(
        self, workspace_id: uuid.UUID, document_id: uuid.UUID | None = None
    ) -> tuple[dict[str, Any], Document | None]:
        """Construct rich execution context from document and extracted fields."""
        context: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if not document_id:
            return context, None

        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            return context, None

        context.update(
            {
                "id": str(doc.id),
                "document_id": str(doc.id),
                "filename": doc.filename,
                "original_filename": doc.original_filename,
                "status": doc.status.value if doc.status else "uploaded",
                "document_type": doc.document_type.value if doc.document_type else "unknown",
                "confidence_score": doc.confidence_score or 0.0,
                "file_size": doc.file_size or 0,
                "mime_type": doc.mime_type or "",
                "metadata": doc.metadata_json or {},
            }
        )

        # Flatten metadata_json into context
        if doc.metadata_json and isinstance(doc.metadata_json, dict):
            for mk, mv in doc.metadata_json.items():
                if mk not in context:
                    context[mk] = mv

        # Load extracted fields
        fields = await self.extraction_repo.list_by_document(document_id, workspace_id)
        for f in fields:
            context[f.field_name] = {
                "value": f.field_value,
                "normalized_value": f.normalized_value,
                "confidence": f.confidence,
                "is_valid": f.is_valid,
            }
            context[f"field_{f.field_name}"] = f.normalized_value or f.field_value

        return context, doc

    # -------------------------------------------------------------------------
    # Execution Core
    # -------------------------------------------------------------------------

    async def trigger_execution(
        self,
        workflow_id: uuid.UUID,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
        custom_context: dict[str, Any] | None = None,
    ) -> WorkflowExecution:
        """Execute a workflow: condition evaluation → action steps → audit trail."""
        workflow = await self.get_workflow(workflow_id, workspace_id)
        if not workflow.is_active:
            raise ValidationException(f"Workflow '{workflow.name}' is inactive.")

        # Idempotency guard: skip if same document is already running
        if document_id:
            recent_runs = await self.execution_repo.list_by_workflow(
                workflow_id=workflow_id, workspace_id=workspace_id, skip=0, limit=5
            )
            for r in recent_runs:
                if r.document_id == document_id and r.status == ExecutionStatus.RUNNING:
                    logger.warning("Duplicate execution for document %s — skipping.", document_id)
                    return r

        trigger_name = (
            workflow.trigger_type.value
            if hasattr(workflow.trigger_type, "value")
            else str(workflow.trigger_type)
        )

        # Create execution record
        execution = WorkflowExecution(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            workspace_id=workspace_id,
            document_id=document_id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(UTC),
            execution_logs=[
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": "INFO",
                    "message": f"Execution started: '{workflow.name}' (trigger={trigger_name})",
                }
            ],
        )
        execution = await self.execution_repo.create(execution)
        logs: list[dict[str, Any]] = list(execution.execution_logs)

        try:
            # Build context
            context, doc = await self._build_document_context(workspace_id, document_id)
            if custom_context:
                context.update(custom_context)

            logs.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": "INFO",
                    "message": f"Context built. document_id={document_id}, context_keys={len(context)}",
                }
            )

            # Evaluate conditions
            condition_passed, eval_msg = ConditionEvaluator.evaluate(context, workflow.conditions)
            logs.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": "INFO",
                    "message": f"Condition eval: {eval_msg} -> passed={condition_passed}",
                }
            )

            # Pick branch
            if condition_passed:
                actions_to_run: list[dict[str, Any]] = workflow.actions or []
            else:
                else_actions = (workflow.conditions or {}).get("else_actions", [])
                actions_to_run = else_actions
                if not actions_to_run:
                    logs.append(
                        {
                            "timestamp": datetime.now(UTC).isoformat(),
                            "level": "INFO",
                            "message": "Condition False and no else_actions — workflow completed without actions.",
                        }
                    )

            # Execute each action step
            execution_failed = False
            step_errors: list[str] = []

            for idx, act in enumerate(actions_to_run, 1):
                act_res = await workflow_engine.execute_action(act, context, doc)
                step_status = act_res.get("status", "COMPLETED")

                logs.append(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "level": "INFO" if step_status == "COMPLETED" else "ERROR",
                        "message": f"Step {idx} [{act_res.get('action_type')}] '{act_res.get('step_name')}': {step_status}",
                        "details": act_res,
                    }
                )

                if step_status == "FAILED":
                    execution_failed = True
                    step_errors.append(
                        f"Step {idx} ({act_res.get('step_name')}) failed: {act_res.get('error')}"
                    )
                    # Continue remaining steps even on one failure

            # Persist document changes made by action handlers
            if doc:
                await self.doc_repo.update(doc)
                await self.db.commit()

            execution.completed_at = datetime.now(UTC)
            execution.status = (
                ExecutionStatus.FAILED if execution_failed else ExecutionStatus.COMPLETED
            )
            if step_errors:
                execution.error_message = "; ".join(step_errors)

            started_at = execution.started_at
            completed_at = execution.completed_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=UTC)
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            logs.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": "INFO" if not execution_failed else "ERROR",
                    "message": f"Execution {'completed' if not execution_failed else 'finished with errors'} in {duration_ms}ms. Steps run: {len(actions_to_run)}.",
                }
            )

        except Exception as exc:
            logger.error("Unhandled error in workflow '%s': %s", workflow.name, exc, exc_info=True)
            logs.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": "ERROR",
                    "message": f"Unhandled exception: {str(exc)}",
                }
            )
            execution.completed_at = datetime.now(UTC)
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(exc)

        execution.execution_logs = logs
        updated_exec = await self.execution_repo.update(execution)
        await self.db.commit()
        return updated_exec

    # -------------------------------------------------------------------------
    # Get single execution
    # -------------------------------------------------------------------------

    async def get_execution(
        self, execution_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkflowExecution:
        """Fetch a single execution record by ID."""
        ex = await self.execution_repo.get_by_id_and_workspace(execution_id, workspace_id)
        if not ex:
            raise EntityNotFoundException("WorkflowExecution", execution_id)
        return ex

    # -------------------------------------------------------------------------
    # Retry
    # -------------------------------------------------------------------------

    async def retry_execution(
        self, execution_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkflowExecution:
        """Retry a FAILED or CANCELLED execution."""
        old_exec = await self.execution_repo.get_by_id_and_workspace(execution_id, workspace_id)
        if not old_exec:
            raise EntityNotFoundException("WorkflowExecution", execution_id)
        if old_exec.status not in (ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            raise ValidationException(
                f"Only FAILED or CANCELLED executions can be retried. Current: {old_exec.status.value}"
            )
        return await self.trigger_execution(
            workflow_id=old_exec.workflow_id,
            workspace_id=workspace_id,
            document_id=old_exec.document_id,
        )

    # -------------------------------------------------------------------------
    # Test / Dry-run
    # -------------------------------------------------------------------------

    async def test_workflow(
        self,
        workflow_id: uuid.UUID,
        workspace_id: uuid.UUID,
        test_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Dry-run: evaluate conditions, show simulated steps — zero side effects."""
        workflow = await self.get_workflow(workflow_id, workspace_id)
        condition_passed, eval_msg = ConditionEvaluator.evaluate(test_context, workflow.conditions)

        actions_to_run = (
            workflow.actions
            if condition_passed
            else (workflow.conditions or {}).get("else_actions", [])
        )

        simulated_steps = []
        for idx, act in enumerate(actions_to_run, 1):
            substituted_params = VariableSubstitutor.substitute_data(
                act.get("params", {}), test_context
            )
            simulated_steps.append(
                {
                    "step_index": idx,
                    "action_type": act.get("type"),
                    "name": act.get("name"),
                    "substituted_params": substituted_params,
                }
            )

        return {
            "workflow_id": str(workflow.id),
            "workflow_name": workflow.name,
            "trigger_type": workflow.trigger_type.value
            if hasattr(workflow.trigger_type, "value")
            else str(workflow.trigger_type),
            "is_active": workflow.is_active,
            "condition_evaluated": condition_passed,
            "evaluation_message": eval_msg,
            "branch": "main" if condition_passed else "else",
            "actions_to_execute_count": len(actions_to_run),
            "simulated_steps": simulated_steps,
        }

    # -------------------------------------------------------------------------
    # List Executions + Stats
    # -------------------------------------------------------------------------

    async def list_executions(
        self,
        workflow_id: uuid.UUID,
        workspace_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[WorkflowExecution]:
        return await self.execution_repo.list_by_workflow(
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )

    async def get_execution_stats(
        self, workflow_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> dict[str, Any]:
        """Return aggregated success rate, avg duration, and status breakdown."""
        executions = await self.execution_repo.list_by_workflow(
            workflow_id=workflow_id, workspace_id=workspace_id, skip=0, limit=1000
        )
        total = len(executions)
        if total == 0:
            return {
                "workflow_id": str(workflow_id),
                "total_executions": 0,
                "completed": 0,
                "failed": 0,
                "running": 0,
                "cancelled": 0,
                "success_rate_pct": 0.0,
                "avg_duration_ms": 0.0,
                "status_breakdown": {},
            }

        status_counts: dict[str, int] = {}
        durations: list[float] = []

        for ex in executions:
            sk = ex.status.value if hasattr(ex.status, "value") else str(ex.status)
            status_counts[sk] = status_counts.get(sk, 0) + 1
            if ex.started_at and ex.completed_at:
                durations.append((ex.completed_at - ex.started_at).total_seconds() * 1000)

        completed = status_counts.get("COMPLETED", 0)
        success_rate = round((completed / total) * 100, 2) if total > 0 else 0.0
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

        return {
            "workflow_id": str(workflow_id),
            "total_executions": total,
            "completed": completed,
            "failed": status_counts.get("FAILED", 0),
            "running": status_counts.get("RUNNING", 0),
            "cancelled": status_counts.get("CANCELLED", 0),
            "success_rate_pct": success_rate,
            "avg_duration_ms": avg_duration,
            "status_breakdown": status_counts,
        }

    # -------------------------------------------------------------------------
    # Event-driven: Execute Matching Workflows
    # -------------------------------------------------------------------------

    async def execute_matching_workflows(
        self,
        workspace_id: uuid.UUID,
        trigger_type: WorkflowTriggerType | str,
        document_id: uuid.UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[WorkflowExecution]:
        """Find all active workflows matching trigger_type and execute them."""
        trigger_val = trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type)
        matching_wfs = await self.workflow_repo.list_by_trigger_type(
            workspace_id=workspace_id,
            trigger_type=trigger_val,
            is_active=True,
        )
        logger.info(
            "Found %d active workflows for trigger '%s' (ws=%s, doc=%s)",
            len(matching_wfs),
            trigger_val,
            workspace_id,
            document_id,
        )

        executions: list[WorkflowExecution] = []
        for wf in matching_wfs:
            try:
                exec_run = await self.trigger_execution(
                    workflow_id=wf.id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    custom_context=context,
                )
                executions.append(exec_run)
            except Exception as err:
                logger.error(
                    "Error executing workflow '%s' (%s): %s", wf.name, wf.id, err, exc_info=True
                )

        return executions

    # -------------------------------------------------------------------------
    # Scheduled trigger: fire all SCHEDULED workflows
    # -------------------------------------------------------------------------

    async def fire_scheduled_workflows(
        self,
        workspace_id: uuid.UUID,
        background_tasks: Any | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fire all active SCHEDULED workflows for a workspace.
        Called by a cron job / APScheduler endpoint.
        Returns a summary of each dispatched execution.
        """
        matching_wfs = await self.workflow_repo.list_by_trigger_type(
            workspace_id=workspace_id,
            trigger_type=WorkflowTriggerType.SCHEDULED,
            is_active=True,
        )
        logger.info(
            "Firing %d SCHEDULED workflows for workspace %s", len(matching_wfs), workspace_id
        )

        results: list[dict[str, Any]] = []
        for wf in matching_wfs:
            try:
                result = await self.dispatch_workflow_async(
                    workflow_id=wf.id,
                    workspace_id=workspace_id,
                    document_id=None,
                    custom_context={
                        "trigger": "SCHEDULED",
                        "fired_at": datetime.now(UTC).isoformat(),
                    },
                    background_tasks=background_tasks,
                )
                results.append({"workflow_id": str(wf.id), "workflow_name": wf.name, **result})
            except Exception as err:
                logger.error("Scheduled workflow '%s' dispatch failed: %s", wf.name, err)
                results.append(
                    {
                        "workflow_id": str(wf.id),
                        "workflow_name": wf.name,
                        "status": "ERROR",
                        "error": str(err),
                    }
                )

        return results

    # -------------------------------------------------------------------------
    # Bulk Execute
    # -------------------------------------------------------------------------

    async def bulk_execute_workflows(
        self,
        workspace_id: uuid.UUID,
        workflow_ids: list[uuid.UUID],
        document_id: uuid.UUID | None = None,
        custom_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute multiple specified workflows and return a per-workflow summary."""
        results: list[dict[str, Any]] = []
        for wf_id in workflow_ids:
            try:
                exec_run = await self.trigger_execution(
                    workflow_id=wf_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    custom_context=custom_context,
                )
                results.append(
                    {
                        "workflow_id": str(wf_id),
                        "execution_id": str(exec_run.id),
                        "status": exec_run.status.value,
                        "error": exec_run.error_message,
                    }
                )
            except Exception as err:
                results.append(
                    {
                        "workflow_id": str(wf_id),
                        "execution_id": None,
                        "status": "ERROR",
                        "error": str(err),
                    }
                )
        return results

    # -------------------------------------------------------------------------
    # Async / Celery Dispatch
    # -------------------------------------------------------------------------

    async def dispatch_workflow_async(
        self,
        workflow_id: uuid.UUID,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
        custom_context: dict[str, Any] | None = None,
        background_tasks: Any | None = None,
    ) -> dict[str, Any]:
        """Dual-mode dispatcher: Celery if available, BackgroundTasks / direct fallback."""
        celery_dispatched = False
        try:
            from backend.app.workers.tasks import execute_workflow_task

            execute_workflow_task.apply_async(
                args=[
                    str(workflow_id),
                    str(workspace_id),
                    str(document_id) if document_id else None,
                    custom_context,
                ],
                retry=False,
            )
            celery_dispatched = True
            logger.info("Workflow %s queued via Celery.", workflow_id)
        except Exception as e:
            logger.info("Celery unavailable (%s); using fallback.", e)

        if not celery_dispatched:
            if background_tasks is not None:
                from backend.app.workers.tasks import async_execute_workflow

                background_tasks.add_task(
                    async_execute_workflow,
                    workflow_id=str(workflow_id),
                    workspace_id=str(workspace_id),
                    document_id=str(document_id) if document_id else None,
                    custom_context=custom_context,
                )
                return {"status": "queued_background", "workflow_id": str(workflow_id)}
            else:
                exec_res = await self.trigger_execution(
                    workflow_id=workflow_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    custom_context=custom_context,
                )
                return {"status": exec_res.status.value, "execution_id": str(exec_res.id)}

        return {"status": "queued_celery", "workflow_id": str(workflow_id)}
