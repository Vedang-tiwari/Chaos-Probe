import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ServiceBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier name for the service",
        examples=["payment-service"],
    )
    description: Optional[str] = Field(
        None,
        description="Short description of the service role and purpose",
        examples=["Processes customer payments and checkout charges"],
    )
    base_url: str = Field(
        ...,
        description="Base URL of the running service",
        examples=["http://localhost:8001"],
    )
    health_check_url: str = Field(
        ...,
        description="Endpoint URL used to probe service health",
        examples=["http://localhost:8001/health"],
    )
    container_id: Optional[str] = Field(
        None,
        description="Docker container ID or container name (if Docker container target)",
        examples=["payment_svc_container"],
    )
    environment: str = Field(
        default="development",
        description="Environment deployment tag (development, staging, test)",
        examples=["development"],
    )


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    health_check_url: Optional[str] = None
    container_id: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[str] = None


class ServiceResponse(ServiceBase):
    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceHealthResponse(BaseModel):
    service_id: uuid.UUID
    service_name: str
    status: str  # HEALTHY, UNHEALTHY, DEGRADED, UNKNOWN
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)
