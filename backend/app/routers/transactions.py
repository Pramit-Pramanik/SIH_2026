from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.authorization import assert_transaction_scope
from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.models.log import ProcurementLog
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.schemas.transaction import TransactionResponse

router = APIRouter(prefix="/transactions", tags=["Authoritative Transaction Ledger"])


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve Authoritative Procurement Transaction",
    description="Retrieves the single authoritative transaction record across all procurement stages."
)
def get_authoritative_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR", "INSPECTOR", "OPERATOR", "FARMER"]))
) -> TransactionResponse:
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id.strip()
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    # Role-based scoping checks (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="inspect transaction")

    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    mandi = db.query(Mandi).filter(Mandi.mandi_id == log.mandi_id).first()

    return TransactionResponse(
        transaction_id=log.transaction_id,
        farmer_id=log.farmer_id,
        farmer_name=farmer.name if farmer else None,
        mandi_id=log.mandi_id,
        mandi_name=mandi.name if mandi else None,
        slot_id=log.slot_id,
        scheduled_date=log.scheduled_date.isoformat() if log.scheduled_date else "",
        crop_type=log.crop_type or (farmer.registered_crop_type if farmer else "Wheat"),
        crop_moisture_pct=float(log.crop_moisture_pct) if log.crop_moisture_pct is not None else None,
        gross_weight_qt=float(log.gross_weight_qt) if log.gross_weight_qt is not None else None,
        tare_weight_qt=float(log.tare_weight_qt) if log.tare_weight_qt is not None else None,
        net_weight_qt=float(log.net_weight_qt) if log.net_weight_qt is not None else None,
        total_payout_inr=float(log.total_payout_inr) if log.total_payout_inr is not None else None,
        current_state=log.current_state,
        token_signature=log.token_signature,
        payout_block_hash=log.payout_block_hash,
        created_at=log.created_at.isoformat() if log.created_at else None,
        updated_at=log.updated_at.isoformat() if log.updated_at else None
    )
