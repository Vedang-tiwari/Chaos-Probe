from typing import Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.chaos.registry import default_fault_registry
from app.core.exceptions import ExperimentValidationError

router = APIRouter(prefix="/faults", tags=["Faults"])


class FaultSummary(BaseModel):
    fault_type: str
    description: str


class FaultDetail(BaseModel):
    fault_type: str
    description: str


@router.get(
    "",
    response_model=List[FaultSummary],
    summary="List available fault types",
    description="Returns all fault injection strategies currently registered in the platform.",
)
def list_faults() -> List[FaultSummary]:
    catalog = default_fault_registry.list_faults()
    return [FaultSummary(**item) for item in catalog]


@router.get(
    "/{fault_type}",
    response_model=FaultDetail,
    summary="Retrieve fault documentation and configuration schema",
    description="Returns documentation, parameters, and requirements for a given fault type.",
)
def get_fault_info(fault_type: str) -> FaultDetail:
    try:
        info = default_fault_registry.get_fault_info(fault_type)
        return FaultDetail(**info)
    except ExperimentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc

