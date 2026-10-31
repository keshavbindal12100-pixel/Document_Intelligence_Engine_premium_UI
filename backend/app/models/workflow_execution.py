import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from backend.app.models.base import Base, TimestampMixin, UUIDMixin, utc_now
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.workflow import Workflow
    from backend.app.models.workspace import Workspace


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowExecution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_executions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SQLEnum(ExecutionStatus, native_enum=False),
        default=ExecutionStatus.PENDING,
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_logs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    document: Mapped[Optional["Document"]] = relationship(
        "Document", back_populates="workflow_executions"
    )

    __table_args__ = (Index("ix_wf_exec_workspace_status", "workspace_id", "status"),)
