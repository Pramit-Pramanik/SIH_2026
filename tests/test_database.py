from datetime import date, time, datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect

from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog, VALID_PROCUREMENT_STATES

def test_mandi_crud_and_constraints(db_session):
    """Verify Mandi model persistence and capacity constraints."""
    # 1. Valid mandi
    mandi = Mandi(
        name="Khanna Grain Market",
        district="Ludhiana",
        state="Punjab",
        daily_capacity_qt=5000.00,
        active_weighbridges=3,
        is_operational=True
    )
    db_session.add(mandi)
    db_session.commit()
    db_session.refresh(mandi)

    assert mandi.mandi_id is not None
    assert mandi.name == "Khanna Grain Market"
    assert mandi.active_weighbridges == 3

    # 2. Check constraint: daily_capacity_qt > 0
    invalid_mandi = Mandi(
        name="Invalid Capacity Mandi",
        district="Ambala",
        state="Haryana",
        daily_capacity_qt=-10.00,
        active_weighbridges=2
    )
    db_session.add(invalid_mandi)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_farmer_crud_and_uniqueness(db_session):
    """Verify Farmer model persistence, aadhaar uniqueness, and yield ceiling constraints."""
    farmer1 = Farmer(
        aadhaar_hash="hash_farmer_101_unique",
        name="Gurpreet Singh",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_101",
        ifsc_code="SBIN0001234",
        land_area_hectares=4.50,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=112.50
    )
    db_session.add(farmer1)
    db_session.commit()
    db_session.refresh(farmer1)

    assert farmer1.farmer_id is not None
    assert farmer1.production_ceiling_qt == 112.50

    # Unique Aadhaar constraint violation
    duplicate_farmer = Farmer(
        aadhaar_hash="hash_farmer_101_unique",  # duplicate
        name="Another Name",
        mobile_number="9876543211",
        bank_account_hash="bank_hash_102",
        ifsc_code="SBIN0001234",
        land_area_hectares=2.00,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=50.00
    )
    db_session.add(duplicate_farmer)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Negative land area check constraint
    invalid_farmer = Farmer(
        aadhaar_hash="hash_farmer_negative_land",
        name="Invalid Land",
        mobile_number="9876543212",
        bank_account_hash="bank_hash_103",
        ifsc_code="SBIN0001234",
        land_area_hectares=-1.00,
        registered_crop_type="Wheat",
        production_ceiling_qt=50.00
    )
    db_session.add(invalid_farmer)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_procurement_slot_capacity_constraint(db_session):
    """Verify slot capacity checks: booked_capacity_qt <= allocated_capacity_qt."""
    mandi = Mandi(
        name="Sirsa Mandi",
        district="Sirsa",
        state="Haryana",
        daily_capacity_qt=2000.00,
        active_weighbridges=2
    )
    db_session.add(mandi)
    db_session.commit()

    # Valid slot
    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 15),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=100.00,
        booked_capacity_qt=40.00,
        version=1
    )
    db_session.add(slot)
    db_session.commit()
    assert slot.slot_id is not None

    # Overbooked slot: booked > allocated
    overbooked_slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 15),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=50.00,
        booked_capacity_qt=50.01,  # Exceeds allocated
        version=1
    )
    db_session.add(overbooked_slot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_procurement_log_states_and_constraints(db_session):
    """Verify procurement log state machine strings, moisture checks, and foreign keys."""
    # Setup mandi and farmer
    mandi = Mandi(
        name="Karnal Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=3000.00,
        active_weighbridges=2
    )
    farmer = Farmer(
        aadhaar_hash="hash_farmer_karnal_001",
        name="Balwinder Singh",
        mobile_number="9876543220",
        bank_account_hash="bank_hash_karnal",
        ifsc_code="PUNB0001234",
        land_area_hectares=3.00,
        registered_crop_type="Paddy (Basmati)",
        production_ceiling_qt=75.00
    )
    db_session.add_all([mandi, farmer])
    db_session.commit()
    f_id = farmer.farmer_id
    m_id = mandi.mandi_id

    # Verify all 12 valid states can be assigned
    for valid_state in VALID_PROCUREMENT_STATES:
        log = ProcurementLog(
            transaction_id=f"TXN-STATE-{valid_state}",
            farmer_id=f_id,
            mandi_id=m_id,
            scheduled_date=date(2026, 10, 16),
            crop_moisture_pct=14.20,
            gross_weight_qt=120.00,
            tare_weight_qt=40.00,
            net_weight_qt=80.00,
            total_payout_inr=176000.00,
            current_state=valid_state,
            token_signature="a" * 64,
            payout_block_hash="b" * 64,
            client_mutation_id="mutation-uuid-001",
            server_receive_sequence=1
        )
        db_session.add(log)
        db_session.commit()
        assert log.current_state == valid_state

    # Invalid state rejection
    invalid_log = ProcurementLog(
        transaction_id="TXN-INVALID-STATE",
        farmer_id=f_id,
        mandi_id=m_id,
        scheduled_date=date(2026, 10, 16),
        current_state="UNKNOWN_STATE_HERE",
        token_signature="a" * 64
    )
    db_session.add(invalid_log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Moisture constraint: > 100%
    invalid_moisture_log = ProcurementLog(
        transaction_id="TXN-INVALID-MOISTURE",
        farmer_id=f_id,
        mandi_id=m_id,
        scheduled_date=date(2026, 10, 16),
        crop_moisture_pct=105.00,  # Invalid
        current_state="IN_QA_QUEUE",
        token_signature="a" * 64
    )
    db_session.add(invalid_moisture_log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_database_indexes_exist(db_session):
    """Verify required indexes are present on the database tables."""
    bind = db_session.get_bind()
    inspector = inspect(bind)

    # 1. farmers indexes
    farmer_indexes = [idx["name"] for idx in inspector.get_indexes("farmers")]
    assert "idx_farmers_aadhaar" in farmer_indexes

    # 2. procurement_slots indexes
    slot_indexes = [idx["name"] for idx in inspector.get_indexes("procurement_slots")]
    assert "idx_slots_date_mandi" in slot_indexes

    # 3. procurement_logs indexes
    log_indexes = [idx["name"] for idx in inspector.get_indexes("procurement_logs")]
    assert "idx_procurement_mandi_state" in log_indexes
    assert "idx_procurement_farmer" in log_indexes
