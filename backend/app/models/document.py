import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, BigInteger, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.document_template import DocumentTemplate
    from backend.app.models.extracted_field import ExtractedField
    from backend.app.models.user import User
    from backend.app.models.workflow_execution import WorkflowExecution
    from backend.app.models.workspace import Workspace


class DocumentType(StrEnum):
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    FORM = "FORM"
    CONTRACT = "CONTRACT"
    ID_CARD = "ID_CARD"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    REJECTED = "rejected"


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    sha256_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, native_enum=False),
        default=DocumentType.UNKNOWN,
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False),
        default=DocumentStatus.UPLOADED,
        index=True,
        nullable=False,
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="documents")
    uploaded_by: Mapped[Optional["User"]] = relationship(
        "User", back_populates="uploaded_documents"
    )
    template: Mapped[Optional["DocumentTemplate"]] = relationship(
        "DocumentTemplate", back_populates="documents"
    )
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        "ExtractedField",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    workflow_executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    @property
    def file_name(self) -> str:
        return self.original_filename

    @property
    def file_size_bytes(self) -> int:
        return self.file_size

    @property
    def ocr_confidence(self) -> float | None:
        return self.confidence_score

    __table_args__ = (
        Index("ix_documents_workspace_status", "workspace_id", "status"),
        Index("ix_documents_workspace_type", "workspace_id", "document_type"),
    )
