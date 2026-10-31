import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.workflow_execution import WorkflowExecution
    from backend.app.models.workspace import Workspace


class WorkflowTriggerType(StrEnum):
    ON_DOCUMENT_EXTRACTED = "ON_DOCUMENT_EXTRACTED"
    ON_DOCUMENT_APPROVED = "ON_DOCUMENT_APPROVED"
    ON_DOCUMENT_REJECTED = "ON_DOCUMENT_REJECTED"
    ON_DOCUMENT_UPLOADED = "ON_DOCUMENT_UPLOADED"
    ON_LOW_CONFIDENCE = "ON_LOW_CONFIDENCE"
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class Workflow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflows"

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
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    trigger_type: Mapped[WorkflowTriggerType] = mapped_column(
        SQLEnum(WorkflowTriggerType, native_enum=False),
        default=WorkflowTriggerType.ON_DOCUMENT_APPROVED,
        nullable=False,
    )
    conditions: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    actions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="workflows")
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="desc(WorkflowExecution.created_at)",
    )
