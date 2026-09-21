from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.authorization import assert_transaction_scope
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.schemas.weighbridge import (
    GrossWeightCaptureRequest,
    TareWeightCaptureRequest,
    UnifiedWeighmentRequest,
    WeighmentResponse
)
from backend.app.services.lock_manager import lock_manager
from backend.app.services.lifecycle_service import validate_lifecycle_transition


def record_gross_weight(
    db: Session,
    request: GrossWeightCaptureRequest,
    current_user: Optional[User] = None
) -> WeighmentResponse:
    """
    Captures gross weight telemetry for a vehicle that has arrived at the weighbridge.
    Validates non-negative weight (>0) and enforces prior state transition (ROUTED_TO_WEIGHBRIDGE).
    Transitions state to WEIGHED_GROSS.
    """
    gross_weight = float(request.gross_weight_qt)
    if gross_weight <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gross weight must be strictly greater than zero quintals."
        )

    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="capture gross weight")

    # Idempotency check: repeated telemetry with exact same weight
    if log.current_state == "WEIGHED_GROSS":
        if log.gross_weight_qt is not None and abs(float(log.gross_weight_qt) - gross_weight) < 1e-4:
            return WeighmentResponse(
                transaction_id=log.transaction_id,
                mandi_id=log.mandi_id,
                farmer_id=log.farmer_id,
                gross_weight_qt=float(log.gross_weight_qt),
                tare_weight_qt=float(log.tare_weight_qt) if log.tare_weight_qt else None,
                net_weight_qt=float(log.net_weight_qt) if log.net_weight_qt else None,
                current_state=log.current_state,
                timestamp=log.updated_at.isoformat(),
                message="Gross weight already captured (idempotent repeated telemetry)."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicting gross weight telemetry for transaction '{log.transaction_id}' already in WEIGHED_GROSS."
            )

    # Cannot re-record gross weight if already weighed tare or completed
    subsequent_states = ("WEIGHED_TARE", "BILL_GENERATED", "DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED")
    if log.current_state in subsequent_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot record gross weight: transaction is already in advanced state '{log.current_state}'."
        )

    # Valid prior states for gross weighment
    allowed_prior_states = ("ROUTED_TO_WEIGHBRIDGE", "QUALITY_APPROVED")
    if log.current_state not in allowed_prior_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot skip required prior state: transaction is in state '{log.current_state}'. "
                f"Vehicle must be in 'ROUTED_TO_WEIGHBRIDGE' or 'QUALITY_APPROVED' to record gross weight."
            )
        )

    # Commit gross weighment
    now = datetime.now(timezone.utc)
    log.gross_weight_qt = gross_weight
    log.current_state = "WEIGHED_GROSS"
    log.updated_at = now
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    return WeighmentResponse(
        transaction_id=log.transaction_id,
        mandi_id=log.mandi_id,
        farmer_id=log.farmer_id,
        gross_weight_qt=float(log.gross_weight_qt),
        tare_weight_qt=None,
        net_weight_qt=None,
        current_state=log.current_state,
        timestamp=now.isoformat(),
        message=f"Gross weight {gross_weight:.2f} qt captured successfully. Vehicle routed to unloading."
    )


def record_tare_weight(
    db: Session,
    request: TareWeightCaptureRequest,
    current_user: Optional[User] = None
) -> WeighmentResponse:
    """
    Captures tare weight telemetry for an unloaded vehicle exiting the weighbridge.
    Validates tare weight (>= 0), ensures gross > tare, computes net weight = gross - tare,
    enforces farmer yield ceiling invariance, and transitions state to WEIGHED_TARE.
    """
    tare_weight = float(request.tare_weight_qt)
    if tare_weight < 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tare weight cannot be negative."
        )

    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="capture tare weight")

    # Idempotency check: repeated tare telemetry with identical reading
    if log.current_state in ("WEIGHED_TARE", "BILL_GENERATED"):
        if log.tare_weight_qt is not None and abs(float(log.tare_weight_qt) - tare_weight) < 1e-4:
            return WeighmentResponse(
                transaction_id=log.transaction_id,
                mandi_id=log.mandi_id,
                farmer_id=log.farmer_id,
                gross_weight_qt=float(log.gross_weight_qt),
                tare_weight_qt=float(log.tare_weight_qt),
                net_weight_qt=float(log.net_weight_qt),
                current_state=log.current_state,
                timestamp=log.updated_at.isoformat(),
                message="Tare weight already captured and net weight settled (idempotent repeated telemetry)."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicting tare weight telemetry for transaction '{log.transaction_id}' already in {log.current_state}."
            )

    # Valid prior state: must be WEIGHED_GROSS
    if log.current_state != "WEIGHED_GROSS" or log.gross_weight_qt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot record tare weight: transaction is in state '{log.current_state}'. "
                f"Gross weight must be recorded before tare weighment."
            )
        )

    gross_weight = float(log.gross_weight_qt)

    # Invariant: gross must be strictly greater than tare
    if tare_weight >= gross_weight:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid weighment reading: Tare weight ({tare_weight:.2f} qt) cannot be "
                f"greater than or equal to Gross weight ({gross_weight:.2f} qt)."
            )
        )

    # Net weight calculation
    net_weight = round(gross_weight - tare_weight, 2)

    with lock_manager.acquire_lock(f"lock:weighbridge:farmer:{log.farmer_id}"):
        # Enforce Farmer Yield Ceiling Invariant (AC-005)
        farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
        if farmer:
            other_delivered = db.query(
                func.coalesce(func.sum(ProcurementLog.net_weight_qt), 0.0)
            ).filter(
                ProcurementLog.farmer_id == log.farmer_id,
                ProcurementLog.transaction_id != log.transaction_id,
                ProcurementLog.current_state.in_([
                    "WEIGHED_TARE", "BILL_GENERATED", "DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"
                ])
            ).scalar()

            total_delivered = float(other_delivered) + net_weight
            ceiling = float(farmer.production_ceiling_qt)
            if total_delivered > ceiling:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Farmer yield ceiling exceeded: Net delivered weight {net_weight:.2f} qt "
                        f"plus prior deliveries {float(other_delivered):.2f} qt ({total_delivered:.2f} qt total) "
                        f"exceeds registered production ceiling of {ceiling:.2f} qt."
                    )
                )

        # Atomically persist tare, net weight, and state transition
        now = datetime.now(timezone.utc)
        log.tare_weight_qt = tare_weight
        log.net_weight_qt = net_weight
        log.current_state = "WEIGHED_TARE"
        log.updated_at = now
        try:
            db.commit()
            db.refresh(log)
        except Exception:
            db.rollback()
            raise

    return WeighmentResponse(
        transaction_id=log.transaction_id,
        mandi_id=log.mandi_id,
        farmer_id=log.farmer_id,
        gross_weight_qt=gross_weight,
        tare_weight_qt=tare_weight,
        net_weight_qt=net_weight,
        current_state=log.current_state,
        timestamp=now.isoformat(),
        message=f"Weighment complete: Gross={gross_weight:.2f} qt, Tare={tare_weight:.2f} qt, Net={net_weight:.2f} qt."
    )


def record_unified_weighment(
    db: Session,
    request: UnifiedWeighmentRequest,
    current_user: Optional[User] = None
) -> WeighmentResponse:
    """
    Atomically records both gross and tare weights in a single telemetry transaction.
    Computes net weight = gross - tare, validates weights, checks yield ceiling,
    and transitions to WEIGHED_TARE.
    """
    gross_weight = float(request.gross_weight_qt)
    tare_weight = float(request.tare_weight_qt)

    if gross_weight <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gross weight must be strictly greater than zero quintals."
        )

    if tare_weight < 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tare weight cannot be negative."
        )

    if tare_weight >= gross_weight:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid weighment reading: Tare weight ({tare_weight:.2f} qt) cannot be "
                f"greater than or equal to Gross weight ({gross_weight:.2f} qt)."
            )
        )

    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="capture unified weighment")

    # Idempotency check: repeated submission of exact same weighment
    if log.current_state in ("WEIGHED_TARE", "BILL_GENERATED"):
        if (
            log.gross_weight_qt is not None
            and abs(float(log.gross_weight_qt) - gross_weight) < 1e-4
            and log.tare_weight_qt is not None
            and abs(float(log.tare_weight_qt) - tare_weight) < 1e-4
        ):
            return WeighmentResponse(
                transaction_id=log.transaction_id,
                mandi_id=log.mandi_id,
                farmer_id=log.farmer_id,
                gross_weight_qt=float(log.gross_weight_qt),
                tare_weight_qt=float(log.tare_weight_qt),
                net_weight_qt=float(log.net_weight_qt),
                current_state=log.current_state,
                timestamp=log.updated_at.isoformat(),
                message="Weighment already captured (idempotent repeated telemetry)."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicting weighment telemetry for transaction '{log.transaction_id}' already in {log.current_state}."
            )

    # State validation
    allowed_states = ("ROUTED_TO_WEIGHBRIDGE", "QUALITY_APPROVED", "WEIGHED_GROSS")
    if log.current_state not in allowed_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot perform weighment: transaction is in state '{log.current_state}'. "
                f"Vehicle must be in 'ROUTED_TO_WEIGHBRIDGE' or 'QUALITY_APPROVED'."
            )
        )

    # For unified weighment, both gross and tare are captured atomically.
    # Set intermediate gross weight state
    prior_state = log.current_state
    log.gross_weight_qt = gross_weight
    log.current_state = "WEIGHED_GROSS"

    # Lifecycle validation with payload
    is_valid, err_msg, _ = validate_lifecycle_transition(
        log.current_state,
        "WEIGHED_TARE",
        payload_fields={"gross_weight_qt": gross_weight, "tare_weight_qt": tare_weight},
        current_log=log
    )
    if not is_valid:
        log.current_state = prior_state
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot perform weighment: {err_msg}"
        )

    net_weight = round(gross_weight - tare_weight, 2)

    # Enforce Farmer Yield Ceiling Invariant (AC-005) under distributed lock
    with lock_manager.acquire_lock(f"lock:weighbridge:farmer:{log.farmer_id}"):
        farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
        if farmer:
            other_delivered = db.query(
                func.coalesce(func.sum(ProcurementLog.net_weight_qt), 0.0)
            ).filter(
                ProcurementLog.farmer_id == log.farmer_id,
                ProcurementLog.transaction_id != log.transaction_id,
                ProcurementLog.current_state.in_([
                    "WEIGHED_TARE", "BILL_GENERATED", "DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"
                ])
            ).scalar()

            total_delivered = float(other_delivered) + net_weight
            ceiling = float(farmer.production_ceiling_qt)
            if total_delivered > ceiling:
                log.current_state = prior_state
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Farmer yield ceiling exceeded: Net delivered weight {net_weight:.2f} qt "
                        f"plus prior deliveries {float(other_delivered):.2f} qt ({total_delivered:.2f} qt total) "
                        f"exceeds registered production ceiling of {ceiling:.2f} qt."
                    )
                )

        # Atomically persist weights
        now = datetime.now(timezone.utc)
        log.gross_weight_qt = gross_weight
        log.tare_weight_qt = tare_weight
        log.net_weight_qt = net_weight
        log.current_state = "WEIGHED_TARE"
        log.updated_at = now
        try:
            db.commit()
            db.refresh(log)
        except Exception:
            db.rollback()
            raise

    return WeighmentResponse(
        transaction_id=log.transaction_id,
        mandi_id=log.mandi_id,
        farmer_id=log.farmer_id,
        gross_weight_qt=gross_weight,
        tare_weight_qt=tare_weight,
        net_weight_qt=net_weight,
        current_state=log.current_state,
        timestamp=now.isoformat(),
        message=f"Atomic weighment complete: Gross={gross_weight:.2f} qt, Tare={tare_weight:.2f} qt, Net={net_weight:.2f} qt."
    )


def get_weighment_details(
    db: Session,
    transaction_id: str,
    current_user: Optional[User] = None
) -> WeighmentResponse:
    """
    Retrieves current weighment telemetry and settlement state for a transaction.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="inspect weighment details")

    return WeighmentResponse(
        transaction_id=log.transaction_id,
        mandi_id=log.mandi_id,
        farmer_id=log.farmer_id,
        gross_weight_qt=float(log.gross_weight_qt) if log.gross_weight_qt else 0.0,
        tare_weight_qt=float(log.tare_weight_qt) if log.tare_weight_qt else None,
        net_weight_qt=float(log.net_weight_qt) if log.net_weight_qt else None,
        current_state=log.current_state,
        timestamp=log.updated_at.isoformat(),
        message=f"Transaction is currently in '{log.current_state}' state."
    )
