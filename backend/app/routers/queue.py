from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.schemas.queue import (
    QueueDispatchResponse,
    QueueListResponse,
    QueueStatusResponse
)
from backend.app.services.quality_service import (
    dispatch_top_vehicle_from_queue,
    get_mandi_queue_list,
    get_vehicle_queue_status
)

router = APIRouter(prefix="/queue", tags=["DCDQ Priority Queue"])


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
    return get_mandi_queue_list(db=db, mandi_id=mandi_id)


@router.post(
    "/{mandi_id}/dispatch",
    response_model=QueueDispatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Dispatch highest-priority vehicle to weighbridge"
)
def dispatch_vehicle(
    mandi_id: int,
    db: Session = Depends(get_db)
) -> QueueDispatchResponse:
    """
    Pops the highest-priority vehicle from the queue (ZPOPMAX with deterministic tie-breaking)
    and transitions its transaction state to ROUTED_TO_WEIGHBRIDGE.
    """
    return dispatch_top_vehicle_from_queue(db=db, mandi_id=mandi_id)


@router.get(
    "/{mandi_id}/status/{transaction_id}",
    response_model=QueueStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get vehicle queue rank and priority status"
)
def check_vehicle_status(
    mandi_id: int,
    transaction_id: str
) -> QueueStatusResponse:
    """
    Queries current rank, priority score, and preceding vehicle count for a vehicle in the active queue.
    """
    return get_vehicle_queue_status(mandi_id=mandi_id, transaction_id=transaction_id)
