import uuid
from unittest.mock import AsyncMock, patch
import pytest
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.executor import ExperimentExecutor
from app.monitoring.health_checker import HealthCheckResult
from app.schemas.experiment import ExperimentCreate
from app.services.experiment_manager import ExperimentManager


@pytest.mark.asyncio
async def test_complete_experiment_lifecycle_execution(db_session):
    # 1. Register a test service
    from app.schemas.service import ServiceCreate
    from app.services.service_registry import ServiceRegistry

    service_reg = ServiceRegistry(db=db_session)
    service = service_reg.register_service(
        ServiceCreate(
            name="order-service",
            base_url="http://order:8000",
            health_check_url="http://order:8000/health",
            container_id="order_container_test",
        )
    )

    # 2. Create experiment
    exp_mgr = ExperimentManager(db=db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="order-latency-test",
            service_id=service.id,
            fault_type="network_latency",
            configuration={"latency_ms": 300, "jitter_ms": 20},
            duration_seconds=2,
            baseline_duration_seconds=1,
            recovery_window_seconds=1,
        )
    )
    assert exp.status == "CREATED"

    # 3. Execute using mock health probes and dry-run docker adapter
    mock_docker = DockerAdapter(dry_run=True)
    executor = ExperimentExecutor(db=db_session)
    executor.fault_registry.docker_adapter = mock_docker

    # Mock health checker to return healthy during baseline/recovery, and degraded during injection
    async def mock_probe(service_id, service_name, health_check_url):
        phase = executor.db.get(type(exp), exp.id).status
        if phase in ("FAULT_INJECTED", "OBSERVING"):
            return HealthCheckResult(service_id, service_name, "DEGRADED", 200, latency_ms=320.0)
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=25.0)

    executor.health_checker.check_http_endpoint = mock_probe

    # Run complete lifecycle
    completed_exp = await executor.execute(exp.id)
    assert completed_exp.status == "COMPLETED"
    assert completed_exp.started_at is not None
    assert completed_exp.completed_at is not None

    # 4. Verify metrics were captured across phases
    metrics = exp_mgr.get_metrics(exp.id)
    assert len(metrics) > 0
    phases = {m.phase for m in metrics}
    assert "baseline" in phases
    assert "injection" in phases
    assert "recovery" in phases

    # 5. Verify events recorded
    events = exp_mgr.get_events(exp.id)
    assert len(events) >= 4
    event_types = [e.event_type for e in events]
    assert "BASELINE_START" in event_types
    assert "FAULT_APPLIED" in event_types
    assert "RECOVERY_START" in event_types


def test_api_experiment_crud_and_abort(client, db_session):
    # 1. Register service first
    svc_res = client.post(
        "/api/v1/services",
        json={
            "name": "cart-service",
            "base_url": "http://cart:8000",
            "health_check_url": "http://cart:8000/health",
        },
    )
    assert svc_res.status_code == 201
    service_id = svc_res.json()["id"]

    # 2. Create experiment via API
    create_payload = {
        "name": "cart-cpu-stress",
        "service_id": service_id,
        "fault_type": "cpu_stress",
        "configuration": {"cpu_percent": 80, "workers": 2},
        "duration_seconds": 30,
        "baseline_duration_seconds": 5,
        "recovery_window_seconds": 5,
    }
    exp_res = client.post("/api/v1/experiments", json=create_payload)
    assert exp_res.status_code == 201, exp_res.text
    exp_data = exp_res.json()
    exp_id = exp_data["id"]
    assert exp_data["status"] == "CREATED"

    # 3. Query status
    status_res = client.get(f"/api/v1/experiments/{exp_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "CREATED"

    # 4. Abort experiment
    abort_res = client.post(
        f"/api/v1/experiments/{exp_id}/abort",
        json={"reason": "Operator cancelled before execution"},
    )
    assert abort_res.status_code == 200
    assert abort_res.json()["status"] == "ABORTED"
    assert abort_res.json()["abort_reason"] == "Operator cancelled before execution"

    # 5. List experiments
    list_res = client.get(f"/api/v1/experiments?service_id={service_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_api_admin_emergency_stop(client):
    # Missing admin key fails with 403
    res_no_auth = client.post("/api/v1/admin/emergency-stop", json={"reason": "Test emergency"})
    assert res_no_auth.status_code == 403

    # With admin key succeeds
    headers = {"X-API-Key": "test-secret-key"}
    res_auth = client.post(
        "/api/v1/admin/emergency-stop",
        json={"reason": "Critical outage detected"},
        headers=headers,
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "EMERGENCY_STOP_ACTIVATED"

    # Reset
    reset_res = client.post("/api/v1/admin/reset-emergency-stop", headers=headers)
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "NORMAL_OPERATION_RESUMED"


@pytest.mark.asyncio
async def test_experiment_aborts_on_safety_threshold_breach(db_session):
    from app.schemas.service import ServiceCreate
    from app.services.service_registry import ServiceRegistry

    service_reg = ServiceRegistry(db=db_session)
    service = service_reg.register_service(
        ServiceCreate(
            name="fragile-service",
            base_url="http://fragile:8000",
            health_check_url="http://fragile:8000/health",
            container_id="fragile_container",
        )
    )

    exp_mgr = ExperimentManager(db=db_session)
    exp = exp_mgr.create_experiment(
        ExperimentCreate(
            name="fragile-threshold-test",
            service_id=service.id,
            fault_type="network_latency",
            configuration={"latency_ms": 200},
            duration_seconds=5,
            baseline_duration_seconds=1,
            safety_thresholds={"max_error_rate": 0.10, "max_latency_ms": 1000.0},
        )
    )

    executor = ExperimentExecutor(db=db_session)
    executor.fault_registry.docker_adapter = DockerAdapter(dry_run=True)

    # Health check returns 100% UNHEALTHY during injection
    async def failing_probe(service_id, service_name, health_check_url):
        phase = executor.db.get(type(exp), exp.id).status
        if phase in ("FAULT_INJECTED", "OBSERVING"):
            return HealthCheckResult(service_id, service_name, "UNHEALTHY", 500, latency_ms=1500.0)
        return HealthCheckResult(service_id, service_name, "HEALTHY", 200, latency_ms=20.0)

    executor.health_checker.check_http_endpoint = failing_probe

    aborted_exp = await executor.execute(exp.id)
    assert aborted_exp.status == "ABORTED"
    assert "exceeded critical safety threshold" in aborted_exp.abort_reason
