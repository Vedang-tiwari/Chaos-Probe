import uuid
from datetime import datetime, timezone
import pytest
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.executor import ExperimentExecutor
from app.chaos.faults.container_kill import ContainerKillFault
from app.chaos.faults.cpu_stress import CPUStressFault
from app.chaos.faults.memory_pressure import MemoryPressureFault
from app.chaos.faults.network_latency import NetworkLatencyFault
from app.chaos.rollback_manager import RollbackManager
from app.chaos.safety_controller import SafetyController
from app.database.models.experiment import Experiment
from app.database.models.service import Service
from app.monitoring.health_checker import HealthCheckResult
from app.reports.generator import ReportGenerator
from app.schemas.experiment import ExperimentCreate
from app.services.experiment_manager import ExperimentManager
from app.services.service_registry import ServiceRegistry


def _setup_service(db_session, name: str = "payment-service") -> Service:
    reg = ServiceRegistry(db=db_session)
    from app.schemas.service import ServiceCreate
    return reg.register_service(
        ServiceCreate(
            name=name,
            base_url="http://localhost:8001",
            health_check_url="http://localhost:8001/health",
            container_id=f"{name}_container",
            environment="test",
        )
    )


# --- Scenario 1: Network Latency Injection & Recovery ---
@pytest.mark.asyncio
async def test_scenario_1_network_latency(db_session):
    service = _setup_service(db_session, "payment-svc-scenario-1")
    exp_mgr = ExperimentManager(db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="scenario-1-latency",
            service_id=service.id,
            fault_type="network_latency",
            configuration={"latency_ms": 500, "jitter_ms": 50},
            duration_seconds=2,
            baseline_duration_seconds=1,
            recovery_window_seconds=1,
        )
    )

    executor = ExperimentExecutor(db=db_session)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    async def probe(service_id=None, service_name=None, health_check_url=None, **kwargs):
        phase = executor.db.get(Experiment, exp.id).status
        if phase in ("FAULT_INJECTED", "OBSERVING"):
            return HealthCheckResult(service_id, service_name, "DEGRADED", 200, latency_ms=545.0)
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=22.0)

    executor.health_checker.check_http_endpoint = probe
    completed = await executor.execute(exp.id)

    assert completed.status == "COMPLETED"
    report = ReportGenerator(db_session).generate_report(exp.id)
    assert report.outcome in ("DEGRADED", "SURVIVED", "RECOVERED")
    assert report.maximum_latency >= 500.0


# --- Scenario 2: Controlled CPU Stress ---
@pytest.mark.asyncio
async def test_scenario_2_cpu_stress(db_session):
    service = _setup_service(db_session, "auth-svc-scenario-2")
    exp_mgr = ExperimentManager(db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="scenario-2-cpu",
            service_id=service.id,
            fault_type="cpu_stress",
            configuration={"cpu_percent": 85, "workers": 2},
            duration_seconds=2,
            baseline_duration_seconds=1,
            recovery_window_seconds=1,
        )
    )

    executor = ExperimentExecutor(db=db_session)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    async def probe(service_id=None, service_name=None, health_check_url=None, **kwargs):
        phase = executor.db.get(Experiment, exp.id).status
        if phase in ("FAULT_INJECTED", "OBSERVING"):
            return HealthCheckResult(service_id, service_name, "DEGRADED", 200, latency_ms=180.0)
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=15.0)

    executor.health_checker.check_http_endpoint = probe
    completed = await executor.execute(exp.id)
    assert completed.status == "COMPLETED"


# --- Scenario 3: Memory Pressure with Threshold Guard ---
@pytest.mark.asyncio
async def test_scenario_3_memory_pressure_guard(db_session):
    service = _setup_service(db_session, "cache-svc-scenario-3")
    exp_mgr = ExperimentManager(db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="scenario-3-memory",
            service_id=service.id,
            fault_type="memory_pressure",
            configuration={"allocation_mb": 512},
            duration_seconds=3,
            baseline_duration_seconds=1,
            recovery_window_seconds=1,
            safety_thresholds={"max_error_rate": 0.20, "max_latency_ms": 2000.0},
        )
    )

    executor = ExperimentExecutor(db=db_session)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    # Simulate OOM errors during injection that trip the safety threshold
    async def probe(service_id=None, service_name=None, health_check_url=None, **kwargs):
        phase = executor.db.get(Experiment, exp.id).status
        if phase in ("FAULT_INJECTED", "OBSERVING"):
            return HealthCheckResult(service_id, service_name, "UNHEALTHY", 503, latency_ms=2500.0)
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=20.0)

    executor.health_checker.check_http_endpoint = probe
    completed = await executor.execute(exp.id)
    assert completed.status == "ABORTED"
    assert "safety threshold" in completed.abort_reason


# --- Scenario 4: Container Crash and Failure Recovery ---
@pytest.mark.asyncio
async def test_scenario_4_container_failure_and_recovery(db_session):
    service = _setup_service(db_session, "worker-svc-scenario-4")
    exp_mgr = ExperimentManager(db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="scenario-4-container-kill",
            service_id=service.id,
            fault_type="container_kill",
            configuration={"signal": "SIGTERM", "restart": True},
            duration_seconds=2,
            baseline_duration_seconds=1,
            recovery_window_seconds=1,
            safety_thresholds={"max_error_rate": 1.0, "min_availability": 0.0},
        )
    )

    executor = ExperimentExecutor(db=db_session)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    # Down during injection, recovers when restarted in recovery phase
    async def probe(service_id=None, service_name=None, health_check_url=None, **kwargs):
        phase = executor.db.get(Experiment, exp.id).status
        if phase in ("FAULT_INJECTED", "OBSERVING"):
            return HealthCheckResult(service_id, service_name, "UNHEALTHY", 502, latency_ms=3000.0)
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=30.0)

    executor.health_checker.check_http_endpoint = probe
    completed = await executor.execute(exp.id)
    assert completed.status == "COMPLETED"

    report = ReportGenerator(db_session).generate_report(exp.id)
    assert report.outcome in ("RECOVERED", "DEGRADED")


# --- Scenario 5: Emergency Stop Verification ---
@pytest.mark.asyncio
async def test_scenario_5_emergency_stop_halts_and_reverts(db_session):
    service = _setup_service(db_session, "critical-svc-scenario-5")
    exp_mgr = ExperimentManager(db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="scenario-5-emergency",
            service_id=service.id,
            fault_type="network_latency",
            configuration={"latency_ms": 1000},
            duration_seconds=10,
            baseline_duration_seconds=2,
        )
    )

    safety = SafetyController()
    executor = ExperimentExecutor(db=db_session, safety_controller=safety)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    # Trigger emergency stop while running
    safety.trigger_emergency_stop("Operator observed secondary outage")

    aborted = await executor.execute(exp.id)
    assert aborted.status == "ABORTED"
    assert "secondary outage" in aborted.abort_reason.lower() or "emergency stop" in aborted.abort_reason.lower()


# --- Scenario 6: Rollback Failure Handling & Operator Notification ---
@pytest.mark.asyncio
async def test_scenario_6_rollback_failure_recorded(db_session):
    service = _setup_service(db_session, "target-svc-scenario-6")
    exp_mgr = ExperimentManager(db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="scenario-6-rollback-failure",
            service_id=service.id,
            fault_type="network_latency",
            configuration={"latency_ms": 200},
            duration_seconds=1,
            baseline_duration_seconds=1,
            recovery_window_seconds=1,
        )
    )

    # Create executor with a failing rollback manager
    class BrokenRollbackManager(RollbackManager):
        async def execute_rollback(self, strategy, context):
            await super().execute_rollback(strategy, context)
            # Force failure record
            self._unhealthy_cleanups[context.experiment_id] = "Failed to clean tc qdisc rules"
            return False

    broken_mgr = BrokenRollbackManager()
    executor = ExperimentExecutor(db=db_session, rollback_manager=broken_mgr)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    async def probe(service_id=None, service_name=None, health_check_url=None, **kwargs):
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=20.0)

    executor.health_checker.check_http_endpoint = probe

    failed = await executor.execute(exp.id)
    # Rollback failure must NOT mark experiment as COMPLETED
    assert failed.status == "FAILED"
    assert "Rollback verification failed" in failed.abort_reason
    assert broken_mgr.has_unhealthy_cleanup(exp.id) is True
