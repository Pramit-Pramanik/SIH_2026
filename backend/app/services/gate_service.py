from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import verify_booking_signature
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.schemas.gate import GateCheckInRequest, GateCheckInResponse


def verify_and_check_in_gate(
    db: Session,
    request: GateCheckInRequest
) -> GateCheckInResponse:
    """
    Validates QR gate pass token, enforces cryptographic integrity and transaction
    relationship invariants, and safely transitions transaction to GATE_ENTRY_VERIFIED.
    Idempotent: repeating check-in on an already verified lot returns HTTP 200 without state corruption.
    """
    # 1. Exact Cryptographic Verification (HMAC-SHA256 over canonical payload)
    is_valid_sig = verify_booking_signature(
        farmer_id=request.farmer_id,
        mandi_id=request.mandi_id,
        slot_id=request.slot_id,
        quantity_qt=request.quantity_qt,
        signature=request.token_signature
    )
    if not is_valid_sig:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptographic verification failed: booking token signature is invalid or payload has been tampered with."
        )

    # 2. Transaction Record Lookup
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement transaction '{request.transaction_id}' not found."
        )

    # 3. Transaction Relationship Invariant Validation
    # Token parameters must match database booking record exactly
    if (
        log.farmer_id != request.farmer_id
        or log.mandi_id != request.mandi_id
        or log.slot_id != request.slot_id
        or abs(float(log.net_weight_qt or 0.0) - float(request.quantity_qt)) > 1e-4
        or log.token_signature != request.token_signature
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transaction relationship mismatch: token attributes do not match registered procurement booking record."
        )

    # 4. Mandi & Slot State Validation
    mandi = db.query(Mandi).filter(Mandi.mandi_id == request.mandi_id).first()
    if not mandi or not mandi.is_operational:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mandi '{request.mandi_id}' is non-operational or does not exist."
        )

    slot = db.query(ProcurementSlot).filter(ProcurementSlot.slot_id == request.slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement slot '{request.slot_id}' not found."
        )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == request.farmer_id).first()
    farmer_name = farmer.name if farmer else "Unknown Farmer"
    crop_type = farmer.registered_crop_type if farmer else "Unknown Crop"

    # 5. Idempotent State Machine Transition
    if log.current_state == "GATE_ENTRY_VERIFIED":
        # Idempotent replay: already checked in, return deterministic safe response
        verified_timestamp = log.updated_at.isoformat() if log.updated_at else datetime.now(timezone.utc).isoformat()
        return GateCheckInResponse(
            status="ALREADY_VERIFIED",
            transaction_id=log.transaction_id,
            current_state=log.current_state,
            farmer_id=log.farmer_id,
            farmer_name=farmer_name,
            crop_type=crop_type,
            mandi_name=mandi.name,
            slot_id=log.slot_id,
            scheduled_date=str(log.scheduled_date),
            quantity_qt=float(log.net_weight_qt or request.quantity_qt),
            verified_at=verified_timestamp,
            message=f"Gate entry was previously verified for transaction {log.transaction_id}. Entry confirmed without state change."
        )

    # Central lifecycle validation
    from backend.app.services.lifecycle_service import validate_lifecycle_transition
    is_valid, err_msg, status_code = validate_lifecycle_transition(
        from_state=log.current_state,
        to_state="GATE_ENTRY_VERIFIED",
        payload_fields={"quantity_qt": request.quantity_qt},
        farmer=farmer,
        db=db,
        current_log=log
    )
    if not is_valid or log.current_state != "SLOT_BOOKED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state for gate entry: transaction is in state '{log.current_state}'. Only 'SLOT_BOOKED' transactions can enter."
        )

    now = datetime.now(timezone.utc)
    log.current_state = "GATE_ENTRY_VERIFIED"
    log.updated_at = now
    if request.client_mutation_id:
        log.client_mutation_id = request.client_mutation_id

    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    return GateCheckInResponse(
        status="VERIFIED",
        transaction_id=log.transaction_id,
        current_state=log.current_state,
        farmer_id=log.farmer_id,
        farmer_name=farmer_name,
        crop_type=crop_type,
        mandi_name=mandi.name,
        slot_id=log.slot_id,
        scheduled_date=str(log.scheduled_date),
        quantity_qt=float(log.net_weight_qt or request.quantity_qt),
        verified_at=now.isoformat(),
        message=f"Gate entry successfully verified for {farmer_name}. Authorized for mandi yard staging entry."
    )


def inspect_gate_transaction(
    db: Session,
    transaction_id: str
) -> GateCheckInResponse:
    """
    Read-only inspection of gate entry status for a transaction.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement transaction '{transaction_id}' not found."
        )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    mandi = db.query(Mandi).filter(Mandi.mandi_id == log.mandi_id).first()

    return GateCheckInResponse(
        status="VERIFIED" if log.current_state == "GATE_ENTRY_VERIFIED" else "PENDING_ENTRY",
        transaction_id=log.transaction_id,
        current_state=log.current_state,
        farmer_id=log.farmer_id,
        farmer_name=farmer.name if farmer else "Unknown Farmer",
        crop_type=farmer.registered_crop_type if farmer else "Unknown Crop",
        mandi_name=mandi.name if mandi else "Unknown Mandi",
        slot_id=log.slot_id,
        scheduled_date=str(log.scheduled_date),
        quantity_qt=float(log.net_weight_qt or 0.0),
        verified_at=log.updated_at.isoformat() if log.updated_at else datetime.now(timezone.utc).isoformat(),
        message=f"Transaction is currently in state '{log.current_state}'."
    )
