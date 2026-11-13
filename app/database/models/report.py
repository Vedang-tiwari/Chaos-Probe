import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.experiment import Experiment


class ExperimentReport(Base):
    """Stores the synthesized outcome, score, metrics summary, and recommendations."""

    __tablename__ = "experiment_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    outcome: Mapped[str] = mapped_column(
        String(64),
        nullable=False,  # SURVIVED, DEGRADED, FAILED, RECOVERED, RECOVERY_FAILED, ABORTED
        index=True,
    )
    availability_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=100.0,
    )
    average_latency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    maximum_latency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    error_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    recovery_time_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    recommendations: Mapped[list[Any]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    experiment: Mapped["Experiment"] = relationship(
        "Experiment",
        back_populates="report",
    )
