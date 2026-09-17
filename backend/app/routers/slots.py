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
from backend.app.services.reservation_service import (
    reserve_slot_atomic,
    get_slot_availability,
    cancel_slot_reservation
)

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

    # Dynamic Showcase Auto-Provisioning:
    # If no slots exist for the target date, dynamically provision standard operational slots
    if not slots:
        from datetime import time
        standard_hours = [9, 10, 11, 12, 14, 15, 16]
        for hour in standard_hours:
            new_slot = ProcurementSlot(
                mandi_id=mandi_id,
                scheduled_date=target_date,
                start_time=time(hour, 0),
                end_time=time(hour + 1, 0),
                allocated_capacity_qt=500.0,
                booked_capacity_qt=0.0,
                version=1
            )
            db.add(new_slot)
        try:
            db.commit()
            slots = db.query(ProcurementSlot).filter(
                ProcurementSlot.mandi_id == mandi_id,
                ProcurementSlot.scheduled_date == target_date
            ).order_by(ProcurementSlot.start_time.asc()).all()
        except Exception:
            db.rollback()
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
    "/mandi/{mandi_id}/date/{scheduled_date}",
    response_model=List[SlotAvailabilityResponse],
    summary="List Procurement Slots by Mandi and Date",
    description="Retrieves available hourly procurement slots for a specific mandi and scheduled date via path parameters."
)
def list_slots_by_path(
    mandi_id: int,
    scheduled_date: date,
    db: Session = Depends(get_db)
) -> List[SlotAvailabilityResponse]:
    return list_slots(mandi_id=mandi_id, scheduled_date=scheduled_date, db=db)


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


@router.post(
    "/cancel",
    summary="Cancel Slot Reservation",
    description="Cancels an unverified procurement slot appointment, restoring hourly capacity and farmer ceiling."
)
def cancel_reservation(
    payload: dict,
    db: Session = Depends(get_db)
) -> dict:
    txn_id = payload.get("transaction_id")
    if not txn_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="transaction_id is required"
        )
    return cancel_slot_reservation(db=db, transaction_id=txn_id)

