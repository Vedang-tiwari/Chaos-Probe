import uuid
from unittest.mock import AsyncMock, patch
import pytest
from app.monitoring.health_checker import HealthCheckResult


def test_api_service_lifecycle(client):
    # 1. Register Service
    payload = {
        "name": "checkout-service",
        "description": "Cart and checkout processor",
        "base_url": "http://checkout:8000",
        "health_check_url": "http://checkout:8000/health",
        "container_id": "checkout_app_container",
        "environment": "staging",
    }
    response = client.post("/api/v1/services", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "checkout-service"
    service_id = data["id"]
    assert service_id is not None
    assert data["status"] == "UNKNOWN"

    # 2. Prevent duplicate name
    dup_res = client.post("/api/v1/services", json=payload)
    assert dup_res.status_code == 409

    # 3. Retrieve service
    get_res = client.get(f"/api/v1/services/{service_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "checkout-service"

    # 4. List services
    list_res = client.get("/api/v1/services?environment=staging")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == service_id

    # 5. Update service
    patch_res = client.patch(
        f"/api/v1/services/{service_id}",
        json={"description": "Updated checkout description", "environment": "production"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["environment"] == "production"
    assert patch_res.json()["description"] == "Updated checkout description"

    # 6. Delete service
    del_res = client.delete(f"/api/v1/services/{service_id}")
    assert del_res.status_code == 204

    # 7. Verify 404 after deletion
    get_404 = client.get(f"/api/v1/services/{service_id}")
    assert get_404.status_code == 404


@pytest.mark.asyncio
async def test_api_service_health_check(client):
    # Register service
    payload = {
        "name": "billing-service",
        "base_url": "http://billing:8000",
        "health_check_url": "http://billing:8000/health",
    }
    reg_res = client.post("/api/v1/services", json=payload)
    assert reg_res.status_code == 201
    service_id = reg_res.json()["id"]

    mock_result = HealthCheckResult(
        service_id=uuid.UUID(service_id),
        service_name="billing-service",
        status="HEALTHY",
        status_code=200,
        latency_ms=18.4,
    )

    with patch(
        "app.monitoring.health_checker.HealthChecker.check_http_endpoint",
        new=AsyncMock(return_value=mock_result),
    ):
        health_res = client.get(f"/api/v1/services/{service_id}/health")
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["status"] == "HEALTHY"
        assert health_data["latency_ms"] == 18.4
        assert health_data["status_code"] == 200
