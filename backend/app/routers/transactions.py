from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    "",
    response_model=List[TransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Scoped Authoritative Transactions",
    description="Lists authoritative transactions filtered by mandi, current state, or farmer, strictly honoring tenant boundaries."
)
def list_authoritative_transactions(
    mandi_id: Optional[int] = Query(None),
    current_state: Optional[str] = Query(None),
    farmer_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR", "INSPECTOR", "OPERATOR", "FARMER"]))
) -> List[TransactionResponse]:
    query = db.query(ProcurementLog)

    # Tenant boundary enforcement
    if current_user:
        role = (current_user.role or "").upper()
        if role == "FARMER":
            user_farmer_id = getattr(current_user, "farmer_id", None) or current_user.user_id
            query = query.filter(ProcurementLog.farmer_id == user_farmer_id)
        elif role in ("SUPERVISOR", "INSPECTOR", "OPERATOR"):
            effective_mandi = current_user.mandi_id or mandi_id
            if effective_mandi:
                query = query.filter(ProcurementLog.mandi_id == effective_mandi)
        elif role == "ADMIN":
            if mandi_id is not None:
                query = query.filter(ProcurementLog.mandi_id == mandi_id)
            if farmer_id is not None:
                query = query.filter(ProcurementLog.farmer_id == farmer_id)
    elif mandi_id is not None:
        query = query.filter(ProcurementLog.mandi_id == mandi_id)

    if current_state:
        states = [s.strip() for s in current_state.split(",") if s.strip()]
        if len(states) == 1:
            query = query.filter(ProcurementLog.current_state == states[0])
        elif len(states) > 1:
            query = query.filter(ProcurementLog.current_state.in_(states))

    if farmer_id is not None and (not current_user or (current_user.role or "").upper() != "FARMER"):
        query = query.filter(ProcurementLog.farmer_id == farmer_id)

    logs = query.order_by(ProcurementLog.updated_at.desc(), ProcurementLog.created_at.desc()).limit(limit).all()

    if not logs:
        return []

    farmer_ids = {l.farmer_id for l in logs if l.farmer_id}
    mandi_ids = {l.mandi_id for l in logs if l.mandi_id}

    farmers = {f.farmer_id: f for f in db.query(Farmer).filter(Farmer.farmer_id.in_(farmer_ids)).all()} if farmer_ids else {}
    mandis = {m.mandi_id: m for m in db.query(Mandi).filter(Mandi.mandi_id.in_(mandi_ids)).all()} if mandi_ids else {}

    results = []
    for log in logs:
        f = farmers.get(log.farmer_id)
        m = mandis.get(log.mandi_id)
        results.append(
            TransactionResponse(
                transaction_id=log.transaction_id,
                farmer_id=log.farmer_id,
                farmer_name=f.name if f else None,
                mandi_id=log.mandi_id,
                mandi_name=m.name if m else None,
                slot_id=log.slot_id,
                scheduled_date=log.scheduled_date.isoformat() if log.scheduled_date else "",
                crop_type=log.crop_type or (f.registered_crop_type if f else "Wheat"),
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
        )
    return results


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
