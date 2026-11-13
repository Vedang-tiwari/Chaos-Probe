import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_service_registry
from app.core.exceptions import ServiceAlreadyExistsError, ServiceNotFoundError
from app.schemas.service import (
    ServiceCreate,
    ServiceHealthResponse,
    ServiceResponse,
    ServiceUpdate,
)
from app.services.service_registry import ServiceRegistry

router = APIRouter(prefix="/services", tags=["Services"])


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a target service",
    description="Registers a new target microservice or container into Chaos Probe.",
)
def register_service(
    service_in: ServiceCreate,
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ServiceResponse:
    try:
        service = registry.register_service(service_in)
        return ServiceResponse.model_validate(service)
    except ServiceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc


@router.get(
    "",
    response_model=List[ServiceResponse],
    summary="List registered services",
    description="Retrieves a list of registered services with optional environment and status filtering.",
)
def list_services(
    environment: Optional[str] = Query(None, description="Filter by environment (e.g. development, staging)"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. HEALTHY, UNHEALTHY, UNKNOWN)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    registry: ServiceRegistry = Depends(get_service_registry),
) -> List[ServiceResponse]:
    services = registry.list_services(
        environment=environment,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [ServiceResponse.model_validate(s) for s in services]


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Get service details",
    description="Retrieves details for a specific registered service.",
)
def get_service(
    service_id: uuid.UUID,
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ServiceResponse:
    try:
        service = registry.get_by_id(service_id)
        return ServiceResponse.model_validate(service)
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Update service details",
    description="Updates registered service parameters such as URLs, description, or environment.",
)
def update_service(
    service_id: uuid.UUID,
    update_in: ServiceUpdate,
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ServiceResponse:
    try:
        service = registry.update_service(service_id, update_in)
        return ServiceResponse.model_validate(service)
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except ServiceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a registered service",
    description="Removes a service from Chaos Probe registry along with its experiment records.",
)
def delete_service(
    service_id: uuid.UUID,
    registry: ServiceRegistry = Depends(get_service_registry),
) -> None:
    try:
        registry.delete_service(service_id)
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.get(
    "/{service_id}/health",
    response_model=ServiceHealthResponse,
    summary="Check service health",
    description="Actively probes the target service health check endpoint and returns health metrics.",
)
async def check_service_health(
    service_id: uuid.UUID,
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ServiceHealthResponse:
    try:
        result = await registry.check_service_health(service_id)
        return ServiceHealthResponse(
            service_id=result.service_id,
            service_name=result.service_name,
            status=result.status,
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            error_message=result.error_message,
            checked_at=result.checked_at,
        )
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
