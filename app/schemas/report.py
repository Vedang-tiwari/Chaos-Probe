from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict


class ExperimentReportResponse(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    outcome: str
    availability_percentage: float
    average_latency: float
    maximum_latency: float
    error_rate: float
    recovery_time_seconds: Optional[float]
    summary: Dict[str, Any]
    recommendations: List[Any]
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentComparisonResponse(BaseModel):
    target_service_id: uuid.UUID
    target_service_name: str
    total_experiments: int
    average_resilience_score: float
    experiments: List[Dict[str, Any]]

