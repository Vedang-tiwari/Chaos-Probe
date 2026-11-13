from typing import Any


class ChaosProbeException(Exception):
    """Base exception for all Chaos Probe errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ServiceNotFoundError(ChaosProbeException):
    """Raised when a requested service is not found in the registry."""
    pass


class ServiceAlreadyExistsError(ChaosProbeException):
    """Raised when attempting to register a duplicate service."""
    pass


class ServiceUnhealthyError(ChaosProbeException):
    """Raised when a service fails health check prior to experiment execution."""
    pass


class ExperimentNotFoundError(ChaosProbeException):
    """Raised when a requested experiment does not exist."""
    pass


class ExperimentConflictError(ChaosProbeException):
    """Raised when an experiment is already running on the target service."""
    pass


class ExperimentValidationError(ChaosProbeException):
    """Raised when experiment configuration or safety parameters are invalid."""
    pass


class ExperimentExecutionError(ChaosProbeException):
    """Raised when an experiment execution encounters an unrecoverable failure."""
    pass


class FaultInjectionError(ChaosProbeException):
    """Raised when a fault strategy fails to apply its injection."""
    pass


class FaultRollbackError(ChaosProbeException):
    """Raised when a fault fails to clean up or restore the target state."""
    pass


class SafetyThresholdExceededError(ChaosProbeException):
    """Raised when an active experiment violates a configured safety threshold."""
    pass


class TargetNotAuthorizedError(ChaosProbeException):
    """Raised when attempting to target a service/container not authorized for testing."""
    pass


class EmergencyStopTriggeredError(ChaosProbeException):
    """Raised when an experiment is halted by operator emergency stop."""
    pass
