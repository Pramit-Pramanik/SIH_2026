from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.schemas.quality import (
    QualityAssessmentRequest,
    QualityAssessmentResponse,
    QualityOverrideRequest,
    QualityOverrideResponse
)
from backend.app.services.quality_service import (
    assess_quality_and_enqueue,
    override_quality_and_admit
)

router = APIRouter(prefix="/quality", tags=["Quality Assessment & Assaying"])


@router.post(
    "/assess",
    response_model=QualityAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assess vehicle crop moisture & quality (AC-006, AC-007)"
)
def assess_crop_quality(
    payload: QualityAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["INSPECTOR", "SUPERVISOR", "ADMIN"]))
) -> QualityAssessmentResponse:
    """
    Ingests digital crop moisture readings from the gate assaying station.
    - If moisture > 17.0%: Immediately triggers QUALITY_REJECTED and routes vehicle to drying apron.
    - If moisture <= 17.0%: Triggers QUALITY_APPROVED, calculates DCDQ priority score, and enqueues in Redis ZSET.
    """
    return assess_quality_and_enqueue(db=db, request=payload)


@router.post(
    "/override",
    response_model=QualityOverrideResponse,
    status_code=status.HTTP_200_OK,
    summary="Supervisor override for rejected crop lots (AC-007)"
)
def override_crop_quality(
    payload: QualityOverrideRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["SUPERVISOR", "ADMIN"]))
) -> QualityOverrideResponse:
    """
    Allows authenticated mandi supervisors to override a quality rejection with explicit audit logging,
    re-admitting the vehicle to the active priority queue.
    """
    return override_quality_and_admit(db=db, request=payload)

