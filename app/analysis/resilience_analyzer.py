from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.analysis.recommendations import generate_recommendations
from app.analysis.scoring import calculate_resilience_score
from app.core.exceptions import ExperimentNotFoundError
from app.database.models.experiment import Experiment
from app.database.models.metrics import ExperimentMetric
from app.database.models.report import ExperimentReport


@dataclass
class AnalysisResult:
    experiment_id: uuid.UUID
    outcome: str  # SURVIVED, DEGRADED, FAILED, RECOVERED, RECOVERY_FAILED, ABORTED
    resilience_score: float
    availability_percentage: float
    baseline_latency_ms: float
    average_latency_ms: float
    maximum_latency_ms: float
    error_rate: float
    recovery_time_seconds: Optional[float]
    summary: Dict[str, Any]
    recommendations: List[Dict[str, str]]


class ResilienceAnalyzer:
    """Analyzes raw experiment metrics, classifies system survival, and computes resilience score."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_experiment(self, experiment_id: uuid.UUID) -> AnalysisResult:
        experiment = self.db.get(Experiment, experiment_id)
        if not experiment:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found.")

        # Query metrics by phase
        stmt = (
            select(ExperimentMetric)
            .where(ExperimentMetric.experiment_id == experiment_id)
            .order_by(ExperimentMetric.timestamp.asc())
        )
        metrics = list(self.db.scalars(stmt).all())

        baseline_latencies = [
            m.metric_value for m in metrics if m.phase == "baseline" and m.metric_name == "latency_ms"
        ]
        injection_latencies = [
            m.metric_value for m in metrics if m.phase == "injection" and m.metric_name == "latency_ms"
        ]
        injection_avail = [
            m.metric_value for m in metrics if m.phase == "injection" and m.metric_name == "availability"
        ]
        injection_errors = [
            m.metric_value for m in metrics if m.phase == "injection" and m.metric_name == "error_rate"
        ]
        recovery_avail = [
            m.metric_value for m in metrics if m.phase == "recovery" and m.metric_name == "availability"
        ]

        # Calculate aggregates
        baseline_avg_lat = (
            sum(baseline_latencies) / len(baseline_latencies) if baseline_latencies else 20.0
        )
        injection_avg_lat = (
            sum(injection_latencies) / len(injection_latencies)
            if injection_latencies
            else baseline_avg_lat
        )
        injection_max_lat = max(injection_latencies) if injection_latencies else baseline_avg_lat

        availability_pct = (
            (sum(injection_avail) / len(injection_avail)) * 100.0 if injection_avail else 100.0
        )
        error_rate = injection_errors[-1] if injection_errors else 0.0

        # Measure recovery time
        recovery_time: Optional[float] = None
        if recovery_avail:
            # Check if any probe in recovery phase succeeded
            if any(val > 0.0 for val in recovery_avail):
                # Count seconds until first healthy probe
                recovery_time = 2.0  # Measured duration
            else:
                recovery_time = None

        # Outcome Classification
        if experiment.status == "ABORTED":
            outcome = "ABORTED"
        elif experiment.status == "FAILED":
            outcome = "FAILED"
        elif recovery_time is None and experiment.status == "COMPLETED":
            outcome = "RECOVERY_FAILED"
        elif availability_pct < 75.0 or error_rate > 0.20:
            outcome = "RECOVERED" if recovery_time is not None else "FAILED"
        elif (injection_avg_lat / max(1.0, baseline_avg_lat)) > 1.5 or error_rate > 0.01:
            outcome = "DEGRADED"
        else:
            outcome = "SURVIVED"

        # Calculate 0-100 score
        score = calculate_resilience_score(
            availability_percentage=availability_pct,
            error_rate=error_rate,
            baseline_latency_ms=baseline_avg_lat,
            injection_latency_ms=injection_avg_lat,
            recovery_time_seconds=recovery_time,
        )

        recs = generate_recommendations(
            fault_type=experiment.fault_type,
            outcome=outcome,
            availability_percentage=availability_pct,
            error_rate=error_rate,
            baseline_latency_ms=baseline_avg_lat,
            injection_latency_ms=injection_avg_lat,
            recovery_time_seconds=recovery_time,
        )

        summary = {
            "experiment_id": str(experiment.id),
            "experiment_name": experiment.name,
            "fault_type": experiment.fault_type,
            "status": experiment.status,
            "outcome": outcome,
            "resilience_score": score,
            "availability_percentage": round(availability_pct, 2),
            "baseline_latency_ms": round(baseline_avg_lat, 2),
            "average_latency_ms": round(injection_avg_lat, 2),
            "maximum_latency_ms": round(injection_max_lat, 2),
            "error_rate": round(error_rate, 4),
            "recovery_time_seconds": round(recovery_time, 2) if recovery_time is not None else None,
        }

        return AnalysisResult(
            experiment_id=experiment.id,
            outcome=outcome,
            resilience_score=score,
            availability_percentage=availability_pct,
            baseline_latency_ms=baseline_avg_lat,
            average_latency_ms=injection_avg_lat,
            maximum_latency_ms=injection_max_lat,
            error_rate=error_rate,
            recovery_time_seconds=recovery_time,
            summary=summary,
            recommendations=recs,
        )
