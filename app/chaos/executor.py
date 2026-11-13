import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.chaos.registry import FaultRegistry, default_fault_registry
from app.chaos.rollback_manager import RollbackManager, default_rollback_manager
from app.chaos.safety_controller import SafetyController, default_safety_controller
from app.core.exceptions import (
    ChaosProbeException,
    EmergencyStopTriggeredError,
    ExperimentValidationError,
    SafetyThresholdExceededError,
    ServiceNotFoundError,
    ServiceUnhealthyError,
)
from app.core.logging import logger
from app.database.models.experiment import Experiment
from app.database.models.metrics import ExperimentEvent, ExperimentMetric
from app.database.models.service import Service
from app.monitoring.health_checker import HealthCheckResult, HealthChecker
from app.monitoring.prometheus import MetricsTracker


class ExperimentExecutor:
    """Orchestrates the 10-stage experiment lifecycle with strict safety and metric collection."""

    def __init__(
        self,
        db: Session,
        fault_registry: Optional[FaultRegistry] = None,
        safety_controller: Optional[SafetyController] = None,
        rollback_manager: Optional[RollbackManager] = None,
        health_checker: Optional[HealthChecker] = None,
    ):
        self.db = db
        self.fault_registry = fault_registry or default_fault_registry
        self.safety_controller = safety_controller or default_safety_controller
        self.rollback_manager = rollback_manager or default_rollback_manager
        self.health_checker = health_checker or HealthChecker()
        self._abort_requested = False
        self._abort_reason: Optional[str] = None

    def request_abort(self, reason: str = "User requested abort") -> None:
        """Flags the running executor to abort cleanly at the next checkpoint."""
        self._abort_requested = True
        self._abort_reason = reason
        logger.warning(f"Executor received abort signal: {reason}")

    def _record_event(self, experiment_id: uuid.UUID, event_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        event = ExperimentEvent(
            experiment_id=experiment_id,
            event_type=event_type,
            message=message,
            event_metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.commit()

    def _record_metric(self, experiment_id: uuid.UUID, metric_name: str, value: float, phase: str) -> None:
        metric = ExperimentMetric(
            experiment_id=experiment_id,
            metric_name=metric_name,
            metric_value=value,
            phase=phase,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(metric)

    def _set_status(self, experiment: Experiment, status: str, abort_reason: str | None = None) -> None:
        experiment.status = status
        if abort_reason:
            experiment.abort_reason = abort_reason
        self.db.commit()
        self.db.refresh(experiment)
        logger.info(f"Experiment {experiment.id} transitioned to state: {status}")

    async def execute(self, experiment_id: uuid.UUID) -> Experiment:
        experiment = self.db.get(Experiment, experiment_id)
        if not experiment:
            raise ChaosProbeException(f"Experiment {experiment_id} not found in database.")

        service = self.db.get(Service, experiment.service_id)
        if not service:
            raise ServiceNotFoundError(f"Target service {experiment.service_id} not found.")

        strategy = self.fault_registry.get_strategy(experiment.fault_type)
        cfg = experiment.configuration or {}
        duration = experiment.duration_seconds
        baseline_duration = cfg.get("baseline_duration_seconds", 5)
        recovery_window = cfg.get("recovery_window_seconds", 5)
        thresholds = cfg.get("safety_thresholds", {
            "max_error_rate": 0.50,
            "max_latency_ms": 5000.0,
            "min_availability": 0.50,
        })

        context = FaultContext(
            experiment_id=experiment.id,
            service_id=service.id,
            target_container_id=service.container_id,
            target_base_url=service.base_url,
            target_health_url=service.health_check_url,
            configuration=cfg,
        )

        lock_acquired = False
        fault_applied = False

        try:
            # 1. State: VALIDATING
            self._set_status(experiment, "VALIDATING")
            self._record_event(experiment.id, "LIFECYCLE_CHANGE", "Validating target service and safety boundaries.")

            self.safety_controller.validate_safety_boundaries(service, duration, cfg)
            strategy.validate_configuration(cfg)

            self.safety_controller.acquire_target_lock(service.id, experiment.id)
            lock_acquired = True

            # Pre-flight health probe
            initial_probe = await self.health_checker.check_http_endpoint(
                service_id=service.id,
                service_name=service.name,
                health_check_url=service.health_check_url,
            )
            if not initial_probe.is_healthy:
                logger.warning(f"Target service {service.name} is currently {initial_probe.status} ({initial_probe.error_message})")

            experiment.started_at = datetime.now(timezone.utc)
            self.db.commit()
            MetricsTracker.experiment_started()

            # 2. State: BASELINE_COLLECTION
            self._set_status(experiment, "BASELINE_COLLECTION")
            self._record_event(experiment.id, "BASELINE_START", f"Collecting baseline for {baseline_duration}s.")

            baseline_end = time.time() + baseline_duration
            while time.time() < baseline_end:
                if self._abort_requested or self.safety_controller.is_emergency_stopped:
                    raise EmergencyStopTriggeredError(self._abort_reason or self.safety_controller.emergency_stop_reason or "Abort requested")

                probe = await self.health_checker.check_http_endpoint(service.id, service.name, service.health_check_url)
                if probe.latency_ms is not None:
                    self._record_metric(experiment.id, "latency_ms", probe.latency_ms, phase="baseline")
                    MetricsTracker.record_probe(service.name, probe.latency_ms / 1000.0, probe.is_healthy, phase="baseline")
                self._record_metric(experiment.id, "availability", 1.0 if probe.is_healthy else 0.0, phase="baseline")
                self._record_metric(experiment.id, "error_count", 0.0 if probe.is_healthy else 1.0, phase="baseline")
                self.db.commit()
                await asyncio.sleep(1.0)

            # 3. State: RUNNING -> FAULT_INJECTED
            self._set_status(experiment, "RUNNING")
            applied = await strategy.apply(context)
            if not applied:
                raise ChaosProbeException(f"Fault strategy {strategy.fault_type} failed to apply.")
            fault_applied = True
            MetricsTracker.fault_applied(strategy.fault_type)

            verified = await strategy.verify(context)
            self._set_status(experiment, "FAULT_INJECTED")
            self._record_event(experiment.id, "FAULT_APPLIED", f"Fault {strategy.fault_type} applied (verified={verified}).")

            # 4. State: OBSERVING
            self._set_status(experiment, "OBSERVING")
            injection_end = time.time() + duration
            error_count = 0
            total_probes = 0

            while time.time() < injection_end:
                if self._abort_requested or self.safety_controller.is_emergency_stopped:
                    raise EmergencyStopTriggeredError(self._abort_reason or self.safety_controller.emergency_stop_reason or "Abort requested")

                probe = await self.health_checker.check_http_endpoint(service.id, service.name, service.health_check_url)
                total_probes += 1
                if probe.status == "UNHEALTHY":
                    error_count += 1

                latency = probe.latency_ms or 0.0
                error_rate = error_count / total_probes if total_probes > 0 else 0.0
                availability = ((total_probes - error_count) / total_probes) * 100.0

                self._record_metric(experiment.id, "latency_ms", latency, phase="injection")
                self._record_metric(experiment.id, "availability", 1.0 if probe.is_healthy else 0.0, phase="injection")
                self._record_metric(experiment.id, "error_rate", error_rate, phase="injection")
                MetricsTracker.record_probe(service.name, latency / 1000.0, probe.is_healthy, phase="injection")
                self.db.commit()

                # Safety guardrail threshold evaluation
                current_metrics = {
                    "latency_ms": latency,
                    "error_rate": error_rate,
                    "availability_percentage": availability,
                }
                safe, breach_msg = self.safety_controller.evaluate_safety_thresholds(
                    experiment.id, current_metrics, thresholds
                )
                if not safe:
                    raise SafetyThresholdExceededError(breach_msg or "Safety threshold exceeded.")

                await asyncio.sleep(1.0)

            # 5. State: RECOVERING
            self._set_status(experiment, "RECOVERING")
            self._record_event(experiment.id, "RECOVERY_START", "Rolling back fault and measuring recovery.")

            rollback_ok = await self.rollback_manager.execute_rollback(strategy, context)
            fault_applied = False
            MetricsTracker.fault_removed(strategy.fault_type)
            if not rollback_ok:
                MetricsTracker.rollback_failed(strategy.fault_type)
                raise ChaosProbeException("Rollback verification failed! Service in unhealthy state.")

            # Recovery window observation
            recovery_start_time = time.time()
            recovery_end = recovery_start_time + recovery_window
            recovered = False
            while time.time() < recovery_end:
                probe = await self.health_checker.check_http_endpoint(service.id, service.name, service.health_check_url)
                if probe.latency_ms is not None:
                    self._record_metric(experiment.id, "latency_ms", probe.latency_ms, phase="recovery")
                    MetricsTracker.record_probe(service.name, probe.latency_ms / 1000.0, probe.is_healthy, phase="recovery")
                self._record_metric(experiment.id, "availability", 1.0 if probe.is_healthy else 0.0, phase="recovery")
                self.db.commit()

                if probe.is_healthy and not recovered:
                    recovered = True
                    rec_dur = time.time() - recovery_start_time
                    MetricsTracker.record_recovery(service.name, rec_dur)
                    self._record_event(experiment.id, "SERVICE_RECOVERED", f"Service returned to healthy state in {rec_dur:.2f}s.")

                await asyncio.sleep(1.0)

            # 6. State: COMPLETED
            experiment.completed_at = datetime.now(timezone.utc)
            self._set_status(experiment, "COMPLETED")
            self._record_event(experiment.id, "LIFECYCLE_CHANGE", "Experiment completed successfully.")

        except (EmergencyStopTriggeredError, SafetyThresholdExceededError) as exc:
            logger.warning(f"Experiment {experiment.id} aborted: {exc.message}")
            experiment.completed_at = datetime.now(timezone.utc)
            self._set_status(experiment, "ABORTED", abort_reason=exc.message)
            self._record_event(experiment.id, "EXPERIMENT_ABORTED", exc.message)
            if fault_applied:
                await self.rollback_manager.execute_rollback(strategy, context)

        except Exception as exc:
            logger.error(f"Experiment {experiment.id} encountered failure: {exc}", exc_info=True)
            experiment.completed_at = datetime.now(timezone.utc)
            self._set_status(experiment, "FAILED", abort_reason=str(exc))
            self._record_event(experiment.id, "EXPERIMENT_FAILED", str(exc))
            if fault_applied:
                await self.rollback_manager.execute_rollback(strategy, context)

        finally:
            dur = 0.0
            if experiment.started_at:
                started = experiment.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                dur = (datetime.now(timezone.utc) - started).total_seconds()

            MetricsTracker.experiment_finished(experiment.status, dur)
            if lock_acquired:
                self.safety_controller.release_target_lock(service.id, experiment.id)

        return experiment
