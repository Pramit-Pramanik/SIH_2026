from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies.auth import require_roles, assert_transaction_scope
from backend.app.dependencies.get_db import get_db
from backend.app.models.user import User
from backend.app.models.mandi import Mandi
from backend.app.models.log import ProcurementLog
from backend.app.schemas.queue import (
    QueueDispatchResponse,
    QueueListResponse,
    QueueStatusResponse,
    QueueOverviewResponse,
    ScaleConfigRequest,
    ScaleConfigResponse
)
from backend.app.services.quality_service import (
    dispatch_top_vehicle_from_queue,
    get_mandi_queue_list,
    get_vehicle_queue_status,
    rerank_mandi_queue
)

router = APIRouter(prefix="/queue", tags=["DCDQ Priority Queue"])


@router.get(
    "/state",
    response_model=QueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active mandi priority queue state via query param (AC-006)"
)
def get_queue_state(
    mandi_id: Optional[int] = Query(None, gt=0, description="Target APMC mandi identifier"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR", "INSPECTOR"], strict=True))
) -> QueueListResponse:
    """
    Retrieves the full active vehicle queue for the specified mandi via query parameter.
    Requires authenticated operational role (ADMIN, SUPERVISOR, OPERATOR, INSPECTOR).
    FARMER is denied access (HTTP 403). Unauthenticated callers receive HTTP 401.
    SUPERVISOR/OPERATOR/INSPECTOR restricted to their assigned mandi.
    """
    if mandi_id is not None:
        target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
        if not target_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mandi with ID {mandi_id} not found."
            )
        effective_mandi = mandi_id
    else:
        if current_user.role != "ADMIN" and current_user.mandi_id is not None:
            effective_mandi = current_user.mandi_id
        else:
            first_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
            if not first_mandi:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No APMC mandis found in database."
                )
            effective_mandi = first_mandi.mandi_id

    # Enforce mandi scope
    assert_transaction_scope(target=effective_mandi, current_user=current_user, action_desc="read queue state")

    return get_mandi_queue_list(db=db, mandi_id=effective_mandi)


@router.get(
    "/{mandi_id}",
    response_model=QueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active mandi priority queue (AC-006)"
)
def list_active_queue(
    mandi_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR", "INSPECTOR"], strict=True))
) -> QueueListResponse:
    """
    Retrieves the full active vehicle queue for the specified mandi, ranked in descending
    order of DCDQ Priority Score (S_i) via Redis ZSET retrieval.
    Requires authenticated operational role (ADMIN, SUPERVISOR, OPERATOR, INSPECTOR).
    FARMER is denied access (HTTP 403). Unauthenticated callers receive HTTP 401.
    SUPERVISOR/OPERATOR/INSPECTOR restricted to their assigned mandi.
    """
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )

    # Enforce mandi scope
    assert_transaction_scope(target=mandi_id, current_user=current_user, action_desc="read queue")

    return get_mandi_queue_list(db=db, mandi_id=mandi_id)


@router.post(
    "/{mandi_id}/dispatch",
    response_model=QueueDispatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Dispatch highest-priority vehicle to weighbridge"
)
def dispatch_vehicle(
    mandi_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"], strict=True))
) -> QueueDispatchResponse:
    """
    Pops the highest-priority vehicle from the queue (ZPOPMAX with deterministic tie-breaking)
    and transitions its transaction state to ROUTED_TO_WEIGHBRIDGE.
    """
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    return dispatch_top_vehicle_from_queue(db=db, mandi_id=mandi_id, current_user=current_user)


@router.post(
    "/{mandi_id}/rerank",
    response_model=QueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger dynamic queue re-ranking based on elapsed wait time"
)
def rerank_queue(
    mandi_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"], strict=True))
) -> QueueListResponse:
    """
    Explicitly recalculates dynamic anti-starvation wait bonuses W_i and re-ranks active vehicles
    in the Redis Sorted Set (ZSET) per DCDQ Algorithm 1 Step 3 (Option B).
    """
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    rerank_mandi_queue(db=db, mandi_id=mandi_id, current_user=current_user)
    return get_mandi_queue_list(db=db, mandi_id=mandi_id)


@router.get(
    "/{mandi_id}/status/{transaction_id}",
    response_model=QueueStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get vehicle queue rank and priority status"
)
def check_vehicle_status(
    mandi_id: int,
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR", "INSPECTOR", "FARMER"], strict=True))
) -> QueueStatusResponse:
    """
    Queries current rank, priority score, and preceding vehicle count for a vehicle in the active queue.
    ADMIN: cross-mandi allowed.
    SUPERVISOR/OPERATOR/INSPECTOR: assigned mandi only.
    FARMER: strictly restricted to their own transaction status.
    Unauthenticated: 401 Unauthorized.
    """
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )

    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    if log.mandi_id != mandi_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' does not belong to Mandi {mandi_id}."
        )

    # Enforce scope:
    # If FARMER: asserts current_user.farmer_id == log.farmer_id
    # If SUPERVISOR/OPERATOR/INSPECTOR: asserts current_user.mandi_id == log.mandi_id
    # If ADMIN: allowed
    assert_transaction_scope(target=log, current_user=current_user, action_desc="read vehicle queue status")

    res = get_vehicle_queue_status(mandi_id=mandi_id, transaction_id=transaction_id, db=db)
    res.current_state = log.current_state
    res.crop_type = log.crop_type
    res.vehicle_number = getattr(log, "vehicle_number", None)
    return res


@router.get(
    "/{mandi_id}/overview",
    response_model=QueueOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get high-level queue overview for farmers and public displays"
)
def get_queue_overview(
    mandi_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR", "INSPECTOR", "FARMER"], strict=True))
) -> QueueOverviewResponse:
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    from backend.app.services.queue_manager import queue_manager
    from backend.app.services.eta_service import get_active_scales, calculate_service_rate_mu
    count = queue_manager.queue_length(mandi_id)
    scales = get_active_scales(db, mandi_id)
    mu, _, _, _ = calculate_service_rate_mu(db, mandi_id)
    rate = mu if mu is not None else 40.0
    return QueueOverviewResponse(
        mandi_id=mandi_id,
        queue_depth=count,
        active_scales=scales,
        service_rate_qt_per_hour_per_scale=round(rate, 2),
        status="OPERATIONAL" if scales > 0 else "DEGRADED",
        message=f"Mandi {mandi_id} has {count} vehicle(s) waiting in priority dispatch queue across {scales} active scale(s)."
    )


@router.get(
    "/{mandi_id}/scales",
    response_model=ScaleConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active weighbridge scales count"
)
def get_scales_config(
    mandi_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR", "INSPECTOR"], strict=True))
) -> ScaleConfigResponse:
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    assert_transaction_scope(target_mandi.mandi_id, current_user, action_desc="read scale configuration")
    from backend.app.services.eta_service import get_active_scales
    count = get_active_scales(db, mandi_id)
    return ScaleConfigResponse(
        mandi_id=mandi_id,
        active_scales=count,
        message=f"Mandi {mandi_id} currently has {count} active operational weighbridge scales."
    )


@router.post(
    "/{mandi_id}/scales",
    response_model=ScaleConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Configure online active weighbridge scales (Demonstrate ETA scaling)"
)
def update_scales_config(
    mandi_id: int,
    payload: ScaleConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR"], strict=True))
) -> ScaleConfigResponse:
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    assert_transaction_scope(target_mandi.mandi_id, current_user, action_desc="configure weighbridge scales")
    from backend.app.services.eta_service import set_active_scales
    new_count = set_active_scales(db, mandi_id, payload.active_scales)
    return ScaleConfigResponse(
        mandi_id=mandi_id,
        active_scales=new_count,
        message=f"Updated active weighbridge scales to {new_count}."
    )


