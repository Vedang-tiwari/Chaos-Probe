from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.adapters.network_adapter import NetworkAdapter
from app.chaos.base import BaseFaultStrategy, FaultContext
from app.core.exceptions import ExperimentValidationError, FaultInjectionError
from app.core.logging import logger


class PacketLossFault(BaseFaultStrategy):
    """Introduces controlled network packet loss to simulate dropped packets."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()
        self.network_adapter = NetworkAdapter(self.docker_adapter)

    @property
    def fault_type(self) -> str:
        return "packet_loss"

    @property
    def description(self) -> str:
        return "Simulates network instability by dropping a percentage of transmitted packets."

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        loss = config.get("loss_percentage", config.get("percentage"))
        if loss is None or not isinstance(loss, (int, float)) or not (0.1 <= loss <= 100.0):
            raise ExperimentValidationError("loss_percentage must be a number between 0.1 and 100.0")

        duration = config.get("duration_seconds", 30)
        if duration <= 0 or duration > 300:
            raise ExperimentValidationError("duration_seconds must be between 1 and 300")

        return {
            "loss_percentage": float(loss),
            "duration_seconds": int(duration),
            "interface": config.get("interface", "eth0"),
        }

    async def apply(self, context: FaultContext) -> bool:
        if not context.target_container_id:
            raise FaultInjectionError("PacketLossFault requires a registered container_id target.")

        validated = self.validate_configuration(context.configuration)
        success = self.network_adapter.add_packet_loss(
            container_id=context.target_container_id,
            loss_percent=validated["loss_percentage"],
            interface=validated["interface"],
        )
        context.state["packet_loss_applied"] = success
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
            context.state["packet_loss_applied"] = False
            return True
        except Exception as exc:
            logger.error(f"Rollback failed for packet loss on {context.target_container_id}: {exc}")
            return False

    async def cleanup(self, context: FaultContext) -> bool:
        return await self.rollback(context)
