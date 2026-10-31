import uuid
from typing import TYPE_CHECKING, Optional

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.audit_log import AuditLog
    from backend.app.models.document import Document
    from backend.app.models.document_template import DocumentTemplate
    from backend.app.models.integration import Integration
    from backend.app.models.user import User, UserWorkspace
    from backend.app.models.workflow import Workflow


class Workspace(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_workspaces",
    )
    user_memberships: Mapped[list["UserWorkspace"]] = relationship(
        "UserWorkspace",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    templates: Mapped[list["DocumentTemplate"]] = relationship(
        "DocumentTemplate",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
