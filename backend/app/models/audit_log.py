import uuid
from typing import TYPE_CHECKING, Any, Optional

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    changes: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="audit_logs")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    @property
    def details(self) -> dict[str, Any] | None:
        return self.changes

    @property
    def document_id(self) -> str | None:
        return self.entity_id

    __table_args__ = (
        Index("ix_audit_logs_workspace_entity", "workspace_id", "entity_type", "entity_id"),
    )
