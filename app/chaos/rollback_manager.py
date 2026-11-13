from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List
import uuid
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import FaultRollbackError
from app.core.logging import logger


class RollbackFailureRecord:
    """Records an unverified or failed rollback requiring operator intervention."""

    def __init__(
        self,
        experiment_id: uuid.UUID,
        fault_type: str,
        target_container_id: str | None,
        error_message: str,
    ):
        self.experiment_id = experiment_id
        self.fault_type = fault_type
        self.target_container_id = target_container_id
        self.error_message = error_message


class RollbackManager:
    """Coordinates fault reversions, cleanup verification, and rollback failure tracking."""

    def __init__(self) -> None:
        self._unhealthy_cleanups: Dict[uuid.UUID, RollbackFailureRecord] = {}

    @property
    def unhealthy_cleanups(self) -> List[RollbackFailureRecord]:
        """Returns all targets with unresolved cleanup failures."""
        return list(self._unhealthy_cleanups.values())

    def has_unhealthy_cleanup(self, experiment_id: uuid.UUID) -> bool:
        return experiment_id in self._unhealthy_cleanups

    def clear_unhealthy_cleanup(self, experiment_id: uuid.UUID) -> None:
        """Allows an operator to mark an unhealthy cleanup as manually resolved."""
        self._unhealthy_cleanups.pop(experiment_id, None)

    async def execute_rollback(
        self,
        strategy: BaseFaultStrategy,
        context: FaultContext,
    ) -> bool:
        """Executes rollback and cleanup for a fault strategy."""
        logger.info(
            f"Executing rollback for {strategy.fault_type} on experiment {context.experiment_id}",
            extra={"experiment_id": str(context.experiment_id), "fault_type": strategy.fault_type},
        )
        rollback_success = False
        cleanup_success = False
        error_msg = None

        try:
            rollback_success = await strategy.rollback(context)
        except Exception as exc:
            error_msg = f"Exception during rollback(): {exc}"
            logger.error(error_msg, exc_info=True)

        try:
            cleanup_success = await strategy.cleanup(context)
        except Exception as exc:
            cleanup_err = f"Exception during cleanup(): {exc}"
            logger.error(cleanup_err, exc_info=True)
            if not error_msg:
                error_msg = cleanup_err

        if not (rollback_success and cleanup_success):
            if not error_msg:
                error_msg = "Rollback or cleanup returned False without explicit exception"

            failure_record = RollbackFailureRecord(
                experiment_id=context.experiment_id,
                fault_type=strategy.fault_type,
                target_container_id=context.target_container_id,
                error_message=error_msg,
            )
            self._unhealthy_cleanups[context.experiment_id] = failure_record
            logger.critical(
                f"ROLLBACK FAILURE on experiment {context.experiment_id}: {error_msg}. Operator attention required!"
            )
            return False

        # If rollback was previously unhealthy but now succeeds, clear it
        self._unhealthy_cleanups.pop(context.experiment_id, None)
        logger.info(f"Rollback and cleanup verified for {strategy.fault_type} on {context.experiment_id}")
        return True

    @asynccontextmanager
    async def managed_fault(
        self,
        strategy: BaseFaultStrategy,
        context: FaultContext,
    ) -> AsyncGenerator[None, None]:
        """Context manager guaranteeing that rollback runs whenever an experiment turn ends or fails."""
        try:
            applied = await strategy.apply(context)
            if not applied:
                raise FaultRollbackError(f"Fault strategy {strategy.fault_type} failed to apply.")
            yield
        finally:
            await self.execute_rollback(strategy, context)


default_rollback_manager = RollbackManager()

