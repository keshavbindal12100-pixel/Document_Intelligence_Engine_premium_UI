import uuid

import pytest
from backend.app.core.permissions import WorkspaceRole
from backend.app.core.security import create_access_token
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.user import User, UserWorkspace
from backend.app.models.workspace import Workspace
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.services.extraction_service import ExtractionService
from backend.tests.fixtures.sample_documents import (
    STANDARD_INVOICE_TEXT,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

MATH_ERROR_INVOICE_TEXT = """
ACME SERVICES
Invoice Number: INV-2026-999
Invoice Date: 2026-03-01
Due Date: 2026-04-01

Description Qty Price Total
Consulting 1 $1,000.00 $1,000.00

Subtotal: $1,000.00
Tax: $100.00
Total Due: $5,000.00
"""

INCOMPLETE_INVOICE_TEXT = """
NOTICE
Some description without required fields.
Total Due: $500.00
"""


@pytest.fixture
async def sample_invoice_document(
    db_session: AsyncSession, test_workspace: Workspace, test_user: User
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_id=test_user.id,
        filename="invoice_review_test.pdf",
        original_filename="invoice_review_test.pdf",
        file_path="uploads/invoice_review_test.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256_hash="hash_phase4_review",
        status=DocumentStatus.UPLOADED,
        metadata_json={},
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def viewer_user_and_headers(
    db_session: AsyncSession, test_workspace: Workspace
) -> tuple[User, dict[str, str]]:
    """Create a user with VIEWER role in the test workspace."""
    viewer = User(
        id=uuid.uuid4(),
        email="viewer_user@example.com",
        full_name="Viewer User",
        hashed_password="hashed_pw",
        is_active=True,
    )
    db_session.add(viewer)
    await db_session.flush()

    member = UserWorkspace(
        workspace_id=test_workspace.id,
        user_id=viewer.id,
        role=WorkspaceRole.VIEWER,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(viewer)

    token = create_access_token(str(viewer.id))
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": str(test_workspace.id),
    }
    return viewer, headers


@pytest.mark.asyncio
async def test_confidence_routing_auto_complete_vs_review_required(
    db_session: AsyncSession,
    sample_invoice_document: Document,
):
    """Verify confidence >= 95% and valid validation auto-completes, while validation failures route to review_required."""
    ext_service = ExtractionService(db_session)

    # 1. Clean standard invoice -> high confidence >= 0.90 & valid math -> COMPLETED
    res_clean = await ext_service.classify_and_extract_document(
        document_id=sample_invoice_document.id,
        workspace_id=sample_invoice_document.workspace_id,
        ocr_text=STANDARD_INVOICE_TEXT,
    )
    assert res_clean.overall_confidence >= 0.90
    assert res_clean.validation is not None
    assert res_clean.validation.is_valid is True
    assert sample_invoice_document.status == DocumentStatus.COMPLETED

    # 2. Document with calculation/math errors -> routes to REVIEW_REQUIRED
    res_math_err = await ext_service.classify_and_extract_document(
        document_id=sample_invoice_document.id,
        workspace_id=sample_invoice_document.workspace_id,
        ocr_text=MATH_ERROR_INVOICE_TEXT,
    )
    assert res_math_err.validation is not None
    assert res_math_err.validation.is_valid is False
    assert sample_invoice_document.status == DocumentStatus.REVIEW_REQUIRED

    # 3. Document with missing required fields -> routes to REVIEW_REQUIRED
    res_incomplete = await ext_service.classify_and_extract_document(
        document_id=sample_invoice_document.id,
        workspace_id=sample_invoice_document.workspace_id,
        ocr_text=INCOMPLETE_INVOICE_TEXT,
    )
    assert res_incomplete.validation is not None
    assert res_incomplete.validation.is_valid is False
    assert sample_invoice_document.status == DocumentStatus.REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_human_corrections_and_audit_logging(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    sample_invoice_document: Document,
    test_user: User,
):
    """Verify user can correct fields, add missing values, and each correction generates an AuditLog."""
    ext_service = ExtractionService(db_session)
    await ext_service.classify_and_extract_document(
        document_id=sample_invoice_document.id,
        workspace_id=sample_invoice_document.workspace_id,
        ocr_text=INCOMPLETE_INVOICE_TEXT,
    )

    # Correct invoice_number and total via PUT /api/documents/{id}/extraction
    update_payload = {
        "fields": {
            "invoice_number": "INV-MANUAL-777",
            "total": "999.00",
            "vendor_name": "Corrected Vendor Corp",
            "subtotal": "999.00",
        },
        "reason": "Corrected missing fields from manual invoice review",
    }

    res = await client.put(
        f"/api/documents/{sample_invoice_document.id}/extraction",
        headers=auth_headers,
        json=update_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["fields"]["invoice_number"]["field_value"] == "INV-MANUAL-777"
    assert data["fields"]["invoice_number"]["is_manually_corrected"] is True
    assert data["fields"]["vendor_name"]["field_value"] == "Corrected Vendor Corp"

    # Verify AuditLog entries were created
    audit_repo = AuditRepository(db_session)
    logs, count = await audit_repo.list_filtered(
        workspace_id=sample_invoice_document.workspace_id,
        action="FIELD_CORRECTED",
    )
    assert count >= 1
    recent_log = logs[0]
    assert recent_log.user_id == test_user.id
    assert recent_log.changes["reason"] == "Corrected missing fields from manual invoice review"
    assert "field_name" in recent_log.changes


@pytest.mark.asyncio
async def test_document_approve_and_reject_apis(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    sample_invoice_document: Document,
    test_user: User,
):
    """Verify POST /api/documents/{id}/approve and /api/documents/{id}/reject with audit recording."""
    ext_service = ExtractionService(db_session)
    await ext_service.classify_and_extract_document(
        document_id=sample_invoice_document.id,
        workspace_id=sample_invoice_document.workspace_id,
        ocr_text=STANDARD_INVOICE_TEXT,
    )

    # 1. Reject document
    reject_res = await client.post(
        f"/api/documents/{sample_invoice_document.id}/reject",
        headers=auth_headers,
        json={
            "reason": "Duplicate invoice submission",
            "notes": "Rejected by accounting department.",
        },
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"
    assert reject_res.json()["processing_error"] == "Duplicate invoice submission"

    # Verify Rejection Audit Log
    audit_repo = AuditRepository(db_session)
    rej_logs, rej_count = await audit_repo.list_filtered(
        workspace_id=sample_invoice_document.workspace_id,
        action="DOCUMENT_REJECTED",
    )
    assert rej_count >= 1
    assert rej_logs[0].changes["reason"] == "Duplicate invoice submission"

    # 2. Approve document
    approve_res = await client.post(
        f"/api/documents/{sample_invoice_document.id}/approve",
        headers=auth_headers,
        json={
            "notes": "Approved after supervisor signoff",
        },
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "completed"

    # Verify Approval Audit Log
    app_logs, app_count = await audit_repo.list_filtered(
        workspace_id=sample_invoice_document.workspace_id,
        action="DOCUMENT_APPROVED",
    )
    assert app_count >= 1
    assert app_logs[0].changes["notes"] == "Approved after supervisor signoff"


@pytest.mark.asyncio
async def test_unauthorized_viewer_cannot_approve_or_reject(
    client: AsyncClient,
    viewer_user_and_headers: tuple[User, dict[str, str]],
    sample_invoice_document: Document,
):
    """Verify users with VIEWER role cannot approve or reject documents (403 Forbidden)."""
    _, viewer_headers = viewer_user_and_headers

    # Attempt approve as VIEWER
    app_res = await client.post(
        f"/api/documents/{sample_invoice_document.id}/approve",
        headers=viewer_headers,
        json={"notes": "Viewer trying to approve"},
    )
    assert app_res.status_code == 403

    # Attempt reject as VIEWER
    rej_res = await client.post(
        f"/api/documents/{sample_invoice_document.id}/reject",
        headers=viewer_headers,
        json={"reason": "Viewer trying to reject"},
    )
    assert rej_res.status_code == 403
