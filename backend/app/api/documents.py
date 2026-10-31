import math
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from backend.app.api.deps import get_current_user, require_permission
from backend.app.core.permissions import Permission
from backend.app.db.database import get_db
from backend.app.models.audit_log import AuditLog
from backend.app.models.document import Document, DocumentStatus, DocumentType
from backend.app.models.user import User
from backend.app.schemas.analytics import BatchDocumentUploadResponse
from backend.app.schemas.audit import AuditLogResponse
from backend.app.schemas.common import MessageResponse, PaginatedResponse
from backend.app.schemas.document import DocumentFilter, DocumentResponse, DocumentUpdate
from backend.app.schemas.extraction import (
    DocumentApprovalRequest,
    DocumentExtractionResponse,
    DocumentExtractionUpdateRequest,
    DocumentRejectionRequest,
)
from backend.app.services.document_service import DocumentService
from backend.app.services.extraction_service import ExtractionService
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    template_id: uuid.UUID | None = Form(None),
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Upload a single document for async processing and OCR extraction."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.upload_document(
        workspace_id=workspace.id,
        user_id=current_user.id,
        file=file,
        document_type=document_type,
        template_id=template_id,
        background_tasks=background_tasks,
    )


@router.post("/upload-any", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_any_format(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    template_id: uuid.UUID | None = Form(None),
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Upload a document in ANY file format (not restricted to PDF/PNG/JPG/TIFF).

    Only filename sanitization and the max file size limit are enforced;
    the extension/MIME/magic-byte checks used by the strict PDF/image
    upload endpoint are skipped here.
    """
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.upload_document_any_format(
        workspace_id=workspace.id,
        user_id=current_user.id,
        file=file,
        document_type=document_type,
        template_id=template_id,
        background_tasks=background_tasks,
    )


@router.post(
    "/batch", response_model=BatchDocumentUploadResponse, status_code=status.HTTP_201_CREATED
)
@router.post(
    "/batch-upload", response_model=BatchDocumentUploadResponse, status_code=status.HTTP_201_CREATED
)
async def batch_upload_documents_endpoint(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
    db: AsyncSession = Depends(get_db),
) -> BatchDocumentUploadResponse:
    """Upload multiple documents in a single request and queue them asynchronously."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.batch_upload_documents(
        workspace_id=workspace.id,
        user_id=current_user.id,
        files=files,
        background_tasks=background_tasks,
    )


@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    status: DocumentStatus | None = Query(None),
    document_type: DocumentType | None = Query(None),
    vendor: str | None = Query(None),
    invoice_number: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    min_amount: float | None = Query(None),
    max_amount: float | None = Query(None),
    min_confidence: float | None = Query(None),
    max_confidence: float | None = Query(None),
    workflow_status: str | None = Query(None),
    upload_date_from: datetime | None = Query(None),
    upload_date_to: datetime | None = Query(None),
    tags: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DocumentResponse]:
    """List documents in active workspace with multi-criteria search, date ranges, and sorting."""
    workspace, _ = ws_context
    service = DocumentService(db)
    filters = DocumentFilter(
        status=status,
        document_type=document_type,
        vendor=vendor,
        invoice_number=invoice_number,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        workflow_status=workflow_status,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to,
        tags=tags,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    items, total = await service.list_documents(workspace.id, filters)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[DocumentResponse](
        items=[DocumentResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/export/csv")
async def export_documents_csv_endpoint(
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Export workspace documents metadata in CSV format."""
    workspace, _ = ws_context
    service = DocumentService(db)
    csv_content = await service.export_documents_csv(workspace.id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="documents_export.csv"'},
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Get document details."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.get_document(document_id, workspace.id)


@router.get("/{document_id}/audit", response_model=list[AuditLogResponse])
async def get_document_audit_history(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> Sequence[AuditLog]:
    """Get audit trail history for a specific document."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.get_document_audit_logs(document_id, workspace.id)


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Download the original document file."""
    workspace, _ = ws_context
    service = DocumentService(db)
    file_bytes, filename, mime_type = await service.get_document_file_bytes(
        document_id, workspace.id
    )
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{document_id}/export-erp")
async def export_document_erp_data(
    document_id: uuid.UUID,
    format: str = Query("json", pattern="^(json|csv|txt)$"),
    ws_context=Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Export extracted document fields and audit metadata in ERP-ready format (JSON, CSV, or TXT)."""
    import csv
    import io
    import json

    workspace, _ = ws_context
    doc_service = DocumentService(db)
    ext_service = ExtractionService(db)

    doc = await doc_service.get_document(document_id, workspace.id)
    try:
        extraction = await ext_service.get_document_extraction(document_id, workspace.id)
        fields_dict = {name: field.field_value for name, field in extraction.fields.items()}
    except Exception:
        fields_dict = {}

    status_str = str(doc.status.value if hasattr(doc.status, "value") else doc.status)
    doc_type_str = str(
        doc.document_type.value if hasattr(doc.document_type, "value") else doc.document_type
    )

    erp_payload = {
        "erp_system_version": "1.0",
        "export_timestamp": datetime.now(UTC).isoformat(),
        "document_id": str(doc.id),
        "filename": doc.original_filename,
        "document_type": doc_type_str,
        "status": status_str,
        "confidence_score": doc.confidence_score or 0.0,
        "extracted_fields": fields_dict,
        "raw_text": (doc.metadata_json or {}).get("ocr_result", {}).get("full_text", ""),
    }

    clean_name = (
        doc.original_filename.rsplit(".", 1)[0]
        if "." in doc.original_filename
        else doc.original_filename
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["Document_ID", "Filename", "Field_Name", "Field_Value", "Confidence", "Status"]
        )
        for fname, fval in fields_dict.items():
            writer.writerow(
                [
                    str(doc.id),
                    doc.original_filename,
                    fname,
                    fval or "",
                    doc.confidence_score or 0.0,
                    status_str,
                ]
            )
        if not fields_dict:
            writer.writerow(
                [
                    str(doc.id),
                    doc.original_filename,
                    "RAW_TEXT",
                    erp_payload["raw_text"],
                    doc.confidence_score or 0.0,
                    status_str,
                ]
            )
        content = output.getvalue()
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{clean_name}_erp_export.csv"'},
        )

    elif format == "txt":
        lines = [
            "=========================================",
            "ERP DOCUMENT EXTRACTION EXPORT",
            "=========================================",
            f"Document ID   : {doc.id}",
            f"Filename      : {doc.original_filename}",
            f"Document Type : {doc_type_str}",
            f"Status        : {status_str}",
            f"Confidence    : {doc.confidence_score or 0.0:.2f}",
            "-----------------------------------------",
            "EXTRACTED FIELDS FOR ERP IMPORT:",
            "-----------------------------------------",
        ]
        for fname, fval in fields_dict.items():
            lines.append(f"{fname:<20} : {fval}")
        if erp_payload["raw_text"]:
            lines.extend(
                [
                    "-----------------------------------------",
                    "FULL EXTRACTED RAW TEXT:",
                    "-----------------------------------------",
                    erp_payload["raw_text"],
                ]
            )
        lines.append("=========================================")
        content = "\n".join(lines)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{clean_name}_erp_export.txt"'},
        )

    else:
        content = json.dumps(erp_payload, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{clean_name}_erp_export.json"'},
        )


def _pdf_escape(value: object) -> str:
    """Escape text for a PDF literal string."""
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_audit_pdf(lines: list[str]) -> bytes:
    """Build a small dependency-free, text-only PDF for audit downloads."""
    page_lines = [lines[i : i + 48] for i in range(0, len(lines), 48)] or [[""]]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_refs: list[str] = []
    for page in page_lines:
        content_lines = ["BT", "/F1 9 Tf", "50 742 Td"]
        for index, line in enumerate(page):
            if index:
                content_lines.append("0 -14 Td")
            content_lines.append(f"({_pdf_escape(line[:150])}) Tj")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", errors="replace")
        content_obj = f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        content_index = len(objects) + 1
        objects.append(content_obj)
        page_obj = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_index} 0 R >>"
        ).encode()
        page_index = len(objects) + 1
        objects.append(page_obj)
        page_refs.append(f"{page_index} 0 R")
    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>".encode()
    )
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    )
    return bytes(pdf)


@router.get("/{document_id}/export-pdf")
async def export_document_audit_pdf(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Download a printable PDF containing extraction metadata and audit history."""
    workspace, _ = ws_context
    doc_service = DocumentService(db)
    ext_service = ExtractionService(db)
    doc = await doc_service.get_document(document_id, workspace.id)
    extraction = await ext_service.get_document_extraction(document_id, workspace.id)
    audit_logs = await doc_service.get_document_audit_logs(document_id, workspace.id)
    status_str = getattr(doc.status, "value", doc.status)
    doc_type_str = getattr(doc.document_type, "value", doc.document_type)
    lines = [
        "DOCUMENT INTELLIGENCE AUDIT REPORT",
        "===================================",
        f"Document ID: {doc.id}",
        f"Filename: {doc.original_filename}",
        f"Document type: {doc_type_str}",
        f"Status: {status_str}",
        f"Overall confidence: {doc.confidence_score or 0.0:.2%}",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "EXTRACTED FIELDS",
        "-----------------",
    ]
    for name, field in extraction.fields.items():
        lines.append(
            f"{name}: {field.field_value or '[missing]'} (confidence {field.confidence:.2%})"
        )
    raw_text = (doc.metadata_json or {}).get("ocr_result", {}).get("full_text", "")
    if raw_text:
        lines.extend(["", "RAW OCR TEXT", "------------", *raw_text.splitlines()])
    lines.extend(["", "AUDIT EVENTS", "------------"])
    for event in audit_logs:
        action = getattr(event.action, "value", event.action)
        details = event.changes or {}
        lines.append(f"{event.created_at.isoformat()} | {action} | {event.entity_type} | {details}")
    content = _build_audit_pdf(lines)
    clean_name = (
        doc.original_filename.rsplit(".", 1)[0]
        if "." in doc.original_filename
        else doc.original_filename
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{clean_name}_audit_report.pdf"'},
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    update_in: DocumentUpdate,
    ws_context=Depends(require_permission(Permission.DOCUMENT_PROCESS)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Update document properties."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.update_document(document_id, workspace.id, update_in)


@router.post("/{document_id}/process", response_model=DocumentResponse)
async def process_document_endpoint(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ws_context=Depends(require_permission(Permission.DOCUMENT_PROCESS)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Trigger asynchronous OCR document processing."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.trigger_processing(
        document_id, workspace.id, background_tasks=background_tasks
    )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document_endpoint(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ws_context=Depends(require_permission(Permission.DOCUMENT_PROCESS)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Force asynchronous reprocessing of a document."""
    workspace, _ = ws_context
    service = DocumentService(db)
    return await service.trigger_reprocessing(
        document_id, workspace.id, background_tasks=background_tasks
    )


@router.get("/{document_id}/extraction", response_model=DocumentExtractionResponse)
async def get_document_extraction_endpoint(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.EXTRACTION_READ)),
    db: AsyncSession = Depends(get_db),
) -> DocumentExtractionResponse:
    """Get structured extracted fields and classification data for a document."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    return await service.get_document_extraction(document_id, workspace.id)


@router.put("/{document_id}/extraction", response_model=DocumentExtractionResponse)
async def update_document_extraction_endpoint(
    document_id: uuid.UUID,
    payload: DocumentExtractionUpdateRequest,
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.EXTRACTION_CORRECT)),
    db: AsyncSession = Depends(get_db),
) -> DocumentExtractionResponse:
    """Update or correct structured extracted fields for a document."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    return await service.update_document_extraction(
        document_id=document_id,
        workspace_id=workspace.id,
        payload=payload,
        user_id=current_user.id,
    )


@router.post("/{document_id}/approve", response_model=DocumentResponse)
async def approve_document_endpoint(
    document_id: uuid.UUID,
    approval_in: DocumentApprovalRequest = DocumentApprovalRequest(),
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.EXTRACTION_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Approve document after review and transition status to completed."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    return await service.approve_document(
        document_id=document_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        approval_in=approval_in,
    )


@router.post("/{document_id}/reject", response_model=DocumentResponse)
async def reject_document_endpoint(
    document_id: uuid.UUID,
    rejection_in: DocumentRejectionRequest,
    current_user: User = Depends(get_current_user),
    ws_context=Depends(require_permission(Permission.EXTRACTION_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Reject document with reason and transition status to rejected."""
    workspace, _ = ws_context
    service = ExtractionService(db)
    return await service.reject_document(
        document_id=document_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        rejection_in=rejection_in,
    )


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: uuid.UUID,
    ws_context=Depends(require_permission(Permission.DOCUMENT_DELETE)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete document and its storage file."""
    workspace, _ = ws_context
    service = DocumentService(db)
    await service.delete_document(document_id, workspace.id)
    return MessageResponse(message="Document deleted successfully.")
