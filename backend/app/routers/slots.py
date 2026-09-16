from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

# Ensure HTTP 422 responses use status.HTTP_422_UNPROCESSABLE_ENTITY without Starlette deprecation warnings
if not hasattr(status, "__dict__") or "HTTP_422_UNPROCESSABLE_ENTITY" not in status.__dict__:
    status.HTTP_422_UNPROCESSABLE_ENTITY = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

from backend.app.dependencies.get_db import get_db
from backend.app.models.slot import ProcurementSlot
from backend.app.schemas.slot import (
    SlotReservationRequest,
    SlotReservationResponse,
    SlotAvailabilityResponse
)
from backend.app.services.reservation_service import reserve_slot_atomic, get_slot_availability

router = APIRouter(prefix="/slots", tags=["Procurement Slots"])


@router.get(
    "",
    response_model=List[SlotAvailabilityResponse],
    summary="List Procurement Slots",
    description="Retrieves available hourly procurement slots for a specific mandi and scheduled date."
)
def list_slots(
    mandi_id: int = Query(..., gt=0, description="Target APMC mandi identifier"),
    scheduled_date: Optional[date] = Query(None, description="Target date (defaults to today)"),
    db: Session = Depends(get_db)
) -> List[SlotAvailabilityResponse]:
    target_date = scheduled_date or date.today()
    slots = db.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == mandi_id,
        ProcurementSlot.scheduled_date == target_date
    ).order_by(ProcurementSlot.start_time.asc()).all()

    result = []
    for slot in slots:
        allocated = float(slot.allocated_capacity_qt)
        booked = float(slot.booked_capacity_qt)
        remaining = max(0.0, allocated - booked)
        result.append(
            SlotAvailabilityResponse(
                slot_id=slot.slot_id,
                mandi_id=slot.mandi_id,
                scheduled_date=str(slot.scheduled_date),
                start_time=str(slot.start_time),
                end_time=str(slot.end_time),
                allocated_capacity_qt=allocated,
                booked_capacity_qt=booked,
                remaining_capacity_qt=remaining
            )
        )
    return result


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
