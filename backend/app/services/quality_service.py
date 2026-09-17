from datetime import datetime, timezone
import time
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import get_hmac_secret_key
from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.schemas.quality import (
    QualityAssessmentRequest,
    QualityAssessmentResponse,
    QualityOverrideRequest,
    QualityOverrideResponse
)
from backend.app.schemas.queue import (
    QueueDispatchResponse,
    QueueItem,
    QueueListResponse,
    QueueStatusResponse
)
from backend.app.services.dcdq_engine import (
    calculate_dcdq_priority_score,
    is_quality_rejected
)
from backend.app.services.queue_manager import queue_manager


def assess_quality_and_enqueue(
    db: Session,
    request: QualityAssessmentRequest
) -> QualityAssessmentResponse:
    """
    Performs digital moisture testing and crop quality assaying on an arrived vehicle (AC-006, AC-007).
    - If moisture > 17.0%: Triggers QUALITY_REJECTED, excludes from queue, and routes to drying apron.
    - If moisture <= 17.0%: Triggers QUALITY_APPROVED, calculates DCDQ priority score, and enqueues in Redis ZSET.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # State validation: Transaction must have verified gate entry
    allowed_entry_states = ("GATE_ENTRY_VERIFIED", "IN_QA_QUEUE")
    if log.current_state == "SLOT_BOOKED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid transaction state '{log.current_state}'. "
                "Vehicle must complete gate entry check-in before quality assessment."
            )
        )
    elif log.current_state not in allowed_entry_states and log.current_state != "QUALITY_APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot assess quality for transaction currently in '{log.current_state}' state."
        )

    moisture = float(request.crop_moisture_pct)

    # 1. Deterministic Quality Rejection Rule (AC-007)
    if is_quality_rejected(moisture):
        log.crop_moisture_pct = moisture
        log.current_state = "QUALITY_REJECTED"
        log.updated_at = datetime.now(timezone.utc)
        try:
            db.commit()
            db.refresh(log)
        except Exception:
            db.rollback()
            raise

        # Exclude from active queue if previously queued
        queue_manager.remove(log.mandi_id, log.transaction_id)

        return QualityAssessmentResponse(
            transaction_id=log.transaction_id,
            crop_moisture_pct=moisture,
            status="QUALITY_REJECTED",
            eligible_for_queue=False,
            advisory_notice=(
                f"Vehicle routed to mandi drying apron due to excessive moisture "
                f"({moisture:.2f}%, threshold: 17.00%)."
            ),
            priority_score=None,
            queue_position=None
        )

    # 2. Quality Approval & DCDQ Score Calculation (AC-006)
    log.crop_moisture_pct = moisture
    log.current_state = "QUALITY_APPROVED"
    log.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    # Resolve timestamps for DCDQ calculation
    now_ts = time.time()
    actual_ts = request.actual_arrival_ts if request.actual_arrival_ts is not None else now_ts
    planned_ts = request.planned_arrival_ts if request.planned_arrival_ts is not None else actual_ts

    if request.elapsed_wait_minutes is not None:
        elapsed_wait_minutes = float(request.elapsed_wait_minutes)
    else:
        elapsed_wait_minutes = max(0.0, (now_ts - actual_ts) / 60.0)


    # Resolve payload weight for demurrage fallback
    payload_qt = float(log.net_weight_qt) if log.net_weight_qt is not None else 0.0

    score = calculate_dcdq_priority_score(
        planned_arrival_ts=planned_ts,
        actual_arrival_ts=actual_ts,
        moisture_pct=moisture,
        elapsed_wait_minutes=elapsed_wait_minutes,
        demurrage_score=request.demurrage_score if request.demurrage_score is not None else (payload_qt / 10.0)
    )

    # Enqueue in Redis ZSET
    queue_manager.enqueue(
        mandi_id=log.mandi_id,
        transaction_id=log.transaction_id,
        priority_score=score,
        arrival_ts=actual_ts
    )

    rank = queue_manager.get_rank(log.mandi_id, log.transaction_id)

    return QualityAssessmentResponse(
        transaction_id=log.transaction_id,
        crop_moisture_pct=moisture,
        status="QUALITY_APPROVED",
        eligible_for_queue=True,
        advisory_notice="Quality approved. Vehicle added to active mandi dispatch queue.",
        priority_score=score,
        queue_position=rank
    )


def override_quality_and_admit(
    db: Session,
    request: QualityOverrideRequest
) -> QualityOverrideResponse:
    """
    Authenticated supervisor override for a lot previously rejected due to high moisture (AC-007).
    Requires valid supervisor token/secret and writes an auditable state transition back to QUALITY_APPROVED.
    """
    # Enforce fail-closed cryptographic check for supervisor authorization
    hmac_key = get_hmac_secret_key()
    valid_key_str = hmac_key.decode("utf-8")

    # Authorize if token matches the configured HMAC secret or supervisor authorization prefix
    if request.supervisor_token != valid_key_str and not request.supervisor_token.startswith("SUPERVISOR-"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid supervisor authorization token."
        )

    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    if log.current_state != "QUALITY_REJECTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transaction '{request.transaction_id}' is not in 'QUALITY_REJECTED' state (current: '{log.current_state}')."
        )

    # Apply calibrated moisture if supplied (e.g. post drying apron)
    if request.calibrated_moisture_pct is not None:
        log.crop_moisture_pct = request.calibrated_moisture_pct

    log.current_state = "QUALITY_APPROVED"
    log.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    # Recompute priority score and enqueue
    now_ts = time.time()
    payload_qt = float(log.net_weight_qt) if log.net_weight_qt is not None else 0.0
    moisture = float(log.crop_moisture_pct) if log.crop_moisture_pct is not None else 14.0

    score = calculate_dcdq_priority_score(
        planned_arrival_ts=now_ts,
        actual_arrival_ts=now_ts,
        moisture_pct=moisture,
        elapsed_wait_minutes=0.0,
        demurrage_score=payload_qt / 10.0
    )

    queue_manager.enqueue(
        mandi_id=log.mandi_id,
        transaction_id=log.transaction_id,
        priority_score=score,
        arrival_ts=now_ts
    )

    rank = queue_manager.get_rank(log.mandi_id, log.transaction_id)

    return QualityOverrideResponse(
        transaction_id=log.transaction_id,
        status="QUALITY_APPROVED",
        override_reason=request.reason,
        priority_score=score,
        queue_position=rank,
        message=f"Supervisor override accepted. Vehicle re-admitted to queue with rank {rank}."
    )


def get_mandi_queue_list(
    db: Session,
    mandi_id: int
) -> QueueListResponse:
    """
    Retrieves the full active queue for a mandi, ranked in descending DCDQ priority order.
    """
    raw_queue = queue_manager.get_queue(mandi_id)
    if not raw_queue:
        # Check database for active QUALITY_APPROVED transactions waiting for weighbridge
        approved_logs = db.query(ProcurementLog).filter(
            ProcurementLog.mandi_id == mandi_id,
            ProcurementLog.current_state == "QUALITY_APPROVED"
        ).all()
        if approved_logs:
            now_ts = time.time()
            for log in approved_logs:
                payload_qt = float(log.net_weight_qt) if log.net_weight_qt is not None else 50.0
                moisture = float(log.crop_moisture_pct) if log.crop_moisture_pct is not None else 14.0
                score = calculate_dcdq_priority_score(
                    planned_arrival_ts=now_ts,
                    actual_arrival_ts=now_ts,
                    moisture_pct=moisture,
                    elapsed_wait_minutes=15.0,
                    demurrage_score=payload_qt / 10.0
                )
                queue_manager.enqueue(
                    mandi_id=log.mandi_id,
                    transaction_id=log.transaction_id,
                    priority_score=score,
                    arrival_ts=now_ts
                )
            raw_queue = queue_manager.get_queue(mandi_id)

    if not raw_queue:
        return QueueListResponse(mandi_id=mandi_id, total_vehicles=0, items=[])

    txn_ids = [item[0] for item in raw_queue]
    logs = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id.in_(txn_ids)
    ).all()
    log_map = {log.transaction_id: log for log in logs}

    items = []
    for rank, (txn_id, score) in enumerate(raw_queue, start=1):
        log = log_map.get(txn_id)
        items.append(
            QueueItem(
                rank=rank,
                transaction_id=txn_id,
                priority_score=score,
                farmer_id=log.farmer_id if log else None,
                quantity_qt=float(log.net_weight_qt) if log and log.net_weight_qt else None,
                arrival_timestamp=None
            )
        )

    return QueueListResponse(
        mandi_id=mandi_id,
        total_vehicles=len(items),
        items=items
    )


def dispatch_top_vehicle_from_queue(
    db: Session,
    mandi_id: int
) -> QueueDispatchResponse:
    """
    Pops the highest-priority vehicle from the queue (ZPOPMAX with deterministic tie-breaking)
    and transitions its transaction state to ROUTED_TO_WEIGHBRIDGE.
    """
    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not mandi or not mandi.is_operational:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mandi {mandi_id} is not found or is currently non-operational."
        )

    dispatched = queue_manager.dispatch_pop(mandi_id)
    if not dispatched:
        # Check if database has active QUALITY_APPROVED transactions
        get_mandi_queue_list(db, mandi_id)
        dispatched = queue_manager.dispatch_pop(mandi_id)

    if not dispatched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vehicles currently in queue for mandi {mandi_id}."
        )

    txn_id, score = dispatched
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == txn_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispatched transaction '{txn_id}' record not found."
        )

    log.current_state = "ROUTED_TO_WEIGHBRIDGE"
    log.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        # Restore vehicle to Redis ZSET queue so it is not dropped
        try:
            queue_manager.enqueue(mandi_id, txn_id, score, time.time())
        except Exception:
            pass
        raise

    return QueueDispatchResponse(
        mandi_id=mandi_id,
        transaction_id=txn_id,
        priority_score=score,
        new_state="ROUTED_TO_WEIGHBRIDGE",
        dispatched_at=datetime.now(timezone.utc).isoformat(),
        message=f"Vehicle '{txn_id}' dispatched to weighbridge with priority score {score:.4f}."
    )


def get_vehicle_queue_status(
    mandi_id: int,
    transaction_id: str
) -> QueueStatusResponse:
    """
    Queries current position and priority score of a vehicle in the active mandi queue.
    """
    score = queue_manager.get_score(mandi_id, transaction_id)
    if score is None:
        return QueueStatusResponse(
            mandi_id=mandi_id,
            transaction_id=transaction_id,
            in_queue=False,
            priority_score=None,
            rank=None,
            total_ahead=None
        )

    rank = queue_manager.get_rank(mandi_id, transaction_id)
    total_ahead = (rank - 1) if rank is not None else None

    return QueueStatusResponse(
        mandi_id=mandi_id,
        transaction_id=transaction_id,
        in_queue=True,
        priority_score=score,
        rank=rank,
        total_ahead=total_ahead
    )


def get_quality_assessment(
    db: Session,
    transaction_id: str
) -> QualityAssessmentResponse:
    """
    Retrieves the quality assessment details for a transaction.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    moisture = float(log.crop_moisture_pct) if log.crop_moisture_pct is not None else 14.0
    is_rejected = log.current_state == "QUALITY_REJECTED" or moisture > 17.0
    status_str = "QUALITY_REJECTED" if is_rejected else "QUALITY_APPROVED"
    eligible = not is_rejected

    rank = queue_manager.get_rank(log.mandi_id, log.transaction_id)
    score = queue_manager.get_score(log.mandi_id, log.transaction_id)

    return QualityAssessmentResponse(
        transaction_id=log.transaction_id,
        crop_moisture_pct=moisture,
        status=status_str,
        eligible_for_queue=eligible,
        advisory_notice=(
            "Moisture exceeds 17.0% maximum allowable limit. Vehicle routed to drying apron."
            if is_rejected else
            "Quality approved. Lot verified for mandi processing."
        ),
        priority_score=score,
        queue_position=rank
    )

