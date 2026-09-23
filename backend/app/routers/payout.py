from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.schemas.payout import (
    DualSignaturePayoutStageRequest,
    DualSignaturePayoutStageResponse,
    DemoPayoutSignatureRequest,
)
from backend.app.services.payout_service import stage_dual_signature_payout
from backend.app.core.config import get_settings
from backend.app.core.security import get_payout_secret_key, compute_role_signature

router = APIRouter(prefix="/payout", tags=["Dual-Signature DBT Payout Staging"])


@router.post(
    "/demo-signatures",
    summary="Generate controlled prototype dual-signature approvals"
)
def create_demo_signatures(
    payload: DemoPayoutSignatureRequest,
    current_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR", "INSPECTOR"], strict=False))
) -> dict:
    """Returns server-generated demo approvals without exposing the payout secret.

    Provides cryptographically valid approvals bound to the transaction and invoice amount
    for authoritative prototype evaluation and showcase demonstrations.
    """
    secret_key = get_payout_secret_key()
    return {
        "inspector_sig_hash": compute_role_signature(
            secret_key, payload.transaction_id, payload.invoice_amount_inr, payload.inspector_id, "INSPECTOR"
        ),
        "operator_sig_hash": compute_role_signature(
            secret_key, payload.transaction_id, payload.invoice_amount_inr, payload.operator_id, "OPERATOR"
        ),
    }


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
    return stage_dual_signature_payout(db=db, request=payload, current_user=current_user)
