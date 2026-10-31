import io
import uuid
from unittest.mock import patch

import pypdfium2
import pytest
from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.models.workspace import Workspace
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.services.ocr_service import ocr_service
from backend.app.services.storage_service import storage_service
from backend.app.workers.tasks import async_process_document
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def sample_document(
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> Document:
    """Create a persistent test document in storage and database."""
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
        original_filename="sample_invoice.pdf",
        file_path=file_path,
        file_size=len(content),
        mime_type="application/pdf",
        sha256_hash=f"hash_{uuid.uuid4().hex}",
        document_type=DocumentType.INVOICE,
        status=DocumentStatus.QUEUED,
    )
    repo = DocumentRepository(db_session)
    created = await repo.create(doc)
    await db_session.commit()
    return created


@pytest.mark.asyncio
async def test_successful_ocr_processing(
    db_session: AsyncSession,
    sample_document: Document,
):
    """Verify end-to-end background task execution on successful OCR."""
    mock_ocr_result = {
        "total_pages": 1,
        "overall_confidence": 0.94,
        "full_text": "ACME CORP\nINVOICE #4590\nTotal Due: $1,250.00",
        "statistics": {
            "character_count": 45,
            "word_count": 7,
            "line_count": 3,
            "is_empty": False,
        },
        "pages": [
            {
                "page_number": 1,
                "confidence": 0.94,
                "cleaned_text": "ACME CORP\nINVOICE #4590\nTotal Due: $1,250.00",
                "word_count": 7,
                "is_empty": False,
            }
        ],
    }

    with patch.object(ocr_service, "process_document", return_value=mock_ocr_result):
        res = await async_process_document(
            document_id=str(sample_document.id),
            workspace_id=str(sample_document.workspace_id),
            task_id="test-task-1",
            force_reprocess=False,
            db=db_session,
        )
        assert res["status"] == "completed"
        assert res["confidence_score"] is not None
        assert res["confidence_score"] >= 0.80

    # Verify DB persistence
    repo = DocumentRepository(db_session)
    updated = await repo.get_by_id_and_workspace(sample_document.id, sample_document.workspace_id)
    assert updated is not None
    assert updated.status == DocumentStatus.COMPLETED
    assert updated.confidence_score is not None
    assert updated.confidence_score >= 0.80
    assert updated.metadata_json["ocr_result"]["total_pages"] == 1
