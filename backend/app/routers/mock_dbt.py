from datetime import datetime, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.models.log import ProcurementLog
from backend.app.schemas.payout import (
    MockDbtPayoutRequest,
    MockDbtPayoutResponse
)
from backend.app.services.payout_service import format_dbt_settlement_reference

router = APIRouter(prefix="/mock", tags=["Mock Government Services"])


class MockDbtDisburseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str
    amount_inr: Optional[float] = None


class MockDbtDisburseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str = "SUCCESS"
    transaction_id: str
    dbt_reference_id: str
    settlement_rail: str = "PFMS-Aadhaar-Payment-Bridge"
    amount_inr: float = 142187.50
    timestamp: str
    message: str = "DBT funds disbursed via PFMS-Aadhaar Payment Bridge."


@router.post(
    "/dbt-payout",
    response_model=MockDbtPayoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulated PFMS / NPCI Direct Benefit Transfer (DBT) Payout Rail"
)
def mock_dbt_payout(payload: MockDbtPayoutRequest) -> MockDbtPayoutResponse:
    """
    Simulated government PFMS / NPCI DBT payment instruction endpoint.
    Returns a deterministic settlement confirmation with unique payout reference.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    short_hash = uuid.uuid4().hex[:8].upper()
    payout_ref = f"DBT-{date_str}-{short_hash}"

    return MockDbtPayoutResponse(
        status="INITIATED",
        payout_reference_id=payout_ref,
        settlement_rail="PFMS-Aadhaar-Bridge",
        timestamp=now.isoformat()
    )


def _get_read_only_settlement_confirmation(
    transaction_id: str,
    db: Session
) -> MockDbtDisburseResponse:
    """
    Authoritatively queries and confirms settlement without executing duplicate DBT transfers.
    Enforces read-only confirmation semantics. Fails closed with 404 if transaction is not found,
    or 409 if transaction is not in PAYMENT_SETTLED with a valid payout block hash.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    if log.current_state != "PAYMENT_SETTLED" or not log.payout_block_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot confirm DBT settlement: transaction is in state '{log.current_state}'. "
                f"Dual signatures must be staged first."
            )
        )

    settlement_ref = format_dbt_settlement_reference(log.payout_block_hash, log.updated_at)
    amount = float(log.total_payout_inr or 0.0)
    now = datetime.now(timezone.utc)
    ts = log.updated_at.isoformat() if log.updated_at else now.isoformat()

    return MockDbtDisburseResponse(
        status="SUCCESS",
        transaction_id=log.transaction_id,
        dbt_reference_id=settlement_ref,
        settlement_rail="PFMS-Aadhaar-Payment-Bridge",
        amount_inr=amount,
        timestamp=ts,
        message="Authoritative DBT settlement confirmed via PFMS-Aadhaar Payment Bridge."
    )


@router.get(
    "/dbt/confirmation/{transaction_id}",
    response_model=MockDbtDisburseResponse,
    status_code=status.HTTP_200_OK,
    summary="Read-only DBT Settlement Confirmation Query"
)
def get_dbt_confirmation(
    transaction_id: str,
    db: Session = Depends(get_db)
) -> MockDbtDisburseResponse:
    """
    Explicit read-only query endpoint for authoritative DBT settlement confirmation.
    Does not execute DBT transfers or modify transaction state.
    """
    return _get_read_only_settlement_confirmation(transaction_id, db)


@router.post(
    "/dbt/disburse",
    response_model=MockDbtDisburseResponse,
    status_code=status.HTTP_200_OK,
    summary="Read-only Simulated PFMS / NPCI DBT Disbursal Confirmation"
)
def mock_dbt_disburse(
    payload: MockDbtDisburseRequest,
    db: Session = Depends(get_db)
) -> MockDbtDisburseResponse:
    """
    Simulated government PFMS / NPCI DBT disbursement endpoint by transaction ID.
    Behaves strictly as a read-only settlement confirmation.
    Authoritatively queries the settlement reference without executing duplicate DBT transfers.
    """
    return _get_read_only_settlement_confirmation(payload.transaction_id, db)

