import shutil
import subprocess
from typing import Any
from app.core.exceptions import ChaosProbeException
from app.core.logging import logger

try:
    import docker
    from docker.errors import DockerException, NotFound
except ImportError:
    docker = None
    DockerException = Exception
    NotFound = Exception


class DockerAdapter:
    """Provides controlled, isolated interactions with the Docker Engine daemon."""

    def __init__(self, client: Any = None, dry_run: bool = False):
        self.dry_run = dry_run
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        if self.dry_run or docker is None:
            return None
        try:
            self._client = docker.from_env()
            return self._client
        except Exception as exc:
            logger.warning(f"Could not connect to Docker daemon: {exc}. Operating in fallback mode.")
            self.dry_run = True
            return None

    def is_available(self) -> bool:
        """Checks if Docker API is reachable."""
        if self.dry_run:
            return False
        try:
            cli = self.client
            return cli is not None and cli.ping()
        except Exception:
            return False

    def container_exists(self, container_id: str) -> bool:
        """Verifies container existence."""
        if self.dry_run or not self.client:
            return True
        try:
            self.client.containers.get(container_id)
            return True
        except NotFound:
            return False
        except Exception as exc:
            logger.error(f"Error checking container {container_id}: {exc}")
            return False

    def is_container_running(self, container_id: str) -> bool:
        """Checks if container is in running state."""
        if self.dry_run or not self.client:
            return True
        try:
            c = self.client.containers.get(container_id)
            return c.status == "running"
        except Exception as exc:
            logger.warning(f"Failed to query running state for {container_id}: {exc}")
            return False

    def exec_command(self, container_id: str, cmd: list[str]) -> tuple[int, str]:
        """Executes a command inside the target container."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Executing inside container {container_id}: {' '.join(cmd)}")
            return 0, "[dry-run output]"

        try:
            container = self.client.containers.get(container_id)
            exec_res = container.exec_run(cmd)
            exit_code = exec_res.exit_code
            output = exec_res.output.decode("utf-8", errors="replace") if exec_res.output else ""
            return exit_code, output
        except Exception as exc:
            logger.error(f"Failed to exec {cmd} in {container_id}: {exc}")
            raise ChaosProbeException(f"Docker exec failed in {container_id}: {exc}") from exc

    def update_resources(
        self,
        container_id: str,
        cpu_quota: int | None = None,
        mem_limit: str | int | None = None,
    ) -> bool:
        """Updates container CPU quota or memory limit dynamically."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Update resources for {container_id}: cpu_quota={cpu_quota}, mem_limit={mem_limit}")
            return True

        try:
            container = self.client.containers.get(container_id)
            kwargs: dict[str, Any] = {}
            if cpu_quota is not None:
                kwargs["cpu_quota"] = cpu_quota
            if mem_limit is not None:
                kwargs["mem_limit"] = mem_limit
            container.update(**kwargs)
            return True
        except Exception as exc:
            logger.error(f"Failed to update resources for {container_id}: {exc}")
            raise ChaosProbeException(f"Resource update failed for {container_id}: {exc}") from exc

    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restarts the specified target container."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Restarting container {container_id}")
            return True

        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=timeout)
            return True
        except Exception as exc:
            logger.error(f"Failed to restart container {container_id}: {exc}")
            return False

    def stop_container(self, container_id: str, timeout: int = 5) -> bool:
        """Stops the specified target container."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Stopping container {container_id}")
            return True

        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            return True
        except Exception as exc:
            logger.error(f"Failed to stop container {container_id}: {exc}")
            return False

    def start_container(self, container_id: str) -> bool:
        """Starts the specified target container."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Starting container {container_id}")
            return True

        try:
            container = self.client.containers.get(container_id)
            container.start()
            return True
        except Exception as exc:
            logger.error(f"Failed to start container {container_id}: {exc}")
            return False

    def pause_container(self, container_id: str) -> bool:
        """Pauses all processes in the specified container."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Pausing container {container_id}")
            return True

        try:
            container = self.client.containers.get(container_id)
            container.pause()
            return True
        except Exception as exc:
            logger.error(f"Failed to pause container {container_id}: {exc}")
            return False

    def unpause_container(self, container_id: str) -> bool:
        """Unpauses all processes in the specified container."""
        if self.dry_run or not self.client:
            logger.info(f"[DRY-RUN] Unpausing container {container_id}")
            return True

        try:
            container = self.client.containers.get(container_id)
            container.unpause()
            return True
        except Exception as exc:
            logger.error(f"Failed to unpause container {container_id}: {exc}")
            return False
