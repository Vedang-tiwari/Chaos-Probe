import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid
from app.core.config import get_settings
from app.core.exceptions import (
    EmergencyStopTriggeredError,
    ExperimentConflictError,
    ExperimentValidationError,
    SafetyThresholdExceededError,
)
from app.core.logging import logger
from app.database.models.service import Service


class SafetyController:
    """Enforces execution boundaries, concurrent lock protection, and threshold guardrails."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Maps service_id -> active experiment_id
        self._active_target_locks: Dict[uuid.UUID, uuid.UUID] = {}
        # Global emergency stop flag
        self._emergency_stop_active = False
        self._emergency_stop_reason: Optional[str] = None

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop_active

    @property
    def emergency_stop_reason(self) -> Optional[str]:
        return self._emergency_stop_reason

    def reset_emergency_stop(self) -> None:
        """Resets emergency stop status after verified operator remediation."""
        with self._lock:
            self._emergency_stop_active = False
            self._emergency_stop_reason = None
            logger.info("SafetyController emergency stop flag reset.")

    def trigger_emergency_stop(self, reason: str = "Manual operator emergency stop") -> None:
        """Halts all active and queued fault injections globally."""
        with self._lock:
            self._emergency_stop_active = True
            self._emergency_stop_reason = reason
            logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")

    def acquire_target_lock(self, service_id: uuid.UUID, experiment_id: uuid.UUID) -> None:
        """Acquires exclusive execution lock for a target service to prevent concurrent experiments."""
        if self._emergency_stop_active:
            raise EmergencyStopTriggeredError(
                f"Cannot start experiment: Platform is in EMERGENCY STOP state ({self._emergency_stop_reason})"
            )

        with self._lock:
            if service_id in self._active_target_locks:
                active_exp = self._active_target_locks[service_id]
                raise ExperimentConflictError(
                    f"Target service {service_id} already has active experiment {active_exp}. Concurrent experiments are forbidden.",
                    details={"service_id": str(service_id), "active_experiment_id": str(active_exp)},
                )
            self._active_target_locks[service_id] = experiment_id
            logger.info(f"Acquired execution lock on service {service_id} for experiment {experiment_id}")

    def release_target_lock(self, service_id: uuid.UUID, experiment_id: uuid.UUID) -> None:
        """Releases execution lock on target service."""
        with self._lock:
            if self._active_target_locks.get(service_id) == experiment_id:
                del self._active_target_locks[service_id]
                logger.info(f"Released execution lock on service {service_id} from experiment {experiment_id}")

    def validate_safety_boundaries(
        self,
        service: Service,
        duration_seconds: int,
        configuration: dict[str, Any],
    ) -> None:
        """Validates that requested experiment respects platform-wide safety constraints."""
        settings = get_settings()

        if duration_seconds <= 0:
            raise ExperimentValidationError("Experiment duration must be greater than 0 seconds.")

        if duration_seconds > settings.MAX_EXPERIMENT_DURATION_SECONDS:
            raise ExperimentValidationError(
                f"Requested duration {duration_seconds}s exceeds platform maximum of {settings.MAX_EXPERIMENT_DURATION_SECONDS}s."
            )

        if not service:
            raise ExperimentValidationError("Target service must be registered in the service registry.")

    def evaluate_safety_thresholds(
        self,
        experiment_id: uuid.UUID,
        current_metrics: Dict[str, float],
        configured_thresholds: Dict[str, float],
    ) -> Tuple[bool, Optional[str]]:
        """Evaluates live observations against configured safety abort thresholds."""
        if self._emergency_stop_active:
            return False, f"Aborted: Emergency stop activated ({self._emergency_stop_reason})"

        # 1. Error Rate Guardrail
        max_error_rate = configured_thresholds.get("max_error_rate", 0.50)
        curr_error_rate = current_metrics.get("error_rate", 0.0)
        if curr_error_rate > max_error_rate:
            msg = f"Error rate {curr_error_rate:.1%} exceeded critical safety threshold of {max_error_rate:.1%}"
            return False, msg

        # 2. Latency Guardrail
        max_latency_ms = configured_thresholds.get("max_latency_ms", 5000.0)
        curr_latency = current_metrics.get("latency_ms", 0.0)
        if curr_latency > max_latency_ms:
            msg = f"Observed latency {curr_latency:.1f}ms exceeded critical threshold of {max_latency_ms:.1f}ms"
            return False, msg

        # 3. Minimum Availability Guardrail
        min_availability = configured_thresholds.get("min_availability", 0.50)
        curr_avail = current_metrics.get("availability_percentage", 100.0) / 100.0
        if curr_avail < min_availability:
            msg = f"Availability {curr_avail:.1%} dropped below critical threshold of {min_availability:.1%}"
            return False, msg

        return True, None


default_safety_controller = SafetyController()

