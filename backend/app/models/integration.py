import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from backend.app.models.base import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, Boolean, ForeignKey, String, Uuid
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.workspace import Workspace


class IntegrationType(StrEnum):
    WEBHOOK = "WEBHOOK"
    REST_API = "REST_API"
    SLACK = "SLACK"
    S3 = "S3"
    EMAIL = "EMAIL"


class Integration(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integrations"

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
    type: Mapped[IntegrationType] = mapped_column(
        SQLEnum(IntegrationType, native_enum=False),
        default=IntegrationType.WEBHOOK,
        nullable=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="integrations")
