import io
import uuid

import pypdfium2
import pytest
from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.models.workflow import Workflow, WorkflowTriggerType
from backend.app.models.workflow_execution import ExecutionStatus
from backend.app.models.workspace import Workspace
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.workflow_repo import WorkflowExecutionRepository
from backend.app.schemas.extraction import DocumentApprovalRequest, DocumentRejectionRequest
from backend.app.services.extraction_service import ExtractionService
from backend.app.services.storage_service import storage_service
from backend.app.services.workflow_service import WorkflowService
from backend.app.workers.tasks import async_process_document
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def sample_test_invoice_doc(
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> Document:
    """Create a sample invoice document in the test database."""
    pdf = pypdfium2.PdfDocument.new()
    pdf.new_page(width=200, height=200)
    buf = io.BytesIO()
    pdf.save(buf)
    content = buf.getvalue()

    saved_name, file_path = await storage_service.save_file(
        workspace_id=test_workspace.id,
        file_bytes=content,
        extension="pdf",
    )

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        filename=saved_name,
        original_filename="sample_lifecycle_invoice.pdf",
        file_path=file_path,
        file_size=len(content),
        mime_type="application/pdf",
        sha256_hash=f"hash_{uuid.uuid4().hex}",
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.QUEUED,
        metadata_json={
            "total": 1250.00,
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-2026-001",
        },
    )
    repo = DocumentRepository(db_session)
    created = await repo.create(doc)
    await db_session.commit()
    return created


@pytest.mark.asyncio
async def test_on_document_extracted_trigger(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_test_invoice_doc: Document,
):
    """Verify ON_DOCUMENT_EXTRACTED workflow triggers automatically after OCR extraction."""
    wf_service = WorkflowService(db_session)

    # 1. Create ON_DOCUMENT_EXTRACTED workflow with condition matching
    wf = await wf_service.create_workflow(
        workspace_id=test_workspace.id,
        workflow_in=Workflow(
            name="Auto Notify on Extraction",
            trigger_type=WorkflowTriggerType.ON_DOCUMENT_EXTRACTED,
            is_active=True,
            conditions={"field": "total", "operator": ">=", "value": 1000},
            actions=[
                {
                    "type": "NOTIFICATION",
                    "name": "Extraction Complete Notification",
                    "params": {
                        "channel": "finance",
                        "message": "High value invoice {{invoice_number}} extracted: {{total}}",
                    },
                }
            ],
        ),
    )

    # 2. Perform classification & extraction
    ext_service = ExtractionService(db_session)
    ocr_text = "TAX INVOICE INV-2026-001\nVendor: Acme Corp\nSubtotal: 1000.00\nTax: 250.00\nTotal: 1250.00"
    await ext_service.classify_and_extract_document(
        document_id=sample_test_invoice_doc.id,
        workspace_id=test_workspace.id,
        ocr_text=ocr_text,
    )

    # 3. Verify workflow execution was created and completed
    exec_repo = WorkflowExecutionRepository(db_session)
    executions = await exec_repo.list_by_workflow(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
    )
    assert len(executions) >= 1
    assert executions[0].status == ExecutionStatus.COMPLETED
    assert executions[0].document_id == sample_test_invoice_doc.id
    assert any(
        "High value invoice INV-2026-001" in str(log_entry.get("details"))
        for log_entry in executions[0].execution_logs
    )


@pytest.mark.asyncio
async def test_on_document_approved_trigger(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_test_invoice_doc: Document,
):
    """Verify ON_DOCUMENT_APPROVED workflow triggers automatically on document approval."""
    wf_service = WorkflowService(db_session)

    # 1. Create ON_DOCUMENT_APPROVED workflow
    wf = await wf_service.create_workflow(
        workspace_id=test_workspace.id,
        workflow_in=Workflow(
            name="Post Approval ERP Sync",
            trigger_type=WorkflowTriggerType.ON_DOCUMENT_APPROVED,
            is_active=True,
            conditions={},
            actions=[
                {
                    "type": "DATABASE_UPDATE",
                    "name": "Archive Document on Approval",
                    "params": {"status": "completed", "metadata": {"erp_synced": True}},
                }
            ],
        ),
    )

    # 2. Approve document
    ext_service = ExtractionService(db_session)
    await ext_service.approve_document(
        document_id=sample_test_invoice_doc.id,
        workspace_id=test_workspace.id,
        user_id=test_workspace.created_by_id,
        approval_in=DocumentApprovalRequest(notes="Approved for payment"),
    )

    # 3. Verify workflow execution was created and completed
    exec_repo = WorkflowExecutionRepository(db_session)
    executions = await exec_repo.list_by_workflow(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
    )
    assert len(executions) >= 1
    assert executions[0].status == ExecutionStatus.COMPLETED
    assert executions[0].document_id == sample_test_invoice_doc.id


@pytest.mark.asyncio
async def test_on_document_rejected_trigger(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_test_invoice_doc: Document,
):
    """Verify ON_DOCUMENT_REJECTED workflow triggers automatically on document rejection."""
    wf_service = WorkflowService(db_session)

    # 1. Create ON_DOCUMENT_REJECTED workflow
    wf = await wf_service.create_workflow(
        workspace_id=test_workspace.id,
        workflow_in=Workflow(
            name="Rejection Notification Workflow",
            trigger_type=WorkflowTriggerType.ON_DOCUMENT_REJECTED,
            is_active=True,
            conditions={},
            actions=[
                {
                    "type": "NOTIFICATION",
                    "name": "Alert Approver on Rejection",
                    "params": {
                        "channel": "alerts",
                        "message": "Document was rejected: {{rejection_reason}}",
                    },
                }
            ],
        ),
    )

    # 2. Reject document
    ext_service = ExtractionService(db_session)
    await ext_service.reject_document(
        document_id=sample_test_invoice_doc.id,
        workspace_id=test_workspace.id,
        user_id=test_workspace.created_by_id,
        rejection_in=DocumentRejectionRequest(
            reason="Blurry receipt image", notes="Please resubmit"
        ),
    )

    # 3. Verify workflow execution
    exec_repo = WorkflowExecutionRepository(db_session)
    executions = await exec_repo.list_by_workflow(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
    )
    assert len(executions) >= 1
    assert executions[0].status == ExecutionStatus.COMPLETED
    assert executions[0].document_id == sample_test_invoice_doc.id


@pytest.mark.asyncio
async def test_workflow_failure_error_logging(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_test_invoice_doc: Document,
):
    """Verify that failing actions transition execution status to FAILED with error messages logged."""
    wf_service = WorkflowService(db_session)

    # Create workflow with an invalid HTTP action endpoint
    wf = await wf_service.create_workflow(
        workspace_id=test_workspace.id,
        workflow_in=Workflow(
            name="Failing Webhook Workflow",
            trigger_type=WorkflowTriggerType.MANUAL,
            is_active=True,
            conditions={},
            actions=[
                {
                    "type": "REST_API_REQUEST",
                    "name": "Invalid Endpoint Call",
                    "params": {
                        "url": "http://invalid-nonexistent-domain-xyz-12345.local/webhook",
                        "timeout": 1.0,
                        "retries": 1,
                    },
                }
            ],
        ),
    )

    # Execute workflow
    execution = await wf_service.trigger_execution(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
        document_id=sample_test_invoice_doc.id,
    )

    # Verify execution transitioned to FAILED and recorded error details
    assert execution.status == ExecutionStatus.FAILED
    assert execution.completed_at is not None
    assert execution.error_message is not None
    assert any(log.get("level") == "ERROR" for log in execution.execution_logs)


@pytest.mark.asyncio
async def test_celery_offline_local_fallback_processing(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_test_invoice_doc: Document,
):
    """Verify async_process_document executes pipeline in-process when Celery broker is offline."""
    res = await async_process_document(
        document_id=str(sample_test_invoice_doc.id),
        workspace_id=str(test_workspace.id),
        task_id="fallback-sync-test-1",
        force_reprocess=True,
        db=db_session,
    )
    assert res["status"] in ("completed", "review_required")

    # Verify DB persistence
    repo = DocumentRepository(db_session)
    updated = await repo.get_by_id_and_workspace(sample_test_invoice_doc.id, test_workspace.id)
    assert updated is not None
    assert updated.status in (DocumentStatus.COMPLETED, DocumentStatus.REVIEW_REQUIRED)


@pytest.mark.asyncio
async def test_dual_mode_workflow_dispatch_fallback(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_test_invoice_doc: Document,
):
    """Verify dual-mode workflow dispatch falls back to BackgroundTasks / async execution when Celery is offline."""
    wf_service = WorkflowService(db_session)

    wf = await wf_service.create_workflow(
        workspace_id=test_workspace.id,
        workflow_in=Workflow(
            name="Fallback Test Workflow",
            trigger_type=WorkflowTriggerType.MANUAL,
            is_active=True,
            conditions={},
            actions=[
                {
                    "type": "NOTIFICATION",
                    "name": "Fallback Step",
                    "params": {"message": "Executed via fallback"},
                }
            ],
        ),
    )

    # Test direct dispatch without Celery broker
    bg_tasks = BackgroundTasks()
    dispatch_res = await wf_service.dispatch_workflow_async(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
        document_id=sample_test_invoice_doc.id,
        background_tasks=bg_tasks,
    )
    assert dispatch_res["status"] in ("queued_fallback", "COMPLETED", "queued_celery")
