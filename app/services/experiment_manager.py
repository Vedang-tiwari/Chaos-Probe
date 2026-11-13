import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.chaos.executor import ExperimentExecutor
from app.chaos.safety_controller import default_safety_controller
from app.core.config import get_settings
from app.core.exceptions import (
    ChaosProbeException,
    ExperimentConflictError,
    ExperimentNotFoundError,
    ServiceNotFoundError,
)
from app.core.logging import logger
from app.database.models.experiment import Experiment
from app.database.models.metrics import ExperimentEvent, ExperimentMetric
from app.database.models.service import Service
from app.database.session import SessionLocal
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentStatusResponse,
)


class ExperimentManager:
    """Manages experiment persistence, queuing, execution dispatch, and lifecycle state queries."""

    # Active running executor references: experiment_id -> ExperimentExecutor
    _active_executors: Dict[uuid.UUID, ExperimentExecutor] = {}

    def __init__(self, db: Session):
        self.db = db

    def create_experiment(self, exp_in: ExperimentCreate) -> Experiment:
        """Validates target service exists and registers a new experiment record in CREATED state."""
        service = self.db.get(Service, exp_in.service_id)
        if not service:
            raise ServiceNotFoundError(f"Target service with id '{exp_in.service_id}' does not exist.")

        experiment = Experiment(
            name=exp_in.name,
            service_id=exp_in.service_id,
            fault_type=exp_in.fault_type,
            configuration={
                **exp_in.configuration,
                "baseline_duration_seconds": exp_in.baseline_duration_seconds,
                "recovery_window_seconds": exp_in.recovery_window_seconds,
                "safety_thresholds": exp_in.safety_thresholds,
            },
            status="CREATED",
            duration_seconds=exp_in.duration_seconds,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)
        logger.info(f"Created experiment {experiment.name} (id={experiment.id}) in CREATED state.")
        return experiment

    def get_by_id(self, experiment_id: uuid.UUID) -> Experiment:
        experiment = self.db.get(Experiment, experiment_id)
        if not experiment:
            raise ExperimentNotFoundError(f"Experiment with id '{experiment_id}' was not found.")
        return experiment

    def list_experiments(
        self,
        service_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Experiment]:
        stmt = select(Experiment)
        if service_id:
            stmt = stmt.where(Experiment.service_id == service_id)
        if status:
            stmt = stmt.where(Experiment.status == status)
        stmt = stmt.limit(limit).offset(offset).order_by(Experiment.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def start_experiment(self, experiment_id: uuid.UUID) -> Experiment:
        """Dispatches an experiment for execution."""
        experiment = self.get_by_id(experiment_id)
        if experiment.status not in ("CREATED", "FAILED", "ABORTED"):
            raise ExperimentConflictError(
                f"Experiment {experiment_id} is in status '{experiment.status}' and cannot be started."
            )

        # Launch async task in background
        asyncio.create_task(self._run_async_executor(experiment_id))
        return experiment

    @classmethod
    async def _run_async_executor(cls, experiment_id: uuid.UUID) -> None:
        """Background coroutine that handles executor lifecycle with an isolated session."""
        db = SessionLocal()
        executor = ExperimentExecutor(db=db)
        cls._active_executors[experiment_id] = executor
        try:
            await executor.execute(experiment_id)
        finally:
            cls._active_executors.pop(experiment_id, None)
            db.close()

    def abort_experiment(self, experiment_id: uuid.UUID, reason: str = "User requested abort") -> Experiment:
        """Signals active running executor to abort cleanly."""
        experiment = self.get_by_id(experiment_id)
        if experiment_id in self._active_executors:
            executor = self._active_executors[experiment_id]
            executor.request_abort(reason)
            logger.info(f"Signaled active executor for experiment {experiment_id} to abort.")
        else:
            experiment.status = "ABORTED"
            experiment.abort_reason = reason
            experiment.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(experiment)

        return experiment

    def get_status(self, experiment_id: uuid.UUID) -> ExperimentStatusResponse:
        experiment = self.get_by_id(experiment_id)
        is_active = experiment.status in ("VALIDATING", "BASELINE_COLLECTION", "RUNNING", "FAULT_INJECTED", "OBSERVING", "RECOVERING")
        elapsed = 0.0
        if experiment.started_at:
            started = experiment.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            end = experiment.completed_at or datetime.now(timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            elapsed = (end - started).total_seconds()

        return ExperimentStatusResponse(
            experiment_id=experiment.id,
            status=experiment.status,
            phase=experiment.status.lower() if is_active else None,
            elapsed_seconds=round(elapsed, 1),
            abort_reason=experiment.abort_reason,
            is_active=is_active,
        )

    def get_metrics(self, experiment_id: uuid.UUID, phase: Optional[str] = None) -> List[ExperimentMetric]:
        self.get_by_id(experiment_id)
        stmt = select(ExperimentMetric).where(ExperimentMetric.experiment_id == experiment_id)
        if phase:
            stmt = stmt.where(ExperimentMetric.phase == phase)
        stmt = stmt.order_by(ExperimentMetric.timestamp.asc())
        return list(self.db.scalars(stmt).all())

    def get_events(self, experiment_id: uuid.UUID) -> List[ExperimentEvent]:
        self.get_by_id(experiment_id)
        stmt = select(ExperimentEvent).where(ExperimentEvent.experiment_id == experiment_id).order_by(ExperimentEvent.timestamp.asc())
        return list(self.db.scalars(stmt).all())
