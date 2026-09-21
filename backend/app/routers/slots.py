from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# Ensure HTTP 422 responses use status.HTTP_422_UNPROCESSABLE_ENTITY without Starlette deprecation warnings
if not hasattr(status, "__dict__") or "HTTP_422_UNPROCESSABLE_ENTITY" not in status.__dict__:
    status.HTTP_422_UNPROCESSABLE_ENTITY = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

from backend.app.core.authorization import assert_transaction_scope
from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
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


def get_authenticated_farmer_id(user: User, db: Session) -> Optional[int]:
    """
    Resolves the associated farmer_id for an authenticated user.
    Authoritative resolution via User.farmer_id foreign key.
    """
    if getattr(user, "farmer_id", None) is not None:
        return user.farmer_id

    # Fallback to direct lookup in farmers table by user_id
    matched = db.query(Farmer).filter(Farmer.farmer_id == user.user_id).first()
    if matched:
        return matched.farmer_id

    return None


from pydantic import BaseModel, Field


class SlotProvisionRequest(BaseModel):
    mandi_id: int = Field(..., gt=0, description="Target APMC mandi identifier")
    scheduled_date: Optional[date] = Field(None, description="Target date to provision slots for")


def provision_standard_slots(
    db: Session,
    mandi_id: int,
    target_date: date,
    standard_hours: Optional[List[int]] = None
) -> List[ProcurementSlot]:
    """
    Deterministically provisions standard operational slots for a given mandi and date.
    Default operational hours: 09:00, 10:00, 11:00, 12:00, 14:00, 15:00, 16:00 (500 qt capacity each).
    """
    from datetime import time
    hours = standard_hours or [9, 10, 11, 12, 14, 15, 16]
    created = False
    for hour in hours:
        existing = db.query(ProcurementSlot).filter(
            ProcurementSlot.mandi_id == mandi_id,
            ProcurementSlot.scheduled_date == target_date,
            ProcurementSlot.start_time == time(hour, 0)
        ).first()
        if not existing:
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
            created = True
    if created:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return db.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == mandi_id,
        ProcurementSlot.scheduled_date == target_date
    ).order_by(ProcurementSlot.start_time.asc()).all()


@router.post(
    "/provision",
    response_model=List[SlotAvailabilityResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision Standard Procurement Slots",
    description="Explicit administrative / showcase endpoint to provision standard hourly procurement slots for a target date."
)
def provision_slots(
    payload: SlotProvisionRequest,
    db: Session = Depends(get_db)
) -> List[SlotAvailabilityResponse]:
    target_date = payload.scheduled_date or date.today()
    slots = provision_standard_slots(db=db, mandi_id=payload.mandi_id, target_date=target_date)
    return [
        SlotAvailabilityResponse(
            slot_id=s.slot_id,
            mandi_id=s.mandi_id,
            scheduled_date=str(s.scheduled_date),
            start_time=str(s.start_time),
            end_time=str(s.end_time),
            allocated_capacity_qt=float(s.allocated_capacity_qt),
            booked_capacity_qt=float(s.booked_capacity_qt),
            remaining_capacity_qt=max(0.0, float(s.allocated_capacity_qt) - float(s.booked_capacity_qt))
        )
        for s in slots
    ]


@router.get(
    "",
    response_model=List[SlotAvailabilityResponse],
    summary="List Procurement Slots",
    description="Retrieves available hourly procurement slots for a specific mandi and scheduled date."
)
def list_slots(
    mandi_id: int = Query(..., gt=0, description="Target APMC mandi identifier"),
    scheduled_date: Optional[date] = Query(None, description="Target date (defaults to today)"),
    auto_provision: bool = Query(
        False,
        description="Explicitly allow showcase slot auto-provisioning if no slots exist for the date."
    ),
    db: Session = Depends(get_db)
) -> List[SlotAvailabilityResponse]:
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    target_date = scheduled_date or date.today()
    slots = db.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == mandi_id,
        ProcurementSlot.scheduled_date == target_date
    ).order_by(ProcurementSlot.start_time.asc()).all()

    # Isolate showcase slot auto-provisioning:
    # Ordinary read requests (auto_provision=False) do NOT mutate the database.
    # Auto-provisioning only occurs if explicitly requested (e.g. showcase demo).
    if not slots and auto_provision:
        slots = provision_standard_slots(db=db, mandi_id=mandi_id, target_date=target_date)

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
    current_user: Optional[User] = Depends(require_roles(["FARMER", "OPERATOR", "ADMIN", "SUPERVISOR"])),
    db: Session = Depends(get_db)
) -> SlotReservationResponse:
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == payload.mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {payload.mandi_id} not found."
        )
    if current_user and current_user.role == "FARMER":
        auth_farmer_id = get_authenticated_farmer_id(current_user, db)
        if auth_farmer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authenticated user has no linked farmer profile."
            )
        if auth_farmer_id != payload.farmer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Authenticated farmer ID ({auth_farmer_id}) does not match reservation payload farmer ID ({payload.farmer_id})."
            )

    return reserve_slot_atomic(
        db=db,
        mandi_id=payload.mandi_id,
        slot_id=payload.slot_id,
        farmer_id=payload.farmer_id,
        requested_qty_qt=payload.requested_qty_qt,
        crop_type=payload.crop_type,
        demo_run_id=payload.demo_run_id,
    )


@router.post(
    "/cancel",
    summary="Cancel Slot Reservation",
    description="Cancels an unverified procurement slot appointment, restoring hourly capacity and farmer ceiling."
)
def cancel_reservation(
    payload: dict,
    current_user: Optional[User] = Depends(require_roles(["FARMER", "OPERATOR", "ADMIN", "SUPERVISOR"])),
    db: Session = Depends(get_db)
) -> dict:
    txn_id = payload.get("transaction_id")
    if not txn_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="transaction_id is required"
        )

    log = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{txn_id}' not found."
        )

    # Enforce mandi-scoped authorization (AUD-001)
    assert_transaction_scope(log, current_user, action_desc="cancel slot reservation")

    return cancel_slot_reservation(db=db, transaction_id=txn_id)
