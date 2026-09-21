from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies.auth import require_roles
from backend.app.dependencies.get_db import get_db
from backend.app.models.user import User
from backend.app.models.mandi import Mandi
from backend.app.schemas.queue import (
    QueueDispatchResponse,
    QueueListResponse,
    QueueStatusResponse
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
    db: Session = Depends(get_db)
) -> QueueListResponse:
    """
    Retrieves the full active vehicle queue for the specified mandi via query parameter.
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
        first_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
        if not first_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No APMC mandis found in database."
            )
        effective_mandi = first_mandi.mandi_id

    return get_mandi_queue_list(db=db, mandi_id=effective_mandi)


@router.get(
    "/{mandi_id}",
    response_model=QueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active mandi priority queue (AC-006)"
)
def list_active_queue(
    mandi_id: int,
    db: Session = Depends(get_db)
) -> QueueListResponse:
    """
    Retrieves the full active vehicle queue for the specified mandi, ranked in descending
    order of DCDQ Priority Score (S_i) via Redis ZSET retrieval.
    """
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
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
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
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
    return dispatch_top_vehicle_from_queue(db=db, mandi_id=mandi_id)


@router.post(
    "/{mandi_id}/rerank",
    response_model=QueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger dynamic queue re-ranking based on elapsed wait time"
)
def rerank_queue(
    mandi_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
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
    rerank_mandi_queue(db=db, mandi_id=mandi_id)
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
    db: Session = Depends(get_db)
) -> QueueStatusResponse:
    """
    Queries current rank, priority score, and preceding vehicle count for a vehicle in the active queue.
    """
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    return get_vehicle_queue_status(mandi_id=mandi_id, transaction_id=transaction_id)
