import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace


class FieldType(StrEnum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    FLOAT = "FLOAT"
    DATE = "DATE"
    CURRENCY = "CURRENCY"
    TABLE = "TABLE"
    JSON = "JSON"
    BOOLEAN = "BOOLEAN"


class ExtractedField(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "extracted_fields"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    field_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    normalized_value: Mapped[Any | None] = mapped_column(
        JSON,
        nullable=True,
    )
    field_type: Mapped[FieldType] = mapped_column(
        SQLEnum(FieldType, native_enum=False),
        default=FieldType.STRING,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    validation_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_manually_corrected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    corrected_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extracted_fields")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    corrected_by: Mapped[Optional["User"]] = relationship("User")

    @property
    def confidence_score(self) -> float:
        return self.confidence

    __table_args__ = (Index("ix_extracted_fields_doc_name", "document_id", "field_name"),)
