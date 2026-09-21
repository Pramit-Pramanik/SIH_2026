from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.schemas.gate import GateCheckInRequest, GateCheckInResponse
from backend.app.services.gate_service import verify_and_check_in_gate, inspect_gate_transaction

router = APIRouter(prefix="/gate", tags=["Mandi Gate Operations"])


@router.post(
    "/check-in",
    response_model=GateCheckInResponse,
    status_code=status.HTTP_200_OK,
    summary="Gate Entry QR Verification & Check-In",
    description="Validates cryptographic booking token, checks transaction relationships, and transitions state to GATE_ENTRY_VERIFIED idempotently."
)
def gate_check_in(
    payload: GateCheckInRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> GateCheckInResponse:
    return verify_and_check_in_gate(db=db, request=payload, current_user=current_user)


@router.get(
    "/verify/{transaction_id}",
    response_model=GateCheckInResponse,
    summary="Inspect Transaction Gate Status",
    description="Read-only query for gate operators to inspect transaction state and verification status without modifying records."
)
def get_gate_status(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN", "INSPECTOR", "FARMER"]))
) -> GateCheckInResponse:
    return inspect_gate_transaction(db=db, transaction_id=transaction_id, current_user=current_user)

