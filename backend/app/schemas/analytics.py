import uuid

from pydantic import BaseModel


class QueueStatusResponse(BaseModel):
    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    total_active: int = 0
    is_healthy: bool = True


class RecentDocumentItem(BaseModel):
    id: str
    filename: str
    document_type: str
    format: str
    extension: str
    status: str
    confidence_percentage: float | None = None
    created_at: str | None = None


class DashboardMetricsResponse(BaseModel):
    total_documents: int = 0
    documents_processed: int = 0
    processing_success_rate: float = 100.0
    accuracy_rate_percentage: float = 100.0
    latest_accuracy_percentage: float | None = None
    avg_accuracy_percentage: float | None = None
    avg_processing_time_seconds: float = 0.0
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    recent_documents: list[RecentDocumentItem] = []
    # Per-status counts
    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    rejected: int = 0


class BatchUploadItemResult(BaseModel):
    filename: str
    document_id: uuid.UUID | None = None
    status: str
    error: str | None = None


class BatchDocumentUploadResponse(BaseModel):
    total_uploaded: int
    successful_count: int
    failed_count: int
    items: list[BatchUploadItemResult]
