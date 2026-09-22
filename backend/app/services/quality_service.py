from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Tuple
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
    calculate_dcdq_components,
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
    if log.net_weight_qt is None:
        raise QueueDataIntegrityError(
            f"Queue integrity violation: Transaction '{log.transaction_id}' is missing authoritative net quantity (weight in quintals)."
        )
    payload_qt = float(log.net_weight_qt)
    if payload_qt < 0.0:
        raise QueueDataIntegrityError(
            f"Queue integrity violation: Transaction '{log.transaction_id}' has negative net weight ({payload_qt:.2f} qt)."
        )

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
    if log.net_weight_qt is None:
        raise QueueDataIntegrityError(
            f"Queue integrity violation: Transaction '{request.transaction_id}' is missing authoritative net quantity (weight in quintals)."
        )
    payload_qt = float(log.net_weight_qt)
    if payload_qt < 0.0:
        raise QueueDataIntegrityError(
            f"Queue integrity violation: Transaction '{request.transaction_id}' has negative net weight ({payload_qt:.2f} qt)."
        )

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


def recompute_and_get_mandi_queue(
    db: Session,
    mandi_id: int,
    current_time: Optional[float] = None
) -> QueueListResponse:
    """
    Authoritative centralized dynamic DCDQ queue computation and retrieval.
    Re-evaluates every active queued vehicle using canonical DCDQ components:
        S_i = alpha*A_i + beta*D_i + gamma*M_i + lambda*W_i
    where:
        A_i = max(0, 40 - 0.5 * lateness_minutes)
        D_i = min(20, payload_qt / 10.0)
        M_i = piecewise moisture curve (disqualified if > 17%)
        W_i = min(20, 0.1 * elapsed_wait_minutes)

    Steps:
    1. Reads active queue members and reconciles with DB QUALITY_APPROVED transactions.
    2. Resolves authoritative transactions from DB.
    3. Resolves arrival timestamps (and planned arrival).
    4. Resolves moisture (raises QueueDataIntegrityError if missing or > 17%).
    5. Resolves quantity (raises QueueDataIntegrityError if missing or < 0).
    6. Calculates current elapsed wait (applying isolated showcase time offset for showcase records only).
    7. Calculates DCDQ score and component decomposition (A, D, M, W, S).
    8. Updates Redis ZSET (and in-memory registry) with newly recomputed score.
    9. Returns deterministically ordered QueueListResponse with full component breakdown.
    """
    now_ts = current_time if current_time is not None else time.time()

    # Query all authoritative QUALITY_APPROVED transactions for this mandi
    approved_logs = db.query(ProcurementLog).filter(
        ProcurementLog.mandi_id == mandi_id,
        ProcurementLog.current_state == "QUALITY_APPROVED"
    ).all()

    if not approved_logs:
        # Clear any stale entries from Redis/memory
        queue_manager.clear(mandi_id)
        return QueueListResponse(mandi_id=mandi_id, total_vehicles=0, items=[])

    approved_map = {log.transaction_id: log for log in approved_logs}
    valid_txn_ids = set(approved_map.keys())

    # Remove any members from Redis queue that are no longer QUALITY_APPROVED
    raw_queue = queue_manager.get_queue(mandi_id)
    for q_txn_id, _ in raw_queue:
        if q_txn_id not in valid_txn_ids:
            queue_manager.remove(mandi_id, q_txn_id)

    computed_components_map: Dict[str, dict] = {}
    wait_minutes_map: Dict[str, float] = {}

    for log in approved_logs:
        txn_id = log.transaction_id

        # 4. Resolve moisture
        if log.crop_moisture_pct is None:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{txn_id}' is missing crop moisture percentage."
            )
        moisture = float(log.crop_moisture_pct)
        if moisture > 17.0:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{txn_id}' has excessive moisture "
                f"({moisture:.2f}% > 17.00%) while in 'QUALITY_APPROVED' state."
            )

        # 5. Resolve quantity
        if log.net_weight_qt is None:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{txn_id}' is missing net quantity (weight in quintals)."
            )
        payload_qt = float(log.net_weight_qt)
        if payload_qt < 0.0:
            raise QueueDataIntegrityError(
                f"Queue integrity violation: Transaction '{txn_id}' has negative net weight ({payload_qt:.2f} qt)."
            )

        # 3. Resolve arrival timestamp
        meta_ts = queue_manager.get_arrival_timestamp(mandi_id, txn_id)
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
                f"Queue integrity violation: Transaction '{txn_id}' is missing persisted arrival/creation timestamp."
            )

        # Resolve planned arrival timestamp (from slot if available, else arrival timestamp)
        planned_ts = arr_ts
        if log.slot and log.scheduled_date:
            try:
                planned_dt = datetime.combine(log.scheduled_date, log.slot.start_time).replace(tzinfo=timezone.utc)
                planned_ts = planned_dt.timestamp()
            except Exception:
                planned_ts = arr_ts

        # 6. Calculate current elapsed wait
        # Showcase isolated simulation clock offset (never applied to production transactions!)
        is_showcase = bool(
            log.is_showcase
            or log.demo_run_id is not None
            or txn_id.startswith("TXN-SIM-")
            or txn_id.startswith("TXN-DEMO-")
        )
        showcase_offset_sec = (queue_manager.get_showcase_time_offset(mandi_id) * 60.0) if is_showcase else 0.0
        effective_now = now_ts + showcase_offset_sec
        elapsed_wait_min = max(0.0, (effective_now - arr_ts) / 60.0)

        # 7. Calculate DCDQ components
        components = calculate_dcdq_components(
            planned_arrival_ts=planned_ts,
            actual_arrival_ts=arr_ts,
            moisture_pct=moisture,
            elapsed_wait_minutes=elapsed_wait_min,
            payload_quintals=payload_qt
        )

        computed_components_map[txn_id] = {
            **components,
            "planned_ts": planned_ts,
            "arr_ts": arr_ts,
            "moisture": moisture,
            "payload_qt": payload_qt
        }
        wait_minutes_map[txn_id] = round(elapsed_wait_min, 2)

        # 8. Update Redis ZSET with authoritative newly recomputed score
        queue_manager.enqueue(
            mandi_id=mandi_id,
            transaction_id=txn_id,
            priority_score=components["S"],
            arrival_ts=arr_ts
        )

    # 9. Return ordered results from queue_manager (deterministic tie-breaking)
    ordered_queue = queue_manager.get_queue(mandi_id)
    items = []
    for rank, (txn_id, score) in enumerate(ordered_queue, start=1):
        log = approved_map.get(txn_id)
        comp = computed_components_map.get(txn_id, {})
        items.append(
            QueueItem(
                rank=rank,
                transaction_id=txn_id,
                priority_score=score,
                farmer_id=log.farmer_id if log else None,
                crop_type=log.crop_type if (log and log.crop_type) else "Wheat",
                quantity_qt=comp.get("payload_qt", float(log.net_weight_qt) if log and log.net_weight_qt is not None else None),
                arrival_timestamp=comp.get("arr_ts"),
                planned_arrival_ts=comp.get("planned_ts"),
                actual_arrival_ts=comp.get("arr_ts"),
                score_a=comp.get("A"),
                score_d=comp.get("D"),
                score_m=comp.get("M"),
                score_w=comp.get("W"),
                wait_minutes=wait_minutes_map.get(txn_id),
                moisture_pct=comp.get("moisture"),
                status=log.current_state if log else "QUALITY_APPROVED",
                is_showcase=bool((log.is_showcase if log else False) or txn_id.startswith("TXN-SIM-") or txn_id.startswith("TXN-DEMO-"))
            )
        )

    # 10. Enrich items with authoritative M(t)/E_k/c(t) ETA calculations
    from backend.app.services.eta_service import calculate_queue_etas
    items = calculate_queue_etas(db=db, mandi_id=mandi_id, queue_items=items, current_time=now_ts)

    return QueueListResponse(
        mandi_id=mandi_id,
        total_vehicles=len(items),
        items=items
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
    and composite priority score S_i via recompute_and_get_mandi_queue.
    Re-indexes the updated priority score S_i into Redis Sorted Set (ZSET)
    and returns the re-ranked active queue.
    """
    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(mandi_id, current_user, action_desc="queue rerank")

    recompute_and_get_mandi_queue(db=db, mandi_id=mandi_id, current_time=current_time)
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
    recompute_and_get_mandi_queue(db=db, mandi_id=mandi_id, current_time=current_time)
    return queue_manager.get_queue(mandi_id)


def get_mandi_queue_list(
    db: Session,
    mandi_id: int
) -> QueueListResponse:
    """
    Retrieves the full active queue for a mandi, ranked in descending DCDQ priority order.
    Dynamically recomputes scores so that every queue retrieval reflects current elapsed wait time.
    """
    return recompute_and_get_mandi_queue(db=db, mandi_id=mandi_id)


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

    eta_minutes = None
    payload_ahead_qt = None
    service_rate = None
    active_scales = None
    eta_status = None

    if db is not None:
        queue_resp = recompute_and_get_mandi_queue(db, mandi_id)
        for item in queue_resp.items:
            if item.transaction_id == transaction_id:
                eta_minutes = item.eta_minutes
                payload_ahead_qt = item.payload_ahead_qt
                service_rate = item.service_rate_qt_per_hour_per_scale
                active_scales = item.active_scales
                eta_status = item.eta_status
                break

    return QueueStatusResponse(
        mandi_id=mandi_id,
        transaction_id=transaction_id,
        in_queue=True,
        priority_score=score,
        rank=rank,
        total_ahead=total_ahead,
        eta_minutes=eta_minutes,
        payload_ahead_qt=payload_ahead_qt,
        service_rate_qt_per_hour_per_scale=service_rate,
        active_scales=active_scales,
        eta_status=eta_status
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

    if log.crop_moisture_pct is None:
        raise QueueDataIntegrityError(
            f"Queue integrity violation: Transaction '{transaction_id}' is missing authoritative crop moisture percentage."
        )
    moisture = float(log.crop_moisture_pct)
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

