import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from backend.app.core.exceptions import EntityNotFoundException
from backend.app.db.database import AsyncSessionLocal
from backend.app.models.document import DocumentStatus
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.services.ocr_service import ocr_service
from backend.app.services.storage_service import storage_service
from backend.app.workers.celery_app import celery_app
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Global session factory that can be swapped in testing environments
_SESSION_FACTORY: Callable[[], Any] = AsyncSessionLocal


def get_session_factory() -> Callable[[], Any]:
    return _SESSION_FACTORY


def set_session_factory(factory: Callable[[], Any]) -> None:
    global _SESSION_FACTORY
    _SESSION_FACTORY = factory


async def _execute_pipeline_on_db(
    db: AsyncSession,
    document_id: str,
    workspace_id: str,
    task_id: str,
    force_reprocess: bool = False,
) -> dict[str, Any]:
    """Inner core pipeline executor against an active database session."""
    doc_uuid = uuid.UUID(document_id)
    ws_uuid = uuid.UUID(workspace_id)
    repo = DocumentRepository(db)

    doc = await repo.get_by_id_and_workspace(doc_uuid, ws_uuid)
    if not doc:
        raise EntityNotFoundException("Document", doc_uuid)

    # Idempotency checks: do not duplicate active or finished jobs unless forced
    if not force_reprocess:
        if doc.status == DocumentStatus.PROCESSING:
            logger.info(
                "Document %s is already processing. Skipping task %s (idempotent).",
                document_id,
                task_id,
            )
            return {
                "document_id": document_id,
                "status": "already_processing",
                "idempotent_skip": True,
            }
        if doc.status == DocumentStatus.COMPLETED:
            logger.info(
                "Document %s is already completed. Skipping task %s (idempotent).",
                document_id,
                task_id,
            )
            return {
                "document_id": document_id,
                "status": "already_completed",
                "idempotent_skip": True,
            }

    # Transition status to processing
    doc.status = DocumentStatus.PROCESSING
    doc.processing_error = None
    if not doc.metadata_json:
        doc.metadata_json = {}
    doc.metadata_json["last_task_id"] = task_id
    await repo.update(doc)
    await db.commit()

    try:
        # 1. Load document bytes from storage
        file_bytes = await storage_service.read_file(doc.file_path)

        # 2. Determine extension
        ext = (
            doc.original_filename.split(".")[-1].lower() if "." in doc.original_filename else "pdf"
        )

        # 3. Execute image preprocessing & OCR off the event loop. Tesseract,
        # OpenCV and PDF rasterization are blocking CPU/process operations; if
        # run inline, Starlette cannot answer status/extraction requests while
        # an upload is being ingested.
        ocr_result = await asyncio.to_thread(
            ocr_service.process_document,
            file_bytes=file_bytes,
            extension=ext,
        )

        # 4. Check confidence & empty text
        is_empty = ocr_result.get("statistics", {}).get("is_empty", False)
        mean_conf = ocr_result.get("overall_confidence", 0.0)

        doc.confidence_score = mean_conf
        metadata = dict(doc.metadata_json or {})
        metadata["ocr_result"] = ocr_result
        metadata["ocr_statistics"] = ocr_result.get("statistics", {})
        metadata["total_pages"] = ocr_result.get("total_pages", 1)
        doc.metadata_json = metadata

        # 5. Document Classification & Structured Extraction
        if not is_empty and ocr_result.get("full_text"):
            from backend.app.services.extraction_service import ExtractionService

            ext_service = ExtractionService(db)
            extraction_res = await ext_service.classify_and_extract_document(
                document_id=doc_uuid,
                workspace_id=ws_uuid,
                ocr_text=ocr_result.get("full_text", ""),
            )
            if extraction_res.overall_confidence > 0.0:
                mean_conf = extraction_res.overall_confidence
            await db.refresh(doc)
        else:
            if is_empty or mean_conf < 0.40:
                doc.status = DocumentStatus.REVIEW_REQUIRED
            else:
                doc.status = DocumentStatus.COMPLETED

            await repo.update(doc)
            await db.commit()

            try:
                from backend.app.models.workflow import WorkflowTriggerType
                from backend.app.services.workflow_service import WorkflowService

                wf_service = WorkflowService(db)
                await wf_service.execute_matching_workflows(
                    workspace_id=ws_uuid,
                    trigger_type=WorkflowTriggerType.ON_DOCUMENT_EXTRACTED,
                    document_id=doc_uuid,
                )
                if doc.status == DocumentStatus.REVIEW_REQUIRED:
                    await wf_service.execute_matching_workflows(
                        workspace_id=ws_uuid,
                        trigger_type=WorkflowTriggerType.ON_LOW_CONFIDENCE,
                        document_id=doc_uuid,
                    )
            except Exception as wf_err:
                logger.warning("Workflow dispatch on raw task completion warning: %s", wf_err)

        logger.info(
            "Document %s processed successfully with status %s (confidence: %.2f)",
            document_id,
            doc.status,
            mean_conf,
        )
        return {
            "document_id": document_id,
            "status": doc.status.value,
            "confidence_score": mean_conf,
            "total_pages": ocr_result.get("total_pages", 1),
        }

    except Exception as err:
        logger.error("Error processing document %s: %s", document_id, err, exc_info=True)
        try:
            await db.rollback()
            err_doc = await repo.get_by_id_and_workspace(doc_uuid, ws_uuid)
            if err_doc:
                err_doc.status = DocumentStatus.FAILED
                err_doc.processing_error = str(err)
                await repo.update(err_doc)
                await db.commit()
        except Exception as rollback_err:
            logger.error("Failed to persist document FAILED status on rollback: %s", rollback_err)
        raise err


async def async_process_document(
    document_id: str,
    workspace_id: str,
    task_id: str,
    force_reprocess: bool = False,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Async execution wrapper for document processing pipeline."""
    if db is not None:
        return await _execute_pipeline_on_db(
            db=db,
            document_id=document_id,
            workspace_id=workspace_id,
            task_id=task_id,
            force_reprocess=force_reprocess,
        )

    session_factory = get_session_factory()
    async with session_factory() as session:
        return await _execute_pipeline_on_db(
            db=session,
            document_id=document_id,
            workspace_id=workspace_id,
            task_id=task_id,
            force_reprocess=force_reprocess,
        )


async def _execute_workflow_on_db(
    db: AsyncSession,
    workflow_id: str,
    workspace_id: str,
    document_id: str | None = None,
    custom_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inner core workflow executor against an active database session."""
    from backend.app.services.workflow_service import WorkflowService

    wf_service = WorkflowService(db)
    wf_uuid = uuid.UUID(workflow_id)
    ws_uuid = uuid.UUID(workspace_id)
    doc_uuid = uuid.UUID(document_id) if document_id else None

    execution = await wf_service.trigger_execution(
        workflow_id=wf_uuid,
        workspace_id=ws_uuid,
        document_id=doc_uuid,
        custom_context=custom_context,
    )
    return {
        "execution_id": str(execution.id),
        "status": execution.status.value,
        "workflow_id": workflow_id,
        "error_message": execution.error_message,
    }


async def async_execute_workflow(
    workflow_id: str,
    workspace_id: str,
    document_id: str | None = None,
    custom_context: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Async execution wrapper for workflow runner."""
    if db is not None:
        return await _execute_workflow_on_db(
            db=db,
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            document_id=document_id,
            custom_context=custom_context,
        )

    session_factory = get_session_factory()
    async with session_factory() as session:
        return await _execute_workflow_on_db(
            db=session,
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            document_id=document_id,
            custom_context=custom_context,
        )


class DocumentProcessingTask(Task):
    """Custom task with exponential backoff retry and failure hooks."""

    autoretry_for = (ConnectionError, TimeoutError)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=DocumentProcessingTask,
    name="app.workers.tasks.process_document_task",
    acks_late=True,
)
def process_document_task(
    self: Task,
    document_id: str,
    workspace_id: str,
    force_reprocess: bool = False,
) -> dict[str, Any]:
    """Celery background task for end-to-end document processing."""
    task_id = self.request.id or str(uuid.uuid4())
    logger.info(
        "Starting document processing task %s for doc=%s, workspace=%s (force=%s)",
        task_id,
        document_id,
        workspace_id,
        force_reprocess,
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(
            async_process_document(
                document_id=document_id,
                workspace_id=workspace_id,
                task_id=task_id,
                force_reprocess=force_reprocess,
            )
        )
        return {"status": "queued", "document_id": document_id}
    else:
        return asyncio.run(
            async_process_document(
                document_id=document_id,
                workspace_id=workspace_id,
                task_id=task_id,
                force_reprocess=force_reprocess,
            )
        )


@celery_app.task(
    bind=True,
    base=DocumentProcessingTask,
    name="app.workers.tasks.execute_workflow_task",
    acks_late=True,
)
def execute_workflow_task(
    self: Task,
    workflow_id: str,
    workspace_id: str,
    document_id: str | None = None,
    custom_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Celery background task for automated workflow execution."""
    task_id = self.request.id or str(uuid.uuid4())
    logger.info(
        "Starting workflow task %s for wf=%s, ws=%s, doc=%s",
        task_id,
        workflow_id,
        workspace_id,
        document_id,
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(
            async_execute_workflow(
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                document_id=document_id,
                custom_context=custom_context,
            )
        )
        return {"status": "queued", "workflow_id": workflow_id}
    else:
        return asyncio.run(
            async_execute_workflow(
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                document_id=document_id,
                custom_context=custom_context,
            )
        )
