import re
from typing import Any
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.core.exceptions import FaultInjectionError, FaultRollbackError
from app.core.logging import logger

SAFE_INTERFACE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


class NetworkAdapter:
    """Manages traffic control (tc / netem) inside target container network namespaces."""

    def __init__(self, docker_adapter: DockerAdapter):
        self.docker_adapter = docker_adapter

    def _validate_interface(self, interface: str) -> str:
        if not SAFE_INTERFACE_PATTERN.match(interface):
            raise FaultInjectionError(f"Invalid network interface name: '{interface}'")
        return interface

    def add_latency(
        self,
        container_id: str,
        latency_ms: int,
        jitter_ms: int = 0,
        interface: str = "eth0",
    ) -> bool:
        """Injects network latency with optional jitter using Linux netem."""
        if latency_ms <= 0 or latency_ms > 60000:
            raise FaultInjectionError(f"Latency {latency_ms}ms outside permitted range (1-60000ms)")
        if jitter_ms < 0 or jitter_ms > latency_ms:
            raise FaultInjectionError(f"Jitter {jitter_ms}ms must be between 0 and latency")

        valid_iface = self._validate_interface(interface)

        # First clean any existing netem rule to ensure idempotent application
        self.remove_netem(container_id, interface=valid_iface, ignore_errors=True)

        cmd = [
            "tc", "qdisc", "add", "dev", valid_iface, "root", "netem",
            "delay", f"{latency_ms}ms",
        ]
        if jitter_ms > 0:
            cmd.extend([f"{jitter_ms}ms", "distribution", "normal"])

        logger.info(f"Applying network latency {latency_ms}ms (jitter={jitter_ms}ms) to {container_id}:{valid_iface}")
        code, out = self.docker_adapter.exec_command(container_id, cmd)
        if code != 0:
            # Fallback or check for tc absence
            if "RTNETLINK answers: Operation not permitted" in out:
                raise FaultInjectionError(
                    f"Container {container_id} lacks NET_ADMIN capability required for tc netem"
                )
            logger.warning(f"tc command exited with {code}: {out}")
            # If in dry-run or mock mode, allow
            if not self.docker_adapter.dry_run and self.docker_adapter.client:
                raise FaultInjectionError(f"Failed to inject latency into {container_id}: {out}")

        return True

    def add_packet_loss(
        self,
        container_id: str,
        loss_percent: float,
        interface: str = "eth0",
    ) -> bool:
        """Injects packet loss using Linux netem."""
        if not (0.1 <= loss_percent <= 100.0):
            raise FaultInjectionError(f"Packet loss {loss_percent}% outside range (0.1% - 100%)")

        valid_iface = self._validate_interface(interface)
        self.remove_netem(container_id, interface=valid_iface, ignore_errors=True)

        cmd = [
            "tc", "qdisc", "add", "dev", valid_iface, "root", "netem",
            "loss", f"{loss_percent:.1f}%",
        ]

        logger.info(f"Applying packet loss {loss_percent}% to {container_id}:{valid_iface}")
        code, out = self.docker_adapter.exec_command(container_id, cmd)
        if code != 0:
            if not self.docker_adapter.dry_run and self.docker_adapter.client:
                raise FaultInjectionError(f"Failed to inject packet loss into {container_id}: {out}")

        return True

    def remove_netem(
        self,
        container_id: str,
        interface: str = "eth0",
        ignore_errors: bool = False,
    ) -> bool:
        """Removes all netem traffic control rules from the interface."""
        valid_iface = self._validate_interface(interface)
        cmd = ["tc", "qdisc", "del", "dev", valid_iface, "root", "netem"]

        logger.info(f"Removing netem rules from {container_id}:{valid_iface}")
        code, out = self.docker_adapter.exec_command(container_id, cmd)
        # code 2 or 'No such file or directory' often means no qdisc was present, which is fine
        if code != 0 and not ignore_errors:
            if "Cannot find device" in out or "No such file" in out:
                return True
            if not self.docker_adapter.dry_run and self.docker_adapter.client:
                logger.error(f"Failed to rollback netem on {container_id}: {out}")
                raise FaultRollbackError(f"Rollback failed for network fault on {container_id}: {out}")

        return True

    def verify_netem(self, container_id: str, interface: str = "eth0") -> dict[str, Any]:
        """Queries active qdisc rules on interface."""
        valid_iface = self._validate_interface(interface)
        cmd = ["tc", "qdisc", "show", "dev", valid_iface]
        code, out = self.docker_adapter.exec_command(container_id, cmd)
        has_netem = "netem" in out
        return {
            "has_netem": has_netem,
            "raw_output": out.strip(),
            "interface": valid_iface,
        }
