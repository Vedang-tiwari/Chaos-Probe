from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class CPUStressFault(BaseFaultStrategy):
    """Simulates CPU resource exhaustion via container CPU quota throttling or bounded stress workers."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()

    @property
    def fault_type(self) -> str:
        return "cpu_stress"

    @property
    def description(self) -> str:
        return "Injects CPU resource constraints by throttling container quotas or generating synthetic load."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        cpu_percent = config.get("cpu_percent", 80)
        if not isinstance(cpu_percent, (int, float)) or not (10 <= cpu_percent <= 100):
            raise ExperimentValidationError("cpu_percent must be a number between 10 and 100")

        workers = config.get("workers", 1)
        if not isinstance(workers, int) or not (1 <= workers <= 16):
            raise ExperimentValidationError("workers must be an integer between 1 and 16")

        duration = config.get("duration_seconds", 30)
        if duration <= 0 or duration > 300:
            raise ExperimentValidationError("duration_seconds must be between 1 and 300")

        return {
            "cpu_percent": int(cpu_percent),
            "workers": int(workers),
            "duration_seconds": int(duration),
        }

    async def apply(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            raise FaultInjectionError("CPUStressFault requires a target container_id.")

        validated = self.validate_configuration(context.configuration)
        container_id = context.target_container_id

        # Calculate CPU quota (period is typically 100,000 microseconds = 100ms)
        # For a quota constrained to cpu_percent:
        period = 100000
        quota = int(period * (validated["cpu_percent"] / 100.0))

        logger.info(f"Throttling CPU quota for container {container_id} to {quota}us (period={period}us)")
        success = self.docker_adapter.update_resources(
            container_id=container_id,
            cpu_quota=quota,
        )
        context.state["initial_cpu_quota"] = 0  # 0 indicates unrestricted default
        context.state["cpu_throttled"] = success
        return success

    async def verify(self, context: FaultContext) -> bool:
        return context.state.get("cpu_throttled", False)

    async def rollback(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            return True

        container_id = context.target_container_id
        initial_quota = context.state.get("initial_cpu_quota", 0)

        logger.info(f"Restoring CPU quota for container {container_id} to {initial_quota}")
        try:
            self.docker_adapter.update_resources(
                container_id=container_id,
                cpu_quota=initial_quota,
            )
            context.state["cpu_throttled"] = False
            return True
        except Exception as exc:
            logger.error(f"Failed to rollback CPU quota for {container_id}: {exc}")
            return False

    async def cleanup(self, context: FaultContext) -> bool:
        return await self.rollback(context)
