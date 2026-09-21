"""
Test Suite for Database State Consistency: CANCELLED state.
Verifies:
1. Migration 0005 CHECK constraint chk_procurement_state_valid allows 'CANCELLED'.
2. Direct SQL update to 'CANCELLED' succeeds without IntegrityError.
3. cancel_slot_reservation restores slot capacity.
4. Cancelled quantity is excluded from farmer's active production calculation.
5. Repeated cancellation of the same transaction is rejected.
"""
from datetime import date, time
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.services.reservation_service import (
    reserve_slot_atomic,
    cancel_slot_reservation,
    ACTIVE_PROCUREMENT_STATES
)


def _ensure_baseline_entities(db: Session):
    mandi = db.query(Mandi).filter(Mandi.mandi_id == 1).first()
    if not mandi:
        mandi = Mandi(
            mandi_id=1,
            name="Test APMC Mandi",
            district="Ludhiana",
            state="Punjab",
            daily_capacity_qt=1000.0,
            is_operational=True
        )
        db.add(mandi)
        db.commit()

    farmer = db.query(Farmer).filter(Farmer.farmer_id == 1).first()
    if not farmer:
        farmer = Farmer(
            farmer_id=1,
            aadhaar_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            name="Harjit Singh",
            mobile_number="9876543210",
            bank_account_hash="1122334455667788990011223344556677889900112233445566778899001122",
            ifsc_code="SBIN0001234",
            land_area_hectares=2.5,
            production_ceiling_qt=150.0,
            registered_crop_type="Wheat (HD-2967)"
        )
        db.add(farmer)
        db.commit()


def test_direct_sql_cancelled_state_allowed(db_session: Session):
    """
    Directly tests that 'CANCELLED' satisfies the database check constraint
    chk_procurement_state_valid in SQLite/PostgreSQL.
    """
    _ensure_baseline_entities(db_session)

    txn_id = "TXN-TEST-CANCEL-DIRECT-01"
    # Clean up if existing
    db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).delete()
    db_session.commit()

    # Insert initial log in SLOT_BOOKED
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=1,
        mandi_id=1,
        scheduled_date=date.today(),
        net_weight_qt=50.0,
        current_state="SLOT_BOOKED",
        token_signature="test_sig_hash_01"
    )
    db_session.add(log)
    db_session.commit()

    # Perform direct UPDATE to CANCELLED - must not fail CHECK constraint
    db_session.execute(
        text("UPDATE procurement_logs SET current_state = 'CANCELLED' WHERE transaction_id = :txn"),
        {"txn": txn_id}
    )
    db_session.commit()

    updated = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert updated is not None
    assert updated.current_state == "CANCELLED"

    # Cleanup
    db_session.delete(updated)
    db_session.commit()


def test_slot_booking_cancellation_flow(db_session: Session):
    """
    Verifies the full lifecycle:
    1. Reserve slot capacity (SLOT_BOOKED).
    2. Cancel slot reservation -> current_state becomes CANCELLED.
    3. Slot booked capacity is decremented/restored.
    4. Cancelled transaction is excluded from ACTIVE_PROCUREMENT_STATES.
    5. Re-cancelling raises 409 Conflict.
    """
    _ensure_baseline_entities(db_session)

    today = date.today()
    # Ensure slot exists
    slot = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today
    ).first()

    if not slot:
        slot = ProcurementSlot(
            mandi_id=1,
            scheduled_date=today,
            start_time=time(10, 0, 0),
            end_time=time(11, 0, 0),
            allocated_capacity_qt=500.0,
            booked_capacity_qt=0.0
        )
        db_session.add(slot)
        db_session.commit()

    initial_booked = float(slot.booked_capacity_qt)
    book_qty = 25.0

    # 1. Book slot
    res = reserve_slot_atomic(
        db=db_session,
        mandi_id=1,
        slot_id=slot.slot_id,
        farmer_id=1,
        requested_qty_qt=book_qty
    )
    txn_id = res.transaction_id

    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == pytest.approx(initial_booked + book_qty, 0.01)

    # 2. Cancel slot
    cancel_res = cancel_slot_reservation(db_session, txn_id)
    assert cancel_res["status"] == "SUCCESS"
    assert cancel_res["current_state"] == "CANCELLED"

    # 3. Capacity restored
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == pytest.approx(initial_booked, 0.01)

    # 4. Verified state in DB
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log is not None
    assert log.current_state == "CANCELLED"
    assert "CANCELLED" not in ACTIVE_PROCUREMENT_STATES

    # 5. Repeated cancellation rejected
    with pytest.raises(HTTPException) as exc_info:
        cancel_slot_reservation(db_session, txn_id)
    assert exc_info.value.status_code == 409
    assert "already in state 'CANCELLED'" in exc_info.value.detail

    # Cleanup
    db_session.delete(log)
    db_session.commit()
