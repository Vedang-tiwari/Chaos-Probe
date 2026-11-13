from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.adapters.network_adapter import NetworkAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class NetworkLatencyFault(BaseFaultStrategy):
    """Introduces controlled network latency and jitter to the target container."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()
        self.network_adapter = NetworkAdapter(self.docker_adapter)

    @property
    def fault_type(self) -> str:
        return "network_latency"

    @property
    def description(self) -> str:
        return "Simulates slow network conditions by injecting millisecond delays and jitter."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        latency_ms = config.get("latency_ms")
        if latency_ms is None or not isinstance(latency_ms, (int, float)) or latency_ms <= 0:
            raise ExperimentValidationError("latency_ms must be a positive integer > 0")

        jitter_ms = config.get("jitter_ms", 0)
        if not isinstance(jitter_ms, (int, float)) or jitter_ms < 0:
            raise ExperimentValidationError("jitter_ms must be a non-negative number")
        if jitter_ms > latency_ms:
            raise ExperimentValidationError("jitter_ms cannot exceed latency_ms")

        duration = config.get("duration_seconds", 30)
        if duration <= 0 or duration > 300:
            raise ExperimentValidationError("duration_seconds must be between 1 and 300")

        return {
            "latency_ms": int(latency_ms),
            "jitter_ms": int(jitter_ms),
            "duration_seconds": int(duration),
            "interface": config.get("interface", "eth0"),
        }

    async def apply(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            raise FaultInjectionError("NetworkLatencyFault requires a registered container_id target.")

        validated = self.validate_configuration(context.configuration)
        success = self.network_adapter.add_latency(
            container_id=context.target_container_id,
            latency_ms=validated["latency_ms"],
            jitter_ms=validated["jitter_ms"],
            interface=validated["interface"],
        )
        context.state["latency_applied"] = success
        context.state["interface"] = validated["interface"]
        return success

    async def verify(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            return False
        if self.docker_adapter.dry_run:
            return True

        iface = context.state.get("interface", "eth0")
        info = self.network_adapter.verify_netem(context.target_container_id, interface=iface)
        return info.get("has_netem", False)

    async def rollback(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            return True

        iface = context.state.get("interface", "eth0")
        try:
            self.network_adapter.remove_netem(context.target_container_id, interface=iface)
            context.state["latency_applied"] = False
            return True
        except Exception as exc:
            logger.error(f"Rollback failed for network latency on {context.target_container_id}: {exc}")
            return False

    async def cleanup(self, context: FaultContext) -> bool:
        # Idempotent cleanup calls rollback ensuring no residual rules remain
        return await self.rollback(context)
