from typing import Optional
from prometheus_client import Counter, Gauge, Histogram

# Platform Metrics
EXPERIMENTS_TOTAL = Counter(
    "chaos_probe_experiments_total",
    "Total count of initiated chaos experiments",
    ["status"],
)

EXPERIMENTS_RUNNING = Gauge(
    "chaos_probe_experiments_running",
    "Current number of actively running experiments",
)

FAULT_INJECTIONS_TOTAL = Counter(
    "chaos_probe_fault_injections_total",
    "Total number of injected faults",
    ["fault_type"],
)

ACTIVE_FAULTS = Gauge(
    "chaos_probe_active_faults",
    "Number of currently active fault injections",
    ["fault_type"],
)

EXPERIMENT_DURATION_SECONDS = Histogram(
    "chaos_probe_experiment_duration_seconds",
    "Total elapsed duration of experiments in seconds",
    buckets=[5, 10, 15, 30, 45, 60, 90, 120, 180, 240, 300],
)

ROLLBACK_FAILURES_TOTAL = Counter(
    "chaos_probe_rollback_failures_total",
    "Total number of unrecovered rollback or cleanup failures",
    ["fault_type"],
)

# Service Health & Resilience Observations
SERVICE_AVAILABILITY = Gauge(
    "chaos_probe_service_availability",
    "Latest availability score (0.0 to 1.0) of target service",
    ["service"],
)

REQUEST_LATENCY_SECONDS = Histogram(
    "chaos_probe_request_latency_seconds",
    "Latency observed during health and resilience probes in seconds",
    ["service", "phase"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_ERRORS_TOTAL = Counter(
    "chaos_probe_request_errors_total",
    "Count of probe errors encountered by phase",
    ["service", "phase"],
)

RECOVERY_DURATION_SECONDS = Histogram(
    "chaos_probe_recovery_duration_seconds",
    "Observed duration in seconds for target service to return to healthy state",
    ["service"],
    buckets=[1, 2, 5, 10, 15, 20, 30, 45, 60],
)


class MetricsTracker:
    """Helper methods to record metrics with thread safety and standardized labels."""

    @staticmethod
    def experiment_started() -> None:
        EXPERIMENTS_RUNNING.inc()

    @staticmethod
    def experiment_finished(status: str, duration_seconds: float) -> None:
        EXPERIMENTS_RUNNING.dec()
        EXPERIMENTS_TOTAL.labels(status=status).inc()
        EXPERIMENT_DURATION_SECONDS.observe(duration_seconds)

    @staticmethod
    def fault_applied(fault_type: str) -> None:
        FAULT_INJECTIONS_TOTAL.labels(fault_type=fault_type).inc()
        ACTIVE_FAULTS.labels(fault_type=fault_type).inc()

    @staticmethod
    def fault_removed(fault_type: str) -> None:
        ACTIVE_FAULTS.labels(fault_type=fault_type).dec()

    @staticmethod
    def rollback_failed(fault_type: str) -> None:
        ROLLBACK_FAILURES_TOTAL.labels(fault_type=fault_type).inc()

    @staticmethod
    def record_probe(
        service_name: str,
        latency_seconds: float,
        is_healthy: bool,
        phase: str,
    ) -> None:
        REQUEST_LATENCY_SECONDS.labels(service=service_name, phase=phase).observe(latency_seconds)
        if not is_healthy:
            REQUEST_ERRORS_TOTAL.labels(service=service_name, phase=phase).inc()
        SERVICE_AVAILABILITY.labels(service=service_name).set(1.0 if is_healthy else 0.0)

    @staticmethod
    def record_recovery(service_name: str, recovery_seconds: float) -> None:
        RECOVERY_DURATION_SECONDS.labels(service=service_name).observe(recovery_seconds)

