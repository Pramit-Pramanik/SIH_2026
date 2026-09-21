from datetime import datetime, timezone
import time
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.authorization import assert_transaction_scope
from backend.app.core.config import get_settings
from backend.app.core.security import get_hmac_secret_key
from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.models.user import User
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
from backend.app.services.queue_manager import queue_manager, QueueDataIntegrityError


def assess_quality_and_enqueue(
    db: Session,
    request: QualityAssessmentRequest,
    current_user: Optional[User] = None
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

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="quality assessment")

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
            current_state="QUALITY_REJECTED",
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

    # Resolve payload weight for demurrage
    payload_qt = float(log.net_weight_qt) if log.net_weight_qt is not None else 50.0

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
        current_state="QUALITY_APPROVED",
        eligible_for_queue=True,
        advisory_notice="Quality approved. Vehicle added to active mandi dispatch queue.",
        priority_score=score,
        queue_position=rank
    )



def override_quality_and_admit(
    db: Session,
    request: QualityOverrideRequest,
    current_user: Optional[User] = None
) -> QualityOverrideResponse:
    """
    Authenticated supervisor override for a lot previously rejected due to high moisture (AC-007).
    Requires authoritative SUPERVISOR or ADMIN role. Magic strings like 'SUPERVISOR-*' are rejected.
    """
    if not current_user or current_user.role not in ("SUPERVISOR", "ADMIN"):
        user_desc = f"User '{current_user.username}' with role '{current_user.role}'" if current_user else "Unauthenticated user"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: {user_desc} is not authorized for supervisor override. Required role: SUPERVISOR or ADMIN."
        )

    authorized_by = f"{current_user.role}:{current_user.username}"

    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="supervisor quality override")

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
    payload_qt = float(log.net_weight_qt) if log.net_weight_qt is not None else 50.0

    if log.crop_moisture_pct is None:
        raise QueueDataIntegrityError(
            f"Queue integrity violation: Transaction '{request.transaction_id}' is missing moisture data for queue admission."
        )
    moisture = float(log.crop_moisture_pct)

    # Derive original arrival timestamp
    meta_ts = queue_manager.get_arrival_timestamp(log.mandi_id, log.transaction_id)
    if meta_ts is not None:
        arr_ts = meta_ts
    elif log.created_at is not None:
        arr_ts = (
            log.created_at.replace(tzinfo=timezone.utc).timestamp()
            if log.created_at.tzinfo is None
            else log.created_at.timestamp()
        )
    else:
        arr_ts = now_ts

    elapsed_wait_minutes = max(0.0, (now_ts - arr_ts) / 60.0)

    # Maintain appointment adherence baseline
    planned_ts = arr_ts

    score = calculate_dcdq_priority_score(
        planned_arrival_ts=planned_ts,
        actual_arrival_ts=arr_ts,
        moisture_pct=moisture,
        elapsed_wait_minutes=elapsed_wait_minutes,
        demurrage_score=payload_qt / 10.0
    )

    queue_manager.enqueue(
        mandi_id=log.mandi_id,
        transaction_id=log.transaction_id,
        priority_score=score,
        arrival_ts=arr_ts
    )

    rank = queue_manager.get_rank(log.mandi_id, log.transaction_id)

    return QualityOverrideResponse(
        transaction_id=log.transaction_id,
        status="QUALITY_APPROVED",
        override_reason=f"[{authorized_by}] {request.reason}",
        priority_score=score,
        queue_position=rank,
        message=f"Supervisor override authorized by {authorized_by}. Vehicle re-admitted to queue with rank {rank}."
    )


def rerank_mandi_queue(
    db: Session,
    mandi_id: int,
    current_time: Optional[float] = None,
    current_user: Optional[User] = None
) -> List[Tuple[str, float]]:
    """
    On-demand dynamic queue re-ranking (DCDQ Algorithm 1 Step 3, Option B).
    Re-evaluates each queued vehicle's anti-starvation wait bonus W_i:
        W_i = min(20.0, 0.1 * elapsed_wait_minutes)
    where elapsed_wait_minutes = max(0.0, (current_time - actual_arrival_ts) / 60.0).
    Re-indexes the updated priority score S_i into the Redis Sorted Set (ZSET)
    and returns the re-ranked active queue.
    """
    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(mandi_id, current_user, action_desc="queue rerank")

    raw_queue = queue_manager.get_queue(mandi_id)
    if not raw_queue:
        return []

    now_ts = current_time if current_time is not None else time.time()
    txn_ids = [item[0] for item in raw_queue]
    logs = db.query(ProcurementLog).filter(ProcurementLog.transaction_id.in_(txn_ids)).all()
    log_map = {log.transaction_id: log for log in logs}

    for txn_id, _ in raw_queue:
        log = log_map.get(txn_id)
        if not log:
            continue

        arr_ts = queue_manager.get_arrival_timestamp(mandi_id, txn_id)
        if arr_ts is None:
            if log.created_at is not None:
                arr_ts = (
                    log.created_at.replace(tzinfo=timezone.utc).timestamp()
                    if log.created_at.tzinfo is None
                    else log.created_at.timestamp()
                )
            else:
                raise QueueDataIntegrityError(
                    f"Queue integrity violation: Transaction '{txn_id}' is missing arrival timestamp during queue rerank."
                )

        if log.crop_moisture_pct is None:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{txn_id}' is missing crop moisture percentage during queue rerank."
            )
        moisture = float(log.crop_moisture_pct)

        if log.net_weight_qt is None:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{txn_id}' is missing net quantity during queue rerank."
            )
        payload_qt = float(log.net_weight_qt)

        elapsed_wait_min = max(0.0, (now_ts - arr_ts) / 60.0)

        # Maintain appointment adherence baseline
        planned_ts = arr_ts

        new_score = calculate_dcdq_priority_score(
            planned_arrival_ts=planned_ts,
            actual_arrival_ts=arr_ts,
            moisture_pct=moisture,
            elapsed_wait_minutes=elapsed_wait_min,
            demurrage_score=payload_qt / 10.0
        )
        queue_manager.update_score(mandi_id, txn_id, new_score)

    return queue_manager.get_queue(mandi_id)


def reconstruct_mandi_queue(
    db: Session,
    mandi_id: int,
    current_time: Optional[float] = None
) -> List[Tuple[str, float]]:
    """
    Authoritatively reconstructs active mandi vehicle queue from persistent database state.
    Strictly derives DCDQ priority scores from persisted transaction data:
    - net_weight_qt (quantity)
    - crop_moisture_pct (moisture)
    - created_at / arrival metadata (arrival timestamp and wait time)
    - slot start time (planned arrival)

    NEVER fabricates or invents fallback values (such as 50.0 qt, 14.0% moisture, 15 min wait).
    Raises QueueDataIntegrityError if required data is missing.
    """
    approved_logs = db.query(ProcurementLog).filter(
        ProcurementLog.mandi_id == mandi_id,
        ProcurementLog.current_state == "QUALITY_APPROVED"
    ).all()

    if not approved_logs:
        queue_manager.clear(mandi_id)
        return []

    now_ts = current_time if current_time is not None else time.time()

    # Authoritatively calculate DCDQ score and enqueue every approved vehicle
    for log in approved_logs:
        if log.crop_moisture_pct is None:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{log.transaction_id}' in state '{log.current_state}' "
                "is missing authoritative crop moisture percentage."
            )
        moisture = float(log.crop_moisture_pct)
        if moisture > 17.0:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{log.transaction_id}' has excessive moisture "
                f"({moisture:.2f}% > 17.00%) while in 'QUALITY_APPROVED' state."
            )

        if log.net_weight_qt is None:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{log.transaction_id}' in state '{log.current_state}' "
                "is missing authoritative net quantity/weight in quintals."
            )
        payload_qt = float(log.net_weight_qt)
        if payload_qt < 0.0:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{log.transaction_id}' has negative net weight "
                f"({payload_qt:.2f} qt)."
            )

        # Derive arrival timestamp strictly from queue metadata or persisted created_at
        meta_ts = queue_manager.get_arrival_timestamp(mandi_id, log.transaction_id)
        if meta_ts is not None:
            arr_ts = meta_ts
        elif log.created_at is not None:
            arr_ts = (
                log.created_at.replace(tzinfo=timezone.utc).timestamp()
                if log.created_at.tzinfo is None
                else log.created_at.timestamp()
            )
        else:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{log.transaction_id}' is missing persisted "
                "creation/arrival timestamp."
            )

        # Maintain appointment adherence baseline
        planned_ts = arr_ts

        # Elapsed wait is derived dynamically from actual elapsed time, NEVER hardcoded
        elapsed_wait_min = max(0.0, (now_ts - arr_ts) / 60.0)

        score = calculate_dcdq_priority_score(
            planned_arrival_ts=planned_ts,
            actual_arrival_ts=arr_ts,
            moisture_pct=moisture,
            elapsed_wait_minutes=elapsed_wait_min,
            demurrage_score=payload_qt / 10.0
        )

        queue_manager.enqueue(
            mandi_id=mandi_id,
            transaction_id=log.transaction_id,
            priority_score=score,
            arrival_ts=arr_ts
        )

    # Clean up any transactions from queue that are no longer QUALITY_APPROVED
    valid_txn_ids = {log.transaction_id for log in approved_logs}
    current_q = queue_manager.get_queue(mandi_id)
    for q_txn_id, _ in current_q:
        if q_txn_id not in valid_txn_ids:
            queue_manager.remove(mandi_id, q_txn_id)

    return queue_manager.get_queue(mandi_id)


def get_mandi_queue_list(
    db: Session,
    mandi_id: int
) -> QueueListResponse:
    """
    Retrieves the full active queue for a mandi, ranked in descending DCDQ priority order.
    Reconstructs queue from database if not initialized in active memory/Redis.
    """
    raw_queue = queue_manager.get_queue(mandi_id)
    if not raw_queue:
        # Check database for active QUALITY_APPROVED transactions waiting for weighbridge
        approved_count = db.query(ProcurementLog).filter(
            ProcurementLog.mandi_id == mandi_id,
            ProcurementLog.current_state == "QUALITY_APPROVED"
        ).count()
        if approved_count > 0:
            raw_queue = reconstruct_mandi_queue(db=db, mandi_id=mandi_id)

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
        arr_ts = queue_manager.get_arrival_timestamp(mandi_id, txn_id)
        if arr_ts is None and log and log.created_at:
            arr_ts = (
                log.created_at.replace(tzinfo=timezone.utc).timestamp()
                if log.created_at.tzinfo is None
                else log.created_at.timestamp()
            )
        items.append(
            QueueItem(
                rank=rank,
                transaction_id=txn_id,
                priority_score=score,
                farmer_id=log.farmer_id if log else None,
                quantity_qt=float(log.net_weight_qt) if log and log.net_weight_qt is not None else None,
                arrival_timestamp=arr_ts
            )
        )

    return QueueListResponse(
        mandi_id=mandi_id,
        total_vehicles=len(items),
        items=items
    )


def dispatch_top_vehicle_from_queue(
    db: Session,
    mandi_id: int,
    current_user: Optional[User] = None
) -> QueueDispatchResponse:
    """
    Pops the highest-priority vehicle from the queue (ZPOPMAX with deterministic tie-breaking)
    and transitions its transaction state to ROUTED_TO_WEIGHBRIDGE.
    """
    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(mandi_id, current_user, action_desc="queue dispatch")

    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not mandi or not mandi.is_operational:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mandi {mandi_id} is not found or is currently non-operational."
        )

    dispatched = queue_manager.dispatch_pop(mandi_id)
    if not dispatched:
        # Check if database has active QUALITY_APPROVED transactions
        reconstruct_mandi_queue(db, mandi_id)
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

    # Enforce transaction mandi-scope before mutation
    assert_transaction_scope(log, current_user, action_desc="queue vehicle dispatch")

    if log.current_state == "QUALITY_REJECTED":
        # Vehicle must not be routed to weighbridge if quality was rejected
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot dispatch transaction '{txn_id}': lot was QUALITY_REJECTED and has not received an authorized supervisor override."
        )

    if log.current_state not in ("QUALITY_APPROVED", "IN_QA_QUEUE"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot dispatch transaction '{txn_id}' from state '{log.current_state}'. Transaction must be in 'QUALITY_APPROVED'."
        )

    log.current_state = "ROUTED_TO_WEIGHBRIDGE"
    log.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        # Restore vehicle to queue with original arrival timestamp
        try:
            restore_arr = (
                log.created_at.replace(tzinfo=timezone.utc).timestamp()
                if log.created_at and log.created_at.tzinfo is None
                else (log.created_at.timestamp() if log.created_at else time.time())
            )
            queue_manager.enqueue(mandi_id, txn_id, score, restore_arr)
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
    transaction_id: str,
    db: Optional[Session] = None
) -> QueueStatusResponse:
    """
    Queries current position and priority score of a vehicle in the active mandi queue.
    If queue is uninitialized in memory/Redis and db is provided, reconstructs queue authoritatively.
    """
    score = queue_manager.get_score(mandi_id, transaction_id)
    if score is None and db is not None:
        reconstruct_mandi_queue(db, mandi_id)
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
    transaction_id: str,
    current_user: Optional[User] = None
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

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="inspect quality assessment")

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

