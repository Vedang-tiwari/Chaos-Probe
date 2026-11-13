from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class ServiceUnavailableFault(BaseFaultStrategy):
    """Simulates dependency or service outage by pausing container execution."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()

    @property
    def fault_type(self) -> str:
        return "service_unavailable"

    @property
    def description(self) -> str:
        return "Simulates complete service or dependency unavailability by suspending container processes."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        duration = config.get("duration_seconds", 30)
        target_dependency = config.get("target_dependency")

        return {
            "target_dependency": target_dependency,
            "duration_seconds": int(duration),
        }

    async def apply(self, context: FaultContext) -> bool:
        target_container = context.configuration.get("target_dependency") or context.target_container_id
        if not target_container:
            raise FaultInjectionError("ServiceUnavailableFault requires a target container_id or target_dependency.")

        logger.info(f"Pausing container {target_container} to simulate service unavailability")
        success = self.docker_adapter.pause_container(target_container)
        context.state["container_paused"] = success
        context.state["paused_container_id"] = target_container
        return success

    async def verify(self, context: FaultContext) -> bool:
        return context.state.get("container_paused", False)

    async def rollback(self, context: FaultContext) -> bool:
        target_container = context.state.get("paused_container_id") or context.target_container_id
        if not target_container:
            return True

        logger.info(f"Unpausing container {target_container}")
        try:
            self.docker_adapter.unpause_container(target_container)
            context.state["container_paused"] = False
            return True
        except Exception as exc:
            logger.error(f"Failed to unpause container {target_container}: {exc}")
            return False

    async def cleanup(self, context: FaultContext) -> bool:
        return await self.rollback(context)
