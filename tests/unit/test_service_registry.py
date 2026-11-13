import uuid
import pytest
from app.core.exceptions import ServiceAlreadyExistsError, ServiceNotFoundError
from app.monitoring.health_checker import HealthChecker, HealthCheckResult
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.service_registry import ServiceRegistry


class MockHealthChecker(HealthChecker):
    """Mock health checker for deterministic unit testing."""

    def __init__(self, status: str = "HEALTHY", status_code: int = 200, latency: float = 12.5):
        super().__init__()
        self._status = status
        self._status_code = status_code
        self._latency = latency

    async def check_http_endpoint(
        self,
        service_id: uuid.UUID,
        service_name: str,
        health_check_url: str,
    ) -> HealthCheckResult:
        return HealthCheckResult(
            service_id=service_id,
            service_name=service_name,
            status=self._status,
            status_code=self._status_code,
            latency_ms=self._latency,
        )


def test_register_service(db_session):
    registry = ServiceRegistry(db=db_session)
    service_in = ServiceCreate(
        name="auth-service",
        description="Handles user authentication and JWTs",
        base_url="http://auth:8000",
        health_check_url="http://auth:8000/health",
        container_id="auth_container_01",
        environment="staging",
    )

    created = registry.register_service(service_in)
    assert created.id is not None
    assert created.name == "auth-service"
    assert created.status == "UNKNOWN"
    assert created.environment == "staging"


def test_prevent_duplicate_service_registration(db_session):
    registry = ServiceRegistry(db=db_session)
    service_in = ServiceCreate(
        name="payment-service",
        base_url="http://payment:8000",
        health_check_url="http://payment:8000/health",
    )
    registry.register_service(service_in)

    with pytest.raises(ServiceAlreadyExistsError) as exc_info:
        registry.register_service(service_in)

    assert "payment-service" in str(exc_info.value.message)


def test_get_by_id_and_name(db_session):
    registry = ServiceRegistry(db=db_session)
    service = registry.register_service(
        ServiceCreate(
            name="order-service",
            base_url="http://order:8000",
            health_check_url="http://order:8000/health",
        )
    )

    by_id = registry.get_by_id(service.id)
    assert by_id.name == "order-service"

    by_name = registry.get_by_name("order-service")
    assert by_name is not None
    assert by_name.id == service.id

    with pytest.raises(ServiceNotFoundError):
        registry.get_by_id(uuid.uuid4())


def test_update_service(db_session):
    registry = ServiceRegistry(db=db_session)
    service = registry.register_service(
        ServiceCreate(
            name="inventory-service",
            base_url="http://inventory:8000",
            health_check_url="http://inventory:8000/health",
        )
    )

    updated = registry.update_service(
        service.id,
        ServiceUpdate(description="Updated inventory description", environment="production"),
    )
    assert updated.description == "Updated inventory description"
    assert updated.environment == "production"


def test_delete_service(db_session):
    registry = ServiceRegistry(db=db_session)
    service = registry.register_service(
        ServiceCreate(
            name="temp-service",
            base_url="http://temp:8000",
            health_check_url="http://temp:8000/health",
        )
    )

    registry.delete_service(service.id)
    with pytest.raises(ServiceNotFoundError):
        registry.get_by_id(service.id)


@pytest.mark.asyncio
async def test_check_service_health_updates_status(db_session):
    mock_checker = MockHealthChecker(status="HEALTHY", status_code=200, latency=15.0)
    registry = ServiceRegistry(db=db_session, health_checker=mock_checker)

    service = registry.register_service(
        ServiceCreate(
            name="monitored-service",
            base_url="http://monitored:8000",
            health_check_url="http://monitored:8000/health",
        )
    )
    assert service.status == "UNKNOWN"

    result = await registry.check_service_health(service.id)
    assert result.status == "HEALTHY"
    assert result.latency_ms == 15.0

    # Verify database was updated
    refreshed = registry.get_by_id(service.id)
    assert refreshed.status == "HEALTHY"
