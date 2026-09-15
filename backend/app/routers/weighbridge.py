from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.schemas.weighbridge import (
    GrossWeightCaptureRequest,
    TareWeightCaptureRequest,
    UnifiedWeighmentRequest,
    WeighmentResponse
)
from backend.app.services.weighbridge_service import (
    record_gross_weight,
    record_tare_weight,
    record_unified_weighment,
    get_weighment_details
)

router = APIRouter(prefix="/weighbridge", tags=["Weighbridge Telemetry & Net Weight Settlement"])


@router.post(
    "/gross",
    response_model=WeighmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Capture loaded vehicle gross weight telemetry (AC-008)"
)
def capture_gross_weight(
    payload: GrossWeightCaptureRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> WeighmentResponse:
    """
    Ingests scale telemetry when a loaded vehicle arrives at the weighbridge.
    Validates gross weight > 0, enforces state transition to WEIGHED_GROSS.
    """
    return record_gross_weight(db=db, request=payload)


@router.post(
    "/tare",
    response_model=WeighmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Capture unloaded vehicle tare weight telemetry and calculate net weight (AC-008, AC-005)"
)
def capture_tare_weight(
    payload: TareWeightCaptureRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> WeighmentResponse:
    """
    Ingests scale telemetry when an empty vehicle exits after unloading.
    Validates gross > tare >= 0, computes Net Weight = Gross - Tare,
    enforces farmer yield ceiling invariance, and transitions state to WEIGHED_TARE.
    """
    return record_tare_weight(db=db, request=payload)


@router.post(
    "/capture",
    response_model=WeighmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Atomically capture gross and tare telemetry in a unified transaction"
)
def capture_unified_weighment(
    payload: UnifiedWeighmentRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> WeighmentResponse:
    """
    Simultaneously records gross and tare weights in a single atomic transaction.
    Computes Net Weight = Gross - Tare and transitions state to WEIGHED_TARE.
    """
    return record_unified_weighment(db=db, request=payload)


@router.get(
    "/{transaction_id}",
    response_model=WeighmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get weighment and net settlement details for a transaction"
)
def get_transaction_weighment(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN", "INSPECTOR", "FARMER"]))
) -> WeighmentResponse:
    """
    Retrieves current weighment telemetry and settlement state for a transaction.
    """
    return get_weighment_details(db=db, transaction_id=transaction_id)

