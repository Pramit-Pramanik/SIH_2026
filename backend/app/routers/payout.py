from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.schemas.payout import (
    DualSignaturePayoutStageRequest,
    DualSignaturePayoutStageResponse
)
from backend.app.services.payout_service import stage_dual_signature_payout

router = APIRouter(prefix="/payout", tags=["Dual-Signature DBT Payout Staging"])


@router.post(
    "/stage",
    response_model=DualSignaturePayoutStageResponse,
    status_code=status.HTTP_200_OK,
    summary="Stage DBT payout with dual cryptographic signatures (AC-009)"
)
def stage_payout(
    payload: DualSignaturePayoutStageRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["INSPECTOR", "OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> DualSignaturePayoutStageResponse:
    """
    Enforces dual-signature cryptographic authorization (AC-009) before staging DBT payout.
    - Requires independent HMAC-SHA256 signatures from both Inspector and Operator.
    - Verifies cryptographic binding to transaction ID and exact J-Form invoice amount.
    - Transitions transaction state to PAYMENT_SETTLED and records payout block hash.
    - Fails closed with HTTP 403 if either signature is missing, forged, or amount is tampered.
    """
    return stage_dual_signature_payout(db=db, request=payload)

