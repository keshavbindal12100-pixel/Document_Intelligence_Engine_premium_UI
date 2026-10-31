import uuid
from typing import TYPE_CHECKING

from backend.app.core.permissions import WorkspaceRole
from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Boolean, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.audit_log import AuditLog
    from backend.app.models.document import Document
    from backend.app.models.workspace import Workspace


class UserWorkspace(Base, TimestampMixin):
    __tablename__ = "user_workspaces"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, native_enum=False),
        default=WorkspaceRole.VIEWER,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="workspace_memberships")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="user_memberships")


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    workspace_memberships: Mapped[list["UserWorkspace"]] = relationship(
        "UserWorkspace",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace",
        back_populates="created_by",
    )
    uploaded_documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="uploaded_by",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
    )
