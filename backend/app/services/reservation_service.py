from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from backend.app.core.security import generate_booking_signature
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.schemas.slot import (
    BookingToken,
    SlotReservationResponse,
    SlotAvailabilityResponse
)
from backend.app.services.lock_manager import lock_manager, LockContentionError


ACTIVE_PROCUREMENT_STATES = (
    "SLOT_BOOKED",
    "GATE_ENTRY_VERIFIED",
    "IN_QA_QUEUE",
    "QUALITY_APPROVED",
    "ROUTED_TO_WEIGHBRIDGE",
    "WEIGHED_GROSS",
    "WEIGHED_TARE",
    "BILL_GENERATED",
    "DBT_PAYMENT_INITIATED",
    "PAYMENT_SETTLED"
)


def get_slot_availability(db: Session, slot_id: int) -> SlotAvailabilityResponse:
    """
    Retrieves slot details and available capacity.
    """
    slot = db.query(ProcurementSlot).filter(ProcurementSlot.slot_id == slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement slot with ID {slot_id} not found."
        )

    allocated = float(slot.allocated_capacity_qt)
    booked = float(slot.booked_capacity_qt)
    remaining = max(0.0, allocated - booked)

    return SlotAvailabilityResponse(
        slot_id=slot.slot_id,
        mandi_id=slot.mandi_id,
        scheduled_date=str(slot.scheduled_date),
        start_time=str(slot.start_time),
        end_time=str(slot.end_time),
        allocated_capacity_qt=allocated,
        booked_capacity_qt=booked,
        remaining_capacity_qt=remaining
    )


def reserve_slot_atomic(
    db: Session,
    mandi_id: int,
    slot_id: int,
    farmer_id: int,
    requested_qty_qt: float
) -> SlotReservationResponse:
    """
    Atomically validates farmer yield ceiling AND reserves hourly slot capacity
    under an atomic lock boundary. Fails closed if secrets are missing.
    Ensures that cumulative bookings never exceed the farmer's registered production ceiling,
    and slot bookings never exceed allocated capacity.
    """
    if requested_qty_qt <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Requested delivery quantity must be strictly greater than 0."
        )

    # 1. Validate farmer existence
    farmer = db.query(Farmer).filter(Farmer.farmer_id == farmer_id).first()
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer with ID {farmer_id} not found."
        )

    # 2. Validate mandi existence and operational status
    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not mandi or not mandi.is_operational:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found or is currently non-operational."
        )

    # 3. Validate slot existence and matching mandi
    slot = db.query(ProcurementSlot).filter(
        ProcurementSlot.slot_id == slot_id,
        ProcurementSlot.mandi_id == mandi_id
    ).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement slot {slot_id} not found for mandi {mandi_id}."
        )

    # 4. Acquire atomic reservation lock
    try:
        with lock_manager.acquire_reservation_lock(mandi_id, slot_id, farmer_id):
            # Refresh entities inside lock boundary
            db.refresh(slot)
            db.refresh(farmer)

            # Compute current cumulative quantity booked by this farmer across active states
            cumulative_res = db.query(
                func.coalesce(func.sum(ProcurementLog.net_weight_qt), 0.0)
            ).filter(
                ProcurementLog.farmer_id == farmer_id,
                ProcurementLog.current_state.in_(ACTIVE_PROCUREMENT_STATES)
            ).scalar()
            current_farmer_booked = float(cumulative_res or 0.0)
            farmer_ceiling = float(farmer.production_ceiling_qt)

            # Check Farmer Production Ceiling Invariant: Q_booked + Q_requested <= ceiling
            if (current_farmer_booked + requested_qty_qt) > farmer_ceiling:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Farmer production ceiling exceeded: requesting {requested_qty_qt:.2f} qt, "
                        f"already booked {current_farmer_booked:.2f} qt, "
                        f"production ceiling is {farmer_ceiling:.2f} qt."
                    )
                )

            # Check Slot Capacity Invariant: booked + requested <= allocated
            allocated = float(slot.allocated_capacity_qt)
            booked = float(slot.booked_capacity_qt)
            remaining = allocated - booked
            if remaining < requested_qty_qt:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Slot capacity exhausted: requesting {requested_qty_qt:.2f} qt, "
                        f"only {remaining:.2f} qt remaining."
                    )
                )

            # Generate HMAC token signature (fails closed if secret missing)
            signature = generate_booking_signature(
                farmer_id=farmer_id,
                mandi_id=mandi_id,
                slot_id=slot_id,
                quantity_qt=requested_qty_qt
            )

            # Mutate slot state
            slot.booked_capacity_qt = booked + requested_qty_qt
            slot.version += 1

            # Create canonical procurement log entry
            txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
            procurement_log = ProcurementLog(
                transaction_id=txn_id,
                farmer_id=farmer_id,
                mandi_id=mandi_id,
                slot_id=slot_id,
                scheduled_date=slot.scheduled_date,
                current_state="SLOT_BOOKED",
                net_weight_qt=requested_qty_qt,
                token_signature=signature,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(procurement_log)

            try:
                db.commit()
                db.refresh(slot)
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Database constraint violation occurred during slot reservation."
                )
            except Exception:
                db.rollback()
                raise

            # Sync Redis tracking keys if Redis is active
            r = lock_manager._get_redis()
            if r is not None:
                try:
                    r.incrbyfloat(f"capacity:booked:{mandi_id}:{slot_id}", requested_qty_qt)
                    r.incrbyfloat(f"farmer:cumulative_booked:{farmer_id}", requested_qty_qt)
                except Exception:
                    pass

            token_id = f"MANDIQ-{uuid.uuid4().hex[:8].upper()}"
            booking_token = BookingToken(
                token_id=token_id,
                farmer_id=farmer_id,
                mandi_id=mandi_id,
                slot_id=slot_id,
                quantity_qt=requested_qty_qt,
                signature=signature
            )

            updated_farmer_booked = current_farmer_booked + requested_qty_qt
            return SlotReservationResponse(
                status="SUCCESS",
                transaction_id=txn_id,
                token=booking_token,
                allocated_capacity_qt=float(slot.allocated_capacity_qt),
                booked_capacity_qt=float(slot.booked_capacity_qt),
                remaining_slot_capacity_qt=max(0.0, float(slot.allocated_capacity_qt - slot.booked_capacity_qt)),
                farmer_cumulative_booked_qt=updated_farmer_booked,
                farmer_remaining_ceiling_qt=max(0.0, farmer_ceiling - updated_farmer_booked)
            )

    except LockContentionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrent lock contention: slot is currently being updated. Please retry."
        )
