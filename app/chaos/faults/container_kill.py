from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class ContainerKillFault(BaseFaultStrategy):
    """Simulates unexpected container crashes or abrupt terminations."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()

    @property
    def fault_type(self) -> str:
        return "container_kill"

    @property
    def description(self) -> str:
        return "Simulates container death (SIGTERM/SIGKILL) and measures automatic recovery time."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        signal = config.get("signal", "SIGTERM").upper()
        if signal not in ("SIGTERM", "SIGKILL", "STOP"):
            raise ExperimentValidationError("signal must be one of: SIGTERM, SIGKILL, STOP")

        restart = config.get("restart", True)
        duration = config.get("duration_seconds", 30)

        return {
            "signal": signal,
            "restart": bool(restart),
            "duration_seconds": int(duration),
        }

    async def apply(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            raise FaultInjectionError("ContainerKillFault requires a target container_id.")

        validated = self.validate_configuration(context.configuration)
        container_id = context.target_container_id

        logger.info(f"Terminating container {container_id} with signal {validated['signal']}")
        success = self.docker_adapter.stop_container(container_id, timeout=2)
        context.state["container_terminated"] = success
        return success

    async def verify(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            return False
        if self.docker_adapter.dry_run:
            return True

        # Confirms container is no longer running
        return not self.docker_adapter.is_container_running(context.target_container_id)

    async def rollback(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            return True

        container_id = context.target_container_id
        logger.info(f"Restoring / restarting container {container_id}")
        success = self.docker_adapter.start_container(container_id)
        if success:
            context.state["container_terminated"] = False
        return success

    async def cleanup(self, context: FaultContext) -> bool:
        return await self.rollback(context)
