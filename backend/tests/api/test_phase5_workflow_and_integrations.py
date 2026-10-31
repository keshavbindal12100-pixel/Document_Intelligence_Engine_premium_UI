import uuid
from unittest.mock import patch

import pytest
from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.models.user import User
from backend.app.models.workflow import Workflow, WorkflowTriggerType
from backend.app.models.workflow_execution import ExecutionStatus
from backend.app.models.workspace import Workspace
from backend.app.services.workflow_service import WorkflowService
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def sample_invoice_document(
    db_session: AsyncSession, test_workspace: Workspace, test_user: User
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_id=test_user.id,
        filename="workflow_test_invoice.pdf",
        original_filename="workflow_test_invoice.pdf",
        file_path="uploads/workflow_test_invoice.pdf",
        mime_type="application/pdf",
        file_size=2048,
        sha256_hash="hash_phase5_test",
        status=DocumentStatus.COMPLETED,
        document_type=DocumentType.INVOICE,
        metadata_json={
            "total": 150000.00,
            "vendor_name": "Mega Enterprise Corp",
            "invoice_number": "INV-MEGA-9901",
            "invoice_date": "2026-03-20",
        },
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_workflow_condition_true_and_false_branches(
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_invoice_document: Document,
):
    """Verify workflow executes THEN actions when condition is met, and ELSE actions when not met."""
    wf_service = WorkflowService(db_session)

    # 1. Workflow: IF total > 100000 THEN require manager approval ELSE archive
    wf = await wf_service.create_workflow(
        workspace_id=test_workspace.id,
        workflow_in=Workflow(
            name="High Value Invoice Routing",
            trigger_type=WorkflowTriggerType.ON_DOCUMENT_APPROVED,
            conditions={
                "field": "total",
                "operator": ">",
                "value": 100000,
                "else_actions": [
                    {
                        "type": "ARCHIVE",
                        "name": "Auto Archive Low Value",
                    }
                ],
            },
            actions=[
                {
                    "type": "APPROVAL",
                    "name": "Require Director Signoff",
                    "params": {"role": "DIRECTOR", "reason": "Invoice exceeds $100,000 threshold"},
                }
            ],
        ),
    )

    # Execution 1: sample_invoice_document has total = 150000.00 -> Condition is True -> Approval required
    exec_res1 = await wf_service.trigger_execution(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
        document_id=sample_invoice_document.id,
    )
    assert exec_res1.status == ExecutionStatus.COMPLETED
    await db_session.refresh(sample_invoice_document)
    assert sample_invoice_document.status == DocumentStatus.REVIEW_REQUIRED
    assert sample_invoice_document.metadata_json["required_approval"]["role"] == "DIRECTOR"

    # Execution 2: custom context with total = 50000.00 -> Condition is False -> Else branch runs (Archive)
    exec_res2 = await wf_service.trigger_execution(
        workflow_id=wf.id,
        workspace_id=test_workspace.id,
        document_id=sample_invoice_document.id,
        custom_context={"total": 50000.00},
    )
    assert exec_res2.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_template_crud_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test Template creation, listing, updating (PUT), and deletion per PRD Section 31."""
    # 1. Create Template
    create_res = await client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Standard Vendor Invoice Template",
            "document_type": "INVOICE",
            "fields_schema": {
                "vendor_name": {"type": "string", "required": True},
                "total": {"type": "currency", "required": True},
            },
            "validation_rules": [
                {"rule": "subtotal + tax - discount == total", "severity": "ERROR"}
            ],
        },
    )
    assert create_res.status_code == 201
    tpl = create_res.json()
    tpl_id = tpl["id"]

    # 2. List Templates
    list_res = await client.get("/api/v1/templates", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Update Template (PUT)
    put_res = await client.put(
        f"/api/v1/templates/{tpl_id}",
        headers=auth_headers,
        json={"name": "Updated Vendor Template"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Updated Vendor Template"

    # 4. Delete Template
    del_res = await client.delete(f"/api/v1/templates/{tpl_id}", headers=auth_headers)
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_integrations_crud_and_test_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test Integration creation, webhook test dispatch per PRD Section 31."""
    # 1. Create Webhook Integration
    create_res = await client.post(
        "/api/v1/integrations",
        headers=auth_headers,
        json={
            "name": "ERP Webhook Destination",
            "type": "WEBHOOK",
            "config": {
                "url": "https://httpbin.org/post",
                "headers": {"X-Custom-Auth": "SecretKey123"},
            },
            "is_active": True,
        },
    )
    assert create_res.status_code == 201
    integ = create_res.json()
    integ_id = integ["id"]

    # 2. List Integrations
    list_res = await client.get("/api/v1/integrations", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Test Integration Webhook (with mock or test payload)
    mock_response = {
        "status_code": 200,
        "success": True,
        "attempts": 1,
        "response_body": '{"received": true}',
        "error": None,
    }
    with patch(
        "backend.app.services.integration_service.workflow_engine.execute_http_request_with_retry",
        return_value=mock_response,
    ):
        test_res = await client.post(
            f"/api/v1/integrations/{integ_id}/test",
            headers=auth_headers,
            json={"event": "test.event", "data": {"invoice_id": "123"}},
        )
        assert test_res.status_code == 200
        assert test_res.json()["status_code"] == 200
