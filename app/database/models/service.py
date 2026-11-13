import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.experiment import Experiment


class Service(Base, TimestampMixin):
    """Represents a registered target application or microservice."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    base_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    health_check_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    container_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    environment: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="development",
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UNKNOWN",  # HEALTHY, UNHEALTHY, UNKNOWN, DEGRADED
        index=True,
    )

    # Relationships
    experiments: Mapped[List["Experiment"]] = relationship(
        "Experiment",
        back_populates="service",
        cascade="all, delete-orphan",
    )
