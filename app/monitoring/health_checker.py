import time
from datetime import datetime, timezone
from typing import Any
import httpx
from app.core.logging import logger


class HealthCheckResult:
    """Encapsulates the result of a health probe against a service."""

    def __init__(
        self,
        service_id: Any,
        service_name: str,
        status: str,  # HEALTHY, UNHEALTHY, DEGRADED, UNKNOWN
        status_code: int | None = None,
        latency_ms: float | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.service_id = service_id
        self.service_name = service_name
        self.status = status
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.error_message = error_message
        self.metadata = metadata or {}
        self.checked_at = datetime.now(timezone.utc)

    @property
    def is_healthy(self) -> bool:
        return self.status == "HEALTHY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": str(self.service_id),
            "service_name": self.service_name,
            "status": self.status,
            "status_code": self.status_code,
            "latency_ms": round(self.latency_ms, 2) if self.latency_ms is not None else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "checked_at": self.checked_at.isoformat(),
        }


class HealthChecker:
    """Executes network and container health checks against target services."""

    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    async def check_http_endpoint(
        self,
        service_id: Any,
        service_name: str,
        health_check_url: str,
    ) -> HealthCheckResult:
        """Probes the service's HTTP health check endpoint."""
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(health_check_url)
                duration_ms = (time.perf_counter() - start_time) * 1000.0

                if 200 <= response.status_code < 300:
                    status = "HEALTHY"
                    error = None
                elif 500 <= response.status_code:
                    status = "UNHEALTHY"
                    error = f"HTTP {response.status_code} Internal Server Error"
                else:
                    status = "DEGRADED"
                    error = f"Unexpected HTTP status {response.status_code}"

                return HealthCheckResult(
                    service_id=service_id,
                    service_name=service_name,
                    status=status,
                    status_code=response.status_code,
                    latency_ms=duration_ms,
                    error_message=error,
                )

        except httpx.ConnectError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning(f"Connection refused to {service_name} at {health_check_url}: {exc}")
            return HealthCheckResult(
                service_id=service_id,
                service_name=service_name,
                status="UNHEALTHY",
                latency_ms=duration_ms,
                error_message=f"Connection refused: {exc}",
            )
        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning(f"Health check timed out for {service_name} at {health_check_url}")
            return HealthCheckResult(
                service_id=service_id,
                service_name=service_name,
                status="UNHEALTHY",
                latency_ms=duration_ms,
                error_message=f"Request timed out after {self.timeout_seconds}s",
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Unexpected error during health check of {service_name}: {exc}")
            return HealthCheckResult(
                service_id=service_id,
                service_name=service_name,
                status="UNKNOWN",
                latency_ms=duration_ms,
                error_message=str(exc),
            )
