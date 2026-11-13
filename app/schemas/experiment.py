from datetime import datetime
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExperimentCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the experiment",
        examples=["payment-latency-spike"],
    )
    service_id: uuid.UUID = Field(
        ...,
        description="UUID of the registered target service to test",
    )
    fault_type: str = Field(
        ...,
        description="Type of fault to inject (e.g. network_latency, cpu_stress, packet_loss)",
        examples=["network_latency"],
    )
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Fault-specific parameters (e.g. latency_ms, jitter_ms, cpu_percent)",
        examples=[{"latency_ms": 500, "jitter_ms": 50}],
    )
    duration_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Duration of fault injection in seconds (max 120 recommended)",
    )
    baseline_duration_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Duration of pre-fault baseline metric collection in seconds",
    )
    recovery_window_seconds: int = Field(
        default=15,
        ge=1,
        le=60,
        description="Time allotted to observe post-fault recovery in seconds",
    )
    safety_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "max_error_rate": 0.25,
            "max_latency_ms": 3000.0,
            "min_availability": 0.70,
        },
        description="Guardrail thresholds that trigger an automatic safety abort if exceeded",
    )


class ExperimentResponse(BaseModel):
    id: uuid.UUID
    name: str
    service_id: uuid.UUID
    fault_type: str
    configuration: Dict[str, Any]
    status: str
    duration_seconds: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    abort_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExperimentStatusResponse(BaseModel):
    experiment_id: uuid.UUID
    status: str
    phase: Optional[str] = None
    progress_percent: float = 0.0
    elapsed_seconds: float = 0.0
    abort_reason: Optional[str] = None
    is_active: bool = False


class ExperimentAbortRequest(BaseModel):
    reason: str = Field(
        default="User requested manual abort",
        description="Reason for aborting the active experiment",
    )
