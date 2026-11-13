from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.core.exceptions import (
    ChaosProbeException,
    ExperimentConflictError,
    ExperimentNotFoundError,
    ServiceNotFoundError,
)
from app.database.session import get_db
from app.schemas.experiment import (
    ExperimentAbortRequest,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentStatusResponse,
)
from app.schemas.report import ExperimentReportResponse
from app.services.experiment_manager import ExperimentManager

router = APIRouter(prefix="/experiments", tags=["Experiments"])


def get_experiment_manager(db: Session = Depends(get_db)) -> ExperimentManager:
    return ExperimentManager(db=db)


@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new experiment",
    description="Registers a new controlled fault injection experiment for a target service.",
)
def create_experiment(
    exp_in: ExperimentCreate,
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> ExperimentResponse:
    try:
        experiment = manager.create_experiment(exp_in)
        return ExperimentResponse.model_validate(experiment)
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.get(
    "",
    response_model=List[ExperimentResponse],
    summary="List experiments",
    description="Lists past and active experiments with optional filtering.",
)
def list_experiments(
    service_id: Optional[uuid.UUID] = Query(None, description="Filter by service ID"),
    status: Optional[str] = Query(None, description="Filter by experiment status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> List[ExperimentResponse]:
    experiments = manager.list_experiments(
        service_id=service_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [ExperimentResponse.model_validate(e) for e in experiments]


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Retrieve experiment details",
    description="Returns configuration and execution metadata for a specific experiment.",
)
def get_experiment(
    experiment_id: uuid.UUID,
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> ExperimentResponse:
    try:
        experiment = manager.get_by_id(experiment_id)
        return ExperimentResponse.model_validate(experiment)
    except ExperimentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.post(
    "/{experiment_id}/start",
    response_model=ExperimentResponse,
    summary="Start experiment execution",
    description="Initiates asynchronous execution of the experiment through the 10-phase lifecycle.",
)
def start_experiment(
    experiment_id: uuid.UUID,
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> ExperimentResponse:
    try:
        experiment = manager.start_experiment(experiment_id)
        return ExperimentResponse.model_validate(experiment)
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ExperimentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc


@router.post(
    "/{experiment_id}/abort",
    response_model=ExperimentResponse,
    summary="Abort an active experiment",
    description="Immediately aborts the experiment, rolls back any active fault injection, and restores target state.",
)
def abort_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentAbortRequest,
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> ExperimentResponse:
    try:
        experiment = manager.abort_experiment(experiment_id, reason=payload.reason)
        return ExperimentResponse.model_validate(experiment)
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/{experiment_id}/status",
    response_model=ExperimentStatusResponse,
    summary="Get execution status and progress",
    description="Returns the live lifecycle phase, elapsed duration, and active state of the experiment.",
)
def get_status(
    experiment_id: uuid.UUID,
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> ExperimentStatusResponse:
    try:
        return manager.get_status(experiment_id)
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/{experiment_id}/metrics",
    summary="Retrieve recorded metrics",
    description="Returns metrics captured during baseline, injection, and recovery phases.",
)
def get_metrics(
    experiment_id: uuid.UUID,
    phase: Optional[str] = Query(None, description="Filter metrics by phase (baseline, injection, recovery)"),
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> List[dict[str, Any]]:
    try:
        metrics = manager.get_metrics(experiment_id, phase=phase)
        return [
            {
                "id": str(m.id),
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "phase": m.phase,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in metrics
        ]
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/{experiment_id}/events",
    summary="Retrieve experiment lifecycle events",
    description="Returns chronological audit trail of state transitions and alerts.",
)
def get_events(
    experiment_id: uuid.UUID,
    manager: ExperimentManager = Depends(get_experiment_manager),
) -> List[dict[str, Any]]:
    try:
        events = manager.get_events(experiment_id)
        return [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "message": e.message,
                "metadata": e.event_metadata,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc



@router.get(
    "/{experiment_id}/report",
    response_model=ExperimentReportResponse,
    summary="Retrieve experiment report",
    description="Generates or returns synthesized resilience score, summary, and engineering recommendations.",
)
def get_report(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ExperimentReportResponse:
    from app.reports.generator import ReportGenerator

    generator = ReportGenerator(db=db)
    try:
        report = generator.generate_report(experiment_id)
        return ExperimentReportResponse.model_validate(report)
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/{experiment_id}/report.html",
    summary="Download or view rendered HTML report dashboard",
    description="Returns interactive HTML report dashboard visualising experiment results.",
)
def get_html_report(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    from app.reports.generator import ReportGenerator

    generator = ReportGenerator(db=db)
    try:
        report = generator.generate_report(experiment_id)
        html = generator.render_html(report)
        return HTMLResponse(content=html, status_code=200)
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/compare/{service_id}",
    summary="Compare historical service resilience across experiments",
    description="Returns aggregate resilience score trends and summaries across all experiments for a target service.",
)
def compare_experiments(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.reports.generator import ReportGenerator

    generator = ReportGenerator(db=db)
    return generator.compare_service_experiments(service_id)
