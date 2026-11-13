import uuid
import pytest
from app.chaos.adapters.docker_adapter import DockerAdapter
from app.chaos.base import FaultContext
from app.chaos.faults.container_kill import ContainerKillFault
from app.chaos.faults.cpu_stress import CPUStressFault
from app.chaos.faults.memory_pressure import MemoryPressureFault
from app.chaos.faults.network_latency import NetworkLatencyFault
from app.chaos.faults.packet_loss import PacketLossFault
from app.chaos.faults.request_timeout import RequestTimeoutFault
from app.chaos.faults.service_unavailable import ServiceUnavailableFault
from app.chaos.registry import FaultRegistry
from app.chaos.rollback_manager import RollbackManager
from app.chaos.safety_controller import SafetyController
from app.core.exceptions import (
    EmergencyStopTriggeredError,
    ExperimentConflictError,
    ExperimentValidationError,
)
from app.database.models.service import Service


@pytest.fixture
def mock_docker_adapter():
    return DockerAdapter(dry_run=True)


@pytest.fixture
def sample_context():
    return FaultContext(
        experiment_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        target_container_id="test_container_123",
        target_base_url="http://localhost:8001",
        target_health_url="http://localhost:8001/health",
        configuration={},
    )


# --- 1. Network Latency Fault Tests ---
@pytest.mark.asyncio
async def test_network_latency_validation_and_lifecycle(mock_docker_adapter, sample_context):
    fault = NetworkLatencyFault(docker_adapter=mock_docker_adapter)

    # Validation errors
    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"latency_ms": -100})
    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"latency_ms": 500, "jitter_ms": 600})

    # Valid application
    sample_context.configuration = {"latency_ms": 500, "jitter_ms": 50, "duration_seconds": 30}
    applied = await fault.apply(sample_context)
    assert applied is True
    assert sample_context.state.get("latency_applied") is True

    # Verify
    verified = await fault.verify(sample_context)
    assert verified is True

    # Rollback
    reverted = await fault.rollback(sample_context)
    assert reverted is True
    assert sample_context.state.get("latency_applied") is False


# --- 2. Packet Loss Fault Tests ---
@pytest.mark.asyncio
async def test_packet_loss_validation_and_lifecycle(mock_docker_adapter, sample_context):
    fault = PacketLossFault(docker_adapter=mock_docker_adapter)

    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"loss_percentage": 0.0})
    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"loss_percentage": 105.0})

    sample_context.configuration = {"loss_percentage": 15.0, "duration_seconds": 30}
    assert await fault.apply(sample_context) is True
    assert await fault.verify(sample_context) is True
    assert await fault.rollback(sample_context) is True


# --- 3. CPU Stress Fault Tests ---
@pytest.mark.asyncio
async def test_cpu_stress_lifecycle(mock_docker_adapter, sample_context):
    fault = CPUStressFault(docker_adapter=mock_docker_adapter)

    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"cpu_percent": 5})

    sample_context.configuration = {"cpu_percent": 85, "workers": 2, "duration_seconds": 30}
    assert await fault.apply(sample_context) is True
    assert await fault.verify(sample_context) is True
    assert await fault.rollback(sample_context) is True


# --- 4. Memory Pressure Fault Tests ---
@pytest.mark.asyncio
async def test_memory_pressure_lifecycle(mock_docker_adapter, sample_context):
    fault = MemoryPressureFault(docker_adapter=mock_docker_adapter)

    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"allocation_mb": 16})

    sample_context.configuration = {"allocation_mb": 512, "duration_seconds": 30}
    assert await fault.apply(sample_context) is True
    assert await fault.verify(sample_context) is True
    assert await fault.rollback(sample_context) is True


# --- 5. Container Kill Fault Tests ---
@pytest.mark.asyncio
async def test_container_kill_lifecycle(mock_docker_adapter, sample_context):
    fault = ContainerKillFault(docker_adapter=mock_docker_adapter)

    with pytest.raises(ExperimentValidationError):
        fault.validate_configuration({"signal": "INVALID"})

    sample_context.configuration = {"signal": "SIGTERM", "restart": True}
    assert await fault.apply(sample_context) is True
    assert await fault.verify(sample_context) is True
    assert await fault.rollback(sample_context) is True


# --- 6. Service Unavailable Fault Tests ---
@pytest.mark.asyncio
async def test_service_unavailable_lifecycle(mock_docker_adapter, sample_context):
    fault = ServiceUnavailableFault(docker_adapter=mock_docker_adapter)
    sample_context.configuration = {"duration_seconds": 20}

    assert await fault.apply(sample_context) is True
    assert await fault.verify(sample_context) is True
    assert await fault.rollback(sample_context) is True


# --- 7. Request Timeout Fault Tests ---
@pytest.mark.asyncio
async def test_request_timeout_lifecycle(mock_docker_adapter, sample_context):
    fault = RequestTimeoutFault(docker_adapter=mock_docker_adapter)
    sample_context.configuration = {"timeout_delay_ms": 8000, "duration_seconds": 30}

    assert await fault.apply(sample_context) is True
    assert await fault.verify(sample_context) is True
    assert await fault.rollback(sample_context) is True


# --- 8. Fault Registry Catalog Tests ---
def test_fault_registry_catalog(mock_docker_adapter):
    registry = FaultRegistry(docker_adapter=mock_docker_adapter)
    faults = registry.list_faults()
    types = [f["fault_type"] for f in faults]

    assert "network_latency" in types
    assert "packet_loss" in types
    assert "cpu_stress" in types
    assert "memory_pressure" in types
    assert "container_kill" in types
    assert "service_unavailable" in types
    assert "request_timeout" in types

    strategy = registry.get_strategy("network_latency")
    assert strategy.fault_type == "network_latency"

    with pytest.raises(ExperimentValidationError):
        registry.get_strategy("non_existent_fault")


# --- 9. Rollback Manager Safety Guarantees ---
@pytest.mark.asyncio
async def test_rollback_manager_guaranteed_reversion(mock_docker_adapter, sample_context):
    manager = RollbackManager()
    fault = NetworkLatencyFault(docker_adapter=mock_docker_adapter)
    sample_context.configuration = {"latency_ms": 300, "duration_seconds": 15}

    # Verify managed_fault automatically rolls back on unhandled error
    with pytest.raises(RuntimeError):
        async with manager.managed_fault(fault, sample_context):
            assert sample_context.state.get("latency_applied") is True
            raise RuntimeError("Unexpected failure during experiment execution!")

    # State must be rolled back
    assert sample_context.state.get("latency_applied") is False
    assert len(manager.unhealthy_cleanups) == 0


@pytest.mark.asyncio
async def test_rollback_manager_records_unhealthy_cleanup(sample_context):
    manager = RollbackManager()

    class FailingFault(NetworkLatencyFault):
        async def rollback(self, context):
            raise Exception("Adapter network connection dropped during rollback!")

    failing_fault = FailingFault()
    success = await manager.execute_rollback(failing_fault, sample_context)
    assert success is False
    assert manager.has_unhealthy_cleanup(sample_context.experiment_id) is True

    unhealthy = manager.unhealthy_cleanups
    assert len(unhealthy) == 1
    assert unhealthy[0].experiment_id == sample_context.experiment_id
    assert "dropped during rollback" in unhealthy[0].error_message

    # Operator clears after manual intervention
    manager.clear_unhealthy_cleanup(sample_context.experiment_id)
    assert manager.has_unhealthy_cleanup(sample_context.experiment_id) is False


# --- 10. Safety Controller Concurrency & Threshold Guards ---
def test_safety_controller_concurrency_lock():
    controller = SafetyController()
    service_id = uuid.uuid4()
    exp_1 = uuid.uuid4()
    exp_2 = uuid.uuid4()

    # Acquire lock for first experiment
    controller.acquire_target_lock(service_id, exp_1)

    # Attempting second experiment on same service raises conflict
    with pytest.raises(ExperimentConflictError):
        controller.acquire_target_lock(service_id, exp_2)

    # Releasing lock allows subsequent experiment
    controller.release_target_lock(service_id, exp_1)
    controller.acquire_target_lock(service_id, exp_2)
    controller.release_target_lock(service_id, exp_2)


def test_safety_controller_threshold_evaluations():
    controller = SafetyController()
    exp_id = uuid.uuid4()
    thresholds = {
        "max_error_rate": 0.20,
        "max_latency_ms": 2000.0,
        "min_availability": 0.80,
    }

    # Within boundaries
    ok, _ = controller.evaluate_safety_thresholds(
        exp_id,
        {"error_rate": 0.05, "latency_ms": 150.0, "availability_percentage": 99.0},
        thresholds,
    )
    assert ok is True

    # Error rate exceeded
    ok, msg = controller.evaluate_safety_thresholds(
        exp_id,
        {"error_rate": 0.35, "latency_ms": 150.0, "availability_percentage": 99.0},
        thresholds,
    )
    assert ok is False
    assert "Error rate" in msg

    # Latency exceeded
    ok, msg = controller.evaluate_safety_thresholds(
        exp_id,
        {"error_rate": 0.05, "latency_ms": 3200.0, "availability_percentage": 99.0},
        thresholds,
    )
    assert ok is False
    assert "Observed latency" in msg


def test_safety_controller_emergency_stop():
    controller = SafetyController()
    service_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    controller.trigger_emergency_stop("Operator detected instability")
    assert controller.is_emergency_stopped is True

    # Acquiring lock is blocked during emergency stop
    with pytest.raises(EmergencyStopTriggeredError):
        controller.acquire_target_lock(service_id, exp_id)

    # Reset
    controller.reset_emergency_stop()
    assert controller.is_emergency_stopped is False

