from datetime import datetime, timezone
import hmac
import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import (
    get_payout_secret_key,
    compute_role_signature,
    compute_payout_block_hash
)
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.schemas.payout import (
    DualSignaturePayoutStageRequest,
    DualSignaturePayoutStageResponse,
    MockDbtPayoutRequest,
    MockDbtPayoutResponse
)
from backend.app.services.lifecycle_service import validate_lifecycle_transition


def execute_mock_dbt_transfer(
    farmer_id: int,
    amount_inr: float,
    bank_ifsc: str,
    account_number_hash: str,
    block_hash: Optional[str] = None
) -> MockDbtPayoutResponse:
    """
    Simulates government Direct Benefit Transfer (DBT) payment rail (PFMS / NPCI Aadhaar Bridge).
    Generates a deterministic payout reference ID bound to the transaction/block hash.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    short_hash = (block_hash[:8] if block_hash else uuid.uuid4().hex[:8]).upper()
    payout_ref = f"DBT-{date_str}-{short_hash}"

    return MockDbtPayoutResponse(
        status="INITIATED",
        payout_reference_id=payout_ref,
        settlement_rail="PFMS-Aadhaar-Bridge",
        timestamp=now.isoformat()
    )


def stage_dual_signature_payout(
    db: Session,
    request: DualSignaturePayoutStageRequest
) -> DualSignaturePayoutStageResponse:
    """
    Validates dual HMAC-SHA256 cryptographic signatures from both Inspector and Operator
    bound to the transaction ID and J-Form invoice amount (AC-009).
    Fails closed if secrets are missing, either signature is missing/forged,
    or amount/transaction ID has been tampered.
    Triggers mock DBT payment instruction upon successful authorization.
    """
    # 1. Fail-closed check: retrieve payout secret key
    secret_key = get_payout_secret_key()

    # 2. Check for missing or empty signatures
    if not request.inspector_sig_hash or not request.inspector_sig_hash.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Inspector Signature"
        )

    if not request.operator_sig_hash or not request.operator_sig_hash.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Operator Signature"
        )

    # 3. Lookup transaction log
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # 4. Idempotency handling: if already in DBT_PAYMENT_INITIATED or PAYMENT_SETTLED
    if log.current_state in ("DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"):
        expected_inspector = compute_role_signature(
            secret_key, request.transaction_id, request.invoice_amount_inr, request.inspector_id, "INSPECTOR"
        )
        expected_operator = compute_role_signature(
            secret_key, request.transaction_id, request.invoice_amount_inr, request.operator_id, "OPERATOR"
        )
        computed_block = compute_payout_block_hash(
            secret_key, request.transaction_id, request.invoice_amount_inr,
            request.inspector_sig_hash, request.operator_sig_hash
        )

        if (
            log.payout_block_hash == computed_block
            and hmac.compare_digest(request.inspector_sig_hash, expected_inspector)
            and hmac.compare_digest(request.operator_sig_hash, expected_operator)
        ):
            return DualSignaturePayoutStageResponse(
                status="AUTHORIZED",
                transaction_id=log.transaction_id,
                amount_inr=float(log.total_payout_inr or request.invoice_amount_inr),
                payout_block_hash=log.payout_block_hash,
                current_state=log.current_state,
                dbt_reference_id=f"DBT-{log.updated_at.strftime('%Y%m%d')}-{log.payout_block_hash[:8].upper()}",
                message="Payout already authorized and processed (idempotent repeated request)."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicting payout staging request for transaction '{log.transaction_id}' already in {log.current_state}."
            )

    amount = float(request.invoice_amount_inr)

    # 5. Enforce state machine progression: must be in BILL_GENERATED per lifecycle engine
    is_valid, err_msg, _ = validate_lifecycle_transition(
        log.current_state,
        "PAYMENT_SETTLED",
        payload_fields={"total_payout_inr": amount},
        current_log=log
    )
    if not is_valid or log.current_state != "BILL_GENERATED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot stage payout: transaction is in state '{log.current_state}'. "
                f"Transaction must be in 'BILL_GENERATED' state before staging DBT payout."
            )
        )

    # 6. Tamper detection: verify request amount matches persisted J-Form total_payout_inr
    if log.total_payout_inr is None or abs(float(log.total_payout_inr) - amount) > 1e-2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Invoice amount mismatch / tamper detected: request amount ₹{amount:.2f} "
                f"does not match authorized J-Form invoice amount ₹{float(log.total_payout_inr or 0.0):.2f}."
            )
        )

    # 7. Cryptographic signature recomputation & verification
    # 7a. Recompute & verify Inspector HMAC-SHA256
    expected_inspector_hash = compute_role_signature(
        secret_key, request.transaction_id, amount, request.inspector_id, "INSPECTOR"
    )
    if not hmac.compare_digest(request.inspector_sig_hash, expected_inspector_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Inspector Signature"
        )

    # 7b. Recompute & verify Operator HMAC-SHA256
    expected_operator_hash = compute_role_signature(
        secret_key, request.transaction_id, amount, request.operator_id, "OPERATOR"
    )
    if not hmac.compare_digest(request.operator_sig_hash, expected_operator_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Operator Signature"
        )

    # 8. Both signatures valid -> Generate Payout Block Hash
    payout_block_hash = compute_payout_block_hash(
        secret_key, request.transaction_id, amount, request.inspector_sig_hash, request.operator_sig_hash
    )

    # 9. Lookup farmer bank credentials and trigger Mock DBT payout
    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    bank_ifsc = farmer.ifsc_code if farmer else "SBIN0001040"
    account_hash = farmer.bank_account_hash if farmer else "default_account_hash"

    dbt_result = execute_mock_dbt_transfer(
        farmer_id=log.farmer_id,
        amount_inr=amount,
        bank_ifsc=bank_ifsc,
        account_number_hash=account_hash,
        block_hash=payout_block_hash
    )

    # 10. Atomically update transaction log
    now = datetime.now(timezone.utc)
    log.payout_block_hash = payout_block_hash
    log.current_state = "PAYMENT_SETTLED"
    log.updated_at = now
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    return DualSignaturePayoutStageResponse(
        status="AUTHORIZED",
        transaction_id=log.transaction_id,
        amount_inr=amount,
        payout_block_hash=payout_block_hash,
        current_state=log.current_state,
        dbt_reference_id=dbt_result.payout_reference_id,
        message=f"DBT Payout of ₹{amount:.2f} authorized with dual signatures and settled via {dbt_result.settlement_rail}."
    )
