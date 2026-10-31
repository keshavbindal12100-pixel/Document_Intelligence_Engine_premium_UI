import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from backend.app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
)
from backend.app.models.audit_log import AuditLog
from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.schemas.analytics import BatchDocumentUploadResponse, BatchUploadItemResult
from backend.app.schemas.document import DocumentFilter, DocumentResponse, DocumentUpdate
from backend.app.services.storage_service import storage_service
from backend.app.utils.file_validators import (
    calculate_sha256,
    sanitize_filename,
    validate_file_metadata,
)
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.audit_repo = AuditRepository(db)

    async def upload_document(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
        document_type: DocumentType = DocumentType.UNKNOWN,
        template_id: uuid.UUID | None = None,
        metadata_json: dict[str, Any] | None = None,
        background_tasks: Any | None = None,
    ) -> Document:
        """Process file upload: validate, hash, persist to disk and DB, create audit log and queue."""
        content = await file.read()
        file_size = len(content)

        sanitized_name = sanitize_filename(file.filename or "document")

        # Validate extension, size, mime, and magic byte signatures
        ext = validate_file_metadata(
            filename=sanitized_name,
            file_size=file_size,
            file_bytes=content,
            content_type=file.content_type,
        )

        sha256_hash = calculate_sha256(content)

        # Save to workspace-isolated storage
        saved_filename, saved_filepath = await storage_service.save_file(
            workspace_id=workspace_id,
            file_bytes=content,
            extension=ext,
        )

        document = Document(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            uploaded_by_id=user_id,
            filename=saved_filename,
            original_filename=sanitized_name,
            file_path=saved_filepath,
            file_size=file_size,
            mime_type=file.content_type or f"application/{ext}",
            sha256_hash=sha256_hash,
            document_type=document_type,
            status=DocumentStatus.UPLOADED,
            template_id=template_id,
            metadata_json=metadata_json or {},
        )

        created_doc = await self.doc_repo.create(document)

        # Create audit log
        audit_entry = AuditLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            action="DOCUMENT_UPLOADED",
            entity_type="DOCUMENT",
            entity_id=str(created_doc.id),
            changes={
                "filename": created_doc.original_filename,
                "file_size": created_doc.file_size,
                "mime_type": created_doc.mime_type,
                "sha256": created_doc.sha256_hash,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        await self.audit_repo.create(audit_entry)
        # The ingestion worker uses a separate DB session; commit the upload
        # before dispatch so it can see the document row reliably.
        await self.db.commit()

        # Dispatch Celery worker task asynchronously with fast failover
        celery_success = False
        try:
            from backend.app.workers.celery_app import has_active_worker
            from backend.app.workers.tasks import process_document_task

            if has_active_worker():
                process_document_task.apply_async(
                    args=[str(created_doc.id), str(workspace_id)], retry=False
                )
                celery_success = True
            else:
                logger.info(
                    "No live Celery worker; using local OCR fallback for document %s",
                    created_doc.id,
                )
        except Exception as e:
            logger.info(
                "Celery async dispatch skipped/offline (%s); fallback available on demand.", e
            )

        if not celery_success and background_tasks is not None:
            from backend.app.workers.tasks import async_process_document

            background_tasks.add_task(
                async_process_document,
                document_id=str(created_doc.id),
                workspace_id=str(workspace_id),
                task_id=f"fallback_{uuid.uuid4().hex[:8]}",
            )

        # Fire ON_DOCUMENT_UPLOADED workflows (event-driven automation)
        try:
            from backend.app.models.workflow import WorkflowTriggerType
            from backend.app.services.workflow_service import WorkflowService

            wf_service = WorkflowService(self.db)
            await wf_service.execute_matching_workflows(
                workspace_id=workspace_id,
                trigger_type=WorkflowTriggerType.ON_DOCUMENT_UPLOADED,
                document_id=created_doc.id,
            )
        except Exception as wf_err:
            logger.info("Workflow trigger on upload skipped: %s", wf_err)

        return created_doc

    async def upload_document_any_format(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
        document_type: DocumentType = DocumentType.UNKNOWN,
        template_id: uuid.UUID | None = None,
        metadata_json: dict[str, Any] | None = None,
        background_tasks: Any | None = None,
    ) -> Document:
        """Upload a file of ANY format (no extension/MIME/magic-byte restriction).

        Filename sanitization and the max file size limit are still enforced,
        so this stays safe while allowing formats outside ALLOWED_EXTENSIONS
        (e.g. .docx, .txt, .csv, .xlsx, etc.), in addition to PDFs and images.
        """
        try:
            content = await file.read()
            file_size = len(content)

            sanitized_name = sanitize_filename(file.filename or "document")

            # Validate size/filename only; skip format restrictions.
            ext = validate_file_metadata(
                filename=sanitized_name,
                file_size=file_size,
                file_bytes=content,
                content_type=file.content_type,
                allow_any_format=True,
            )

            sha256_hash = calculate_sha256(content)

            saved_filename, saved_filepath = await storage_service.save_file(
                workspace_id=workspace_id,
                file_bytes=content,
                extension=ext,
            )

            document = Document(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                uploaded_by_id=user_id,
                filename=saved_filename,
                original_filename=sanitized_name,
                file_path=saved_filepath,
                file_size=file_size,
                mime_type=file.content_type or f"application/{ext}",
                sha256_hash=sha256_hash,
                document_type=document_type,
                status=DocumentStatus.UPLOADED,
                template_id=template_id,
                metadata_json=metadata_json or {},
            )

            created_doc = await self.doc_repo.create(document)

            audit_entry = AuditLog(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                user_id=user_id,
                action="DOCUMENT_UPLOADED",
                entity_type="DOCUMENT",
                entity_id=str(created_doc.id),
                changes={
                    "filename": created_doc.original_filename,
                    "file_size": created_doc.file_size,
                    "mime_type": created_doc.mime_type,
                    "sha256": created_doc.sha256_hash,
                    "upload_mode": "any_format",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            await self.audit_repo.create(audit_entry)
            await self.db.commit()

            celery_success = False
            try:
                from backend.app.workers.celery_app import has_active_worker
                from backend.app.workers.tasks import process_document_task

                if has_active_worker():
                    process_document_task.apply_async(
                        args=[str(created_doc.id), str(workspace_id)], retry=False
                    )
                    celery_success = True
                else:
                    logger.info(
                        "No live Celery worker; using local OCR fallback for document %s",
                        created_doc.id,
                    )
            except Exception as e:
                logger.info(
                    "Celery async dispatch skipped/offline (%s); fallback available on demand.", e
                )

            if not celery_success and background_tasks is not None:
                from backend.app.workers.tasks import async_process_document

                background_tasks.add_task(
                    async_process_document,
                    document_id=str(created_doc.id),
                    workspace_id=str(workspace_id),
                    task_id=f"fallback_{uuid.uuid4().hex[:8]}",
                )

            return created_doc
        except ValidationException:
            # Re-raise validation errors (bad filename, empty file, too large)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during any-format upload: {e}")
            raise ValidationException(
                "Could not process the uploaded file. Please try again."
            ) from e

    async def batch_upload_documents(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        files: list[UploadFile],
        background_tasks: Any | None = None,
    ) -> BatchDocumentUploadResponse:
        """Batch upload multiple documents asynchronously with partial failure resilience."""
        items: list[BatchUploadItemResult] = []
        created_docs: list[DocumentResponse] = []

        for file in files:
            orig_name = file.filename or "unknown_file"
            try:
                doc = await self.upload_document(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    file=file,
                    background_tasks=background_tasks,
                )
                items.append(
                    BatchUploadItemResult(
                        filename=orig_name,
                        document_id=doc.id,
                        status="queued",
                        error=None,
                    )
                )
                created_docs.append(DocumentResponse.model_validate(doc))
            except Exception as exc:
                logger.warning("Batch upload failed for file %s: %s", orig_name, str(exc))
                items.append(
                    BatchUploadItemResult(
                        filename=orig_name,
                        document_id=None,
                        status="failed",
                        error=str(exc),
                    )
                )

        successful_count = len(created_docs)
        failed_count = len(files) - successful_count

        return BatchDocumentUploadResponse(
            total_uploaded=successful_count,
            successful_count=successful_count,
            failed_count=failed_count,
            items=items,
        )

    async def get_document(self, document_id: uuid.UUID, workspace_id: uuid.UUID) -> Document:
        """Fetch document by ID with workspace isolation."""
        doc = await self.doc_repo.get_by_id_and_workspace(document_id, workspace_id)
        if not doc:
            raise EntityNotFoundException("Document", document_id)
        return doc

    async def list_documents(
        self, workspace_id: uuid.UUID, filters: DocumentFilter
    ) -> tuple[Sequence[Document], int]:
        """List documents matching multiple filters, date ranges, confidence, and sorting."""
        skip = (filters.page - 1) * filters.page_size
        return await self.doc_repo.list_filtered(
            workspace_id=workspace_id,
            status=filters.status,
            document_type=filters.document_type,
            search=filters.search,
            min_confidence=filters.min_confidence,
            max_confidence=filters.max_confidence,
            upload_date_from=filters.upload_date_from,
            upload_date_to=filters.upload_date_to,
            vendor=filters.vendor,
            invoice_number=filters.invoice_number,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
            skip=skip,
            limit=filters.page_size,
        )

    async def update_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        update_in: DocumentUpdate,
    ) -> Document:
        """Update document metadata or status."""
        doc = await self.get_document(document_id, workspace_id)
        if update_in.document_type is not None:
            doc.document_type = update_in.document_type
        if update_in.status is not None:
            doc.status = update_in.status
        if update_in.template_id is not None:
            doc.template_id = update_in.template_id
        if update_in.metadata_json is not None:
            doc.metadata_json = update_in.metadata_json
        return await self.doc_repo.update(doc)

    async def delete_document(self, document_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        """Delete document from database and disk storage."""
        doc = await self.get_document(document_id, workspace_id)
        await storage_service.delete_file(doc.file_path)
        await self.doc_repo.delete(doc)

    async def get_document_file_bytes(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> tuple[bytes, str, str]:
        """Get document raw bytes, original filename, and mime type for download."""
        doc = await self.get_document(document_id, workspace_id)
        file_bytes = await storage_service.read_file(doc.file_path)
        return file_bytes, doc.original_filename, doc.mime_type

    async def get_document_audit_logs(
        self, document_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Sequence[AuditLog]:
        """Fetch complete audit history trail for a single document."""
        await self.get_document(document_id, workspace_id)
        items, _ = await self.audit_repo.list_filtered(
            workspace_id=workspace_id,
            entity_id=str(document_id),
            skip=0,
            limit=100,
        )
        return items

    async def trigger_processing(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        force_reprocess: bool = False,
        background_tasks: Any | None = None,
    ) -> Document:
        """Enqueue document for asynchronous OCR processing with Celery and local fallback."""
        doc = await self.get_document(document_id, workspace_id)

        if not force_reprocess:
            if doc.status in (DocumentStatus.PROCESSING, DocumentStatus.COMPLETED):
                return doc

        doc.status = DocumentStatus.QUEUED
        await self.doc_repo.update(doc)

        from backend.app.workers.celery_app import has_active_worker
        from backend.app.workers.tasks import async_process_document, process_document_task

        if not doc.metadata_json:
            doc.metadata_json = {}

        celery_success = False
        try:
            if has_active_worker():
                task = process_document_task.apply_async(
                    args=[str(doc.id), str(workspace_id)],
                    kwargs={"force_reprocess": force_reprocess},
                    retry=False,
                )
                doc.metadata_json["task_id"] = task.id
                celery_success = True
            else:
                logger.info(
                    "No live Celery worker; using local in-process / background task fallback."
                )
                doc.metadata_json["task_id"] = f"fallback_{uuid.uuid4().hex[:8]}"
        except Exception as e:
            logger.info(
                "Celery broker offline (%s); using local in-process / background task fallback.", e
            )
            doc.metadata_json["task_id"] = f"fallback_{uuid.uuid4().hex[:8]}"

        doc = await self.doc_repo.update(doc)
        await self.db.commit()

        if not celery_success:
            task_id = doc.metadata_json.get("task_id", str(uuid.uuid4()))
            if background_tasks is not None:
                background_tasks.add_task(
                    async_process_document,
                    document_id=str(doc.id),
                    workspace_id=str(workspace_id),
                    task_id=task_id,
                    force_reprocess=force_reprocess,
                )
            else:
                try:
                    await async_process_document(
                        document_id=str(doc.id),
                        workspace_id=str(workspace_id),
                        task_id=task_id,
                        force_reprocess=force_reprocess,
                        db=self.db,
                    )
                except Exception as fallback_err:
                    logger.warning(
                        "In-process fallback execution encountered error: %s", fallback_err
                    )
                await self.db.refresh(doc)

        return doc

    async def trigger_reprocessing(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        background_tasks: Any | None = None,
    ) -> Document:
        """Force reprocessing of an existing document."""
        return await self.trigger_processing(
            document_id=document_id,
            workspace_id=workspace_id,
            force_reprocess=True,
            background_tasks=background_tasks,
        )

    async def export_documents_csv(self, workspace_id: uuid.UUID) -> str:
        """Export workspace documents metadata and extraction summary to CSV format."""
        import csv
        import io

        filters = DocumentFilter(page=1, page_size=1000)
        items, _ = await self.list_documents(workspace_id, filters)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "filename",
                "document_type",
                "status",
                "confidence_score",
                "created_at",
                "file_size",
            ]
        )
        for doc in items:
            writer.writerow(
                [
                    str(doc.id),
                    doc.original_filename,
                    doc.document_type.value
                    if hasattr(doc.document_type, "value")
                    else str(doc.document_type),
                    doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                    f"{doc.confidence_score:.2f}" if doc.confidence_score is not None else "",
                    doc.created_at.isoformat() if doc.created_at else "",
                    doc.file_size,
                ]
            )
        return output.getvalue()
