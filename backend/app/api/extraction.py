import uuid

from backend.app.api.deps import get_current_user, require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.models.document import Document
from backend.app.models.user import User
from backend.app.schemas.document import DocumentResponse
from backend.app.schemas.extraction import (
    DocumentExtractionSummary,
    DocumentReviewAction,
    ExtractedFieldCorrection,
    ExtractedFieldResponse,
)
from backend.app.services.extraction_service import ExtractionService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/extraction", tags=["Extraction & Human Review"])


@router.get("/{document_id}", response_model=DocumentExtractionSummary)
async def get_extraction_summary(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.EXTRACTION_READ)),
    db: AsyncSession = Depends(get_db),
) -> DocumentExtractionSummary:
    """Get all extracted fields and validation metrics for a document."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    return await service.get_document_extractions(document_id, workspace.id)


@router.post("/{document_id}/correct", response_model=ExtractedFieldResponse)
async def correct_field(
    document_id: uuid.UUID,
    correction_in: ExtractedFieldCorrection,
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.EXTRACTION_CORRECT)),
    db: AsyncSession = Depends(get_db),
) -> ExtractedFieldResponse:
    """Manually correct a single extracted field value."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    field = await service.correct_field(
        document_id=document_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        correction=correction_in,
    )
    return ExtractedFieldResponse.model_validate(field)


@router.post("/{document_id}/review", response_model=DocumentResponse)
async def review_document(
    document_id: uuid.UUID,
    review_in: DocumentReviewAction,
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.EXTRACTION_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Submit human review decision (APPROVE / REJECT) with optional corrections."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    return await service.review_document(
        document_id=document_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        review=review_in,
    )
