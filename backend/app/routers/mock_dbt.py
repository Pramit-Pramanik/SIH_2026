from datetime import datetime, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from backend.app.schemas.payout import (
    MockDbtPayoutRequest,
    MockDbtPayoutResponse
)

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


@router.post(
    "/dbt/disburse",
    response_model=MockDbtDisburseResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulated PFMS / NPCI Direct Benefit Transfer (DBT) Disbursal"
)
def mock_dbt_disburse(payload: MockDbtDisburseRequest) -> MockDbtDisburseResponse:
    """
    Simulated government PFMS / NPCI DBT disbursement endpoint by transaction ID.
    Returns settlement rail confirmation and unique reference ID.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    short_hash = uuid.uuid4().hex[:8].upper()
    payout_ref = f"DBT-{date_str}-{short_hash}"

    return MockDbtDisburseResponse(
        status="SUCCESS",
        transaction_id=payload.transaction_id,
        dbt_reference_id=payout_ref,
        settlement_rail="PFMS-Aadhaar-Payment-Bridge",
        amount_inr=payload.amount_inr or 142187.50,
        timestamp=now.isoformat(),
        message="DBT funds disbursed via PFMS-Aadhaar Payment Bridge."
    )

