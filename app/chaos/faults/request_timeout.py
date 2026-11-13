from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.adapters.network_adapter import NetworkAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class RequestTimeoutFault(BaseFaultStrategy):
    """Simulates severe delays in upstream dependencies that trigger request timeouts."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()
        self.network_adapter = NetworkAdapter(self.docker_adapter)

    @property
    def fault_type(self) -> str:
        return "request_timeout"

    @property
    def description(self) -> str:
        return "Simulates delayed upstream dependency responses exceeding typical client HTTP timeout limits."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        timeout_delay_ms = config.get("timeout_delay_ms", config.get("delay_ms", 10000))
        if not isinstance(timeout_delay_ms, (int, float)) or timeout_delay_ms <= 0:
            raise ExperimentValidationError("timeout_delay_ms must be a positive integer > 0")

        duration = config.get("duration_seconds", 30)
        target_dependency = config.get("target_dependency")

        return {
            "timeout_delay_ms": int(timeout_delay_ms),
            "target_dependency": target_dependency,
            "duration_seconds": int(duration),
            "interface": config.get("interface", "eth0"),
        }

    async def apply(self, context: FaultContext) -> bool:
        target_container = context.configuration.get("target_dependency") or context.target_container_id
        if not target_container:
            raise FaultInjectionError("RequestTimeoutFault requires a target container_id.")

        validated = self.validate_configuration(context.configuration)
        success = self.network_adapter.add_latency(
            container_id=target_container,
            latency_ms=validated["timeout_delay_ms"],
            jitter_ms=0,
            interface=validated["interface"],
        )
        context.state["timeout_injected"] = success
        context.state["target_container"] = target_container
        context.state["interface"] = validated["interface"]
        return success

    async def verify(self, context: FaultContext) -> bool:
        target_container = context.state.get("target_container") or context.target_container_id
        if not target_container:
            return False
        if self.docker_adapter.dry_run:
            return True

        iface = context.state.get("interface", "eth0")
        info = self.network_adapter.verify_netem(target_container, interface=iface)
        return info.get("has_netem", False)

    async def rollback(self, context: FaultContext) -> bool:
        target_container = context.state.get("target_container") or context.target_container_id
        if not target_container:
            return True

        iface = context.state.get("interface", "eth0")
        try:
            self.network_adapter.remove_netem(target_container, interface=iface)
            context.state["timeout_injected"] = False
            return True
        except Exception as exc:
            logger.error(f"Rollback failed for request timeout on {target_container}: {exc}")
            return False

    async def cleanup(self, context: FaultContext) -> bool:
        return await self.rollback(context)

