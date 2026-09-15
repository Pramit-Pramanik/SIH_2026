from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.schemas.slot import (
    SlotReservationRequest,
    SlotReservationResponse,
    SlotAvailabilityResponse
)
from backend.app.services.reservation_service import reserve_slot_atomic, get_slot_availability

router = APIRouter(prefix="/slots", tags=["Procurement Slots"])


@router.get(
    "/{slot_id}",
    response_model=SlotAvailabilityResponse,
    summary="Get Slot Availability",
    description="Retrieves current capacity and availability status for an hourly procurement slot."
)
def get_slot_status(
    slot_id: int,
    db: Session = Depends(get_db)
) -> SlotAvailabilityResponse:
    return get_slot_availability(db=db, slot_id=slot_id)


@router.post(
    "/reserve",
    response_model=SlotReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve Procurement Slot",
    description="Atomically reserves delivery capacity in an hourly slot with yield ceiling enforcement and HMAC gate pass generation (AC-002, AC-003, AC-005)."
)
def reserve_slot(
    payload: SlotReservationRequest,
    db: Session = Depends(get_db)
) -> SlotReservationResponse:
    return reserve_slot_atomic(
        db=db,
        mandi_id=payload.mandi_id,
        slot_id=payload.slot_id,
        farmer_id=payload.farmer_id,
        requested_qty_qt=payload.requested_qty_qt
    )
