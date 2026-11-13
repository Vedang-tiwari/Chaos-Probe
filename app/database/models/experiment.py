import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.metrics import ExperimentEvent, ExperimentMetric
    from app.database.models.report import ExperimentReport
    from app.database.models.service import Service


class Experiment(Base):
    """Represents a controlled fault-injection experiment against a target service."""

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fault_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="CREATED",
        index=True,
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    abort_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="experiments",
    )
    metrics: Mapped[List["ExperimentMetric"]] = relationship(
        "ExperimentMetric",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    events: Mapped[List["ExperimentEvent"]] = relationship(
        "ExperimentEvent",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    report: Mapped["ExperimentReport | None"] = relationship(
        "ExperimentReport",
        back_populates="experiment",
        uselist=False,
        cascade="all, delete-orphan",
    )
