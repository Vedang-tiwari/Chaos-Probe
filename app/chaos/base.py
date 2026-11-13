from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class FaultContext:
    """Contextual metadata passed to fault lifecycle operations."""

    experiment_id: uuid.UUID
    service_id: uuid.UUID
    target_container_id: str | None
    target_base_url: str
    target_health_url: str
    configuration: dict[str, Any]
    state: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseFaultStrategy(ABC):
    """Abstract base class for all Chaos Probe fault injection strategies.

    Every fault strategy must adhere to strict safety guarantees:
    - apply: activates the fault
    - verify: confirms the fault is active
    - rollback: restores original state (must be safe to run even if apply failed)
    - cleanup: ensures resources, temporary configs, and background tasks are purged
    """

    @property
    @abstractmethod
    def fault_type(self) -> str:
        """Returns the unique identifier key for this fault strategy."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the fault and its intended impact."""
        pass

    @abstractmethod
    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validates configuration parameters against safety boundaries."""
        pass

    @abstractmethod
    async def apply(self, context: FaultContext) -> bool:
        """Applies the fault to the target service or infrastructure."""
        pass

    @abstractmethod
    async def verify(self, context: FaultContext) -> bool:
        """Verifies that the fault is currently active."""
        pass

    @abstractmethod
    async def rollback(self, context: FaultContext) -> bool:
        """Reverts the injected fault and restores baseline operational state."""
        pass

    @abstractmethod
    async def cleanup(self, context: FaultContext) -> bool:
        """Idempotent final cleanup of any residual state or resources."""
        pass
