from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, status

from backend.app.schemas.payout import (
    MockDbtPayoutRequest,
    MockDbtPayoutResponse
)

router = APIRouter(prefix="/mock", tags=["Mock Government Services"])


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
