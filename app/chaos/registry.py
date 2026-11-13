from typing import Any, Dict, Type
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.base import BaseFaultStrategy
from app.chaos.faults.container_kill import ContainerKillFault
from app.chaos.faults.cpu_stress import CPUStressFault
from app.chaos.faults.memory_pressure import MemoryPressureFault
from app.chaos.faults.network_latency import NetworkLatencyFault
from app.chaos.faults.packet_loss import PacketLossFault
from app.chaos.faults.request_timeout import RequestTimeoutFault
from app.chaos.faults.service_unavailable import ServiceUnavailableFault
from app.core.exceptions import ExperimentValidationError


class FaultRegistry:
    """Registry maintaining available fault strategies and their configuration metadata."""

    def __init__(self, docker_adapter: DockerAdapter | None = None):
        self.docker_adapter = docker_adapter or DockerAdapter()
        self._strategies: Dict[str, BaseFaultStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        defaults = [
            NetworkLatencyFault(self.docker_adapter),
            PacketLossFault(self.docker_adapter),
            CPUStressFault(self.docker_adapter),
            MemoryPressureFault(self.docker_adapter),
            ContainerKillFault(self.docker_adapter),
            ServiceUnavailableFault(self.docker_adapter),
            RequestTimeoutFault(self.docker_adapter),
        ]
        for strategy in defaults:
            self._strategies[strategy.fault_type] = strategy

    def get_strategy(self, fault_type: str) -> BaseFaultStrategy:
        """Retrieves an instantiated strategy for the given fault_type key."""
        if fault_type not in self._strategies:
            raise ExperimentValidationError(
                f"Unsupported fault type '{fault_type}'. Available: {list(self._strategies.keys())}"
            )
        return self._strategies[fault_type]

    def list_faults(self) -> list[dict[str, Any]]:
        """Returns catalog of all registered fault types with descriptions."""
        return [
            {
                "fault_type": name,
                "description": strategy.description,
            }
            for name, strategy in self._strategies.items()
        ]

    def get_fault_info(self, fault_type: str) -> dict[str, Any]:
        """Returns detailed parameter schema and description for a specific fault."""
        strategy = self.get_strategy(fault_type)
        return {
            "fault_type": strategy.fault_type,
            "description": strategy.description,
        }


default_fault_registry = FaultRegistry()
