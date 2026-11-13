from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from app.chaos.rollback_manager import default_rollback_manager
from app.chaos.safety_controller import default_safety_controller
from app.core.security import verify_admin_key

router = APIRouter(prefix="/admin", tags=["Administration"])


class EmergencyStopRequest(BaseModel):
    reason: str = "Manual operator intervention"


class EmergencyStopResponse(BaseModel):
    status: str
    message: str
    reason: str


class UnhealthyCleanupItem(BaseModel):
    experiment_id: str
    fault_type: str
    target_container_id: Optional[str]
    error_message: str


@router.post(
    "/emergency-stop",
    response_model=EmergencyStopResponse,
    summary="Trigger immediate platform-wide emergency stop",
    description="Halts all running experiments, cancels pending injections, and triggers automatic rollback.",
    dependencies=[Depends(verify_admin_key)],
)
def emergency_stop(payload: EmergencyStopRequest) -> EmergencyStopResponse:
    default_safety_controller.trigger_emergency_stop(reason=payload.reason)
    return EmergencyStopResponse(
        status="EMERGENCY_STOP_ACTIVATED",
        message="All active fault injection processes halted. Rollbacks initiated.",
        reason=payload.reason,
    )


@router.post(
    "/reset-emergency-stop",
    summary="Reset emergency stop state",
    description="Resets the emergency stop state after verified operator inspection.",
    dependencies=[Depends(verify_admin_key)],
)
def reset_emergency_stop() -> dict[str, str]:
    default_safety_controller.reset_emergency_stop()
    return {"status": "NORMAL_OPERATION_RESUMED"}


@router.get(
    "/cleanups/unhealthy",
    response_model=List[UnhealthyCleanupItem],
    summary="List rollbacks requiring operator attention",
    description="Returns all experiments where rollback or cleanup encountered an error.",
    dependencies=[Depends(verify_admin_key)],
)
def get_unhealthy_cleanups() -> List[UnhealthyCleanupItem]:
    cleanups = default_rollback_manager.unhealthy_cleanups
    return [
        UnhealthyCleanupItem(
            experiment_id=str(c.experiment_id),
            fault_type=c.fault_type,
            target_container_id=c.target_container_id,
            error_message=c.error_message,
        )
        for c in cleanups
    ]
