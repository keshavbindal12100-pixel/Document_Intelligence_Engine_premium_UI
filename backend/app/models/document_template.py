import uuid
from typing import TYPE_CHECKING, Any

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from backend.app.models.document import DocumentType
from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.workspace import Workspace


class DocumentTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_templates"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, native_enum=False),
        default=DocumentType.CUSTOM,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    rules_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="templates")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="template")
