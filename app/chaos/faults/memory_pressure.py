from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class MemoryPressureFault(BaseFaultStrategy):
    """Simulates memory resource constraints on the target container."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()

    @property
    def fault_type(self) -> str:
        return "memory_pressure"

    @property
    def description(self) -> str:
        return "Constrains container memory limits to evaluate degradation and out-of-memory behavior."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        alloc_mb = config.get("allocation_mb", config.get("memory_limit_mb", 256))
        if not isinstance(alloc_mb, (int, float)) or not (32 <= alloc_mb <= 4096):
            raise ExperimentValidationError("allocation_mb must be an integer between 32 and 4096 MB")

        duration = config.get("duration_seconds", 30)
        if duration <= 0 or duration > 300:
            raise ExperimentValidationError("duration_seconds must be between 1 and 300")

        return {
            "allocation_mb": int(alloc_mb),
            "duration_seconds": int(duration),
        }

    async def apply(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            raise FaultInjectionError("MemoryPressureFault requires a target container_id.")

        validated = self.validate_configuration(context.configuration)
        container_id = context.target_container_id
        mem_limit_bytes = validated["allocation_mb"] * 1024 * 1024

        logger.info(f"Constraining memory limit for container {container_id} to {validated['allocation_mb']}MB")
        success = self.docker_adapter.update_resources(
            container_id=container_id,
            mem_limit=mem_limit_bytes,
        )
        context.state["initial_mem_limit"] = 0  # 0 indicates unrestricted default
        context.state["memory_constrained"] = success
        return success

    async def verify(self, context: FaultContext) -> bool:
        return context.state.get("memory_constrained", False)

    async def rollback(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            return True

        container_id = context.target_container_id
        initial_limit = context.state.get("initial_mem_limit", 0)

        logger.info(f"Restoring memory limit for container {container_id} to {initial_limit}")
        try:
            self.docker_adapter.update_resources(
                container_id=container_id,
                mem_limit=initial_limit,
            )
            context.state["memory_constrained"] = False
            return True
        except Exception as exc:
            logger.error(f"Failed to rollback memory limit for {container_id}: {exc}")
            return False

    async def cleanup(self, context: FaultContext) -> bool:
        return await self.rollback(context)
