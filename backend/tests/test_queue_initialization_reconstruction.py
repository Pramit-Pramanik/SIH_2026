"""
Tests for AUD-005 / AUD-006: Queue Initialization and Authoritative Reconstruction.

Verifies:
1. Bootstrap queue populated with TXN-DEMO-1002 with authoritative score.
2. Bootstrap failure propagation when queue priming fails (never swallowed).
3. Redis unavailable (in-memory fallback guarantees exact IDs, scores, and states).
4. Backend restart and queue reconstruction from persistent database state.
5. Determinism: Same DB data produces identical ordering across multiple reconstructions.
6. Deterministic tie-breaking (earlier arrival first, then alphabetical transaction ID).
7. Dispatch pop consumes top vehicle and transitions state to ROUTED_TO_WEIGHBRIDGE.
8. Quality rejection removes vehicle from the active priority queue.
9. Quality approval (and supervisor override) re-adds vehicle to the active priority queue.
10. Data integrity enforcement: Controlled QueueDataIntegrityError is raised when
    moisture, weight, or timestamps are missing, rather than fabricating fallback values (14.0%, 50.0 qt, 15 min).
"""

from datetime import date, datetime, time as dt_time, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.user import User
from backend.app.core.security import generate_booking_signature
from backend.app.services.queue_manager import (
    QueueManager,
    InMemoryQueueRegistry,
    QueueDataIntegrityError,
    queue_manager
)
from backend.app.services.quality_service import (
    reconstruct_mandi_queue,
    get_mandi_queue_list,
    dispatch_top_vehicle_from_queue,
    get_vehicle_queue_status,
    rerank_mandi_queue,
    assess_quality_and_enqueue,
    override_quality_and_admit
)
from backend.app.services.seed_service import (
    bootstrap_database,
    ensure_showcase_queue_state
)
from backend.app.schemas.quality import (
    QualityAssessmentRequest,
    QualityOverrideRequest
)


@pytest.fixture
def queue_env(db_session: Session):
    """Sets up a clean test mandi, crop, slot, and farmer environment."""
    mandi = Mandi(
        mandi_id=101,
        name="Test Mandi Ludhiana",
        state="Punjab",
        district="Ludhiana",
        daily_capacity_qt=5000.0,
        active_weighbridges=2,
        is_operational=True
    )
    db_session.add(mandi)

    crop = Crop(
        crop_code="WHEAT_PB",
        crop_name="Wheat (PB-2026)",
        msp_price_inr=2275.0,
        optimal_moisture_pct=12.0,
        max_moisture_pct=14.0,
        is_active=True
    )
    db_session.add(crop)

    farmer = Farmer(
        farmer_id=201,
        aadhaar_hash="aadhaar_queue_test_hash_001",
        name="Harpreet Singh",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_harpreet",
        ifsc_code="SBIN0001042",
        land_area_hectares=5.0,
        registered_crop_type="Wheat (PB-2026)",
        production_ceiling_qt=250.0
    )
    db_session.add(farmer)

    today = date.today()
    slot = ProcurementSlot(
        slot_id=301,
        mandi_id=101,
        scheduled_date=today,
        start_time=dt_time(9, 0),
        end_time=dt_time(10, 0),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=100.0
    )
    db_session.add(slot)
    db_session.commit()

    # Clear queue for test mandi
    queue_manager.clear(101)

    return mandi, crop, farmer, slot


def test_bootstrap_queue_populated(db_session: Session):
    """
    Test 1: Bootstrap populates the active priority queue with canonical TXN-DEMO-1002.
    """
    result = bootstrap_database(db_session, reset=True)
    assert result["status"] == "SUCCESS"

    queue = queue_manager.get_queue(1)
    txn_ids = [item[0] for item in queue]
    assert "TXN-DEMO-1002" in txn_ids

    # Verify score is authoritative and positive
    score = queue_manager.get_score(1, "TXN-DEMO-1002")
    assert score is not None
    assert score > 0.0


def test_bootstrap_queue_priming_failure_propagates(db_session: Session):
    """
    Test 2: If queue priming fails during bootstrap, the exception is NEVER swallowed,
    and bootstrap must report failure.
    """
    with patch.object(queue_manager, "enqueue", side_effect=RuntimeError("Redis connection failure")):
        with pytest.raises(RuntimeError) as exc_info:
            ensure_showcase_queue_state(db=db_session, mandi_id=1)
        assert "Redis connection failure" in str(exc_info.value)


def test_redis_unavailable_in_memory_fallback():
    """
    Test 3: When Redis is unavailable, in-memory fallback guarantees exact transaction IDs,
    deterministic scores, and exact arrival timestamps.
    """
    # Force Redis unavailable
    with patch.object(queue_manager, "_get_redis", return_value=None):
        mandi_id = 102
        queue_manager.clear(mandi_id)

        queue_manager.enqueue(mandi_id, "TXN-REAL-001", 72.50, arrival_ts=1000.0)
        queue_manager.enqueue(mandi_id, "TXN-REAL-002", 85.00, arrival_ts=1050.0)

        # Confirm exact IDs and descending order by score
        queue = queue_manager.get_queue(mandi_id)
        assert len(queue) == 2
        assert queue[0] == ("TXN-REAL-002", 85.00)
        assert queue[1] == ("TXN-REAL-001", 72.50)

        # Confirm exact arrival timestamp preservation
        assert queue_manager.get_arrival_timestamp(mandi_id, "TXN-REAL-001") == 1000.0
        assert queue_manager.get_arrival_timestamp(mandi_id, "TXN-REAL-002") == 1050.0

        # Confirm push alias works identically
        queue_manager.push(mandi_id, "TXN-REAL-003", 95.00, arrival_ts=1100.0)
        assert queue_manager.get_rank(mandi_id, "TXN-REAL-003") == 1

        queue_manager.clear(mandi_id)


def test_backend_restart_queue_reconstruction(db_session: Session, queue_env):
    """
    Test 4: Simulates a backend restart (clearing active memory queue).
    Calling get_mandi_queue_list authoritatively reconstructs the queue from database state.
    """
    mandi, crop, farmer, slot = queue_env
    today = date.today()

    txn = ProcurementLog(
        transaction_id="TXN-PERSIST-101",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_type=crop.crop_name,
        crop_moisture_pct=13.50,
        net_weight_qt=65.00,
        current_state="QUALITY_APPROVED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 65.0),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=20)
    )
    db_session.add(txn)
    db_session.commit()

    # Simulate backend restart: queue is wiped
    queue_manager.clear(mandi.mandi_id)
    assert queue_manager.queue_length(mandi.mandi_id) == 0

    # Inspection reconstructs queue authoritatively
    response = get_mandi_queue_list(db=db_session, mandi_id=mandi.mandi_id)
    assert response.total_vehicles == 1
    assert response.items[0].transaction_id == "TXN-PERSIST-101"
    assert response.items[0].quantity_qt == 65.00
    assert response.items[0].priority_score > 0.0
    assert response.items[0].arrival_timestamp is not None


def test_same_db_data_produces_same_ordering(db_session: Session, queue_env):
    """
    Test 5: Determinism — Reconstructing queue multiple times from the same DB state
    at a fixed timestamp produces the EXACT same ordering and identical scores.
    """
    mandi, crop, farmer, slot = queue_env
    today = date.today()
    fixed_eval_time = 1750000000.0

    # Create 3 transactions with varied attributes
    txns = [
        ProcurementLog(
            transaction_id="TXN-ORD-A",
            farmer_id=farmer.farmer_id,
            mandi_id=mandi.mandi_id,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_moisture_pct=15.50,  # higher moisture risk -> higher priority
            net_weight_qt=80.00,
            current_state="QUALITY_APPROVED",
            token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 80.0),
            created_at=datetime.fromtimestamp(fixed_eval_time - 1800, tz=timezone.utc)
        ),
        ProcurementLog(
            transaction_id="TXN-ORD-B",
            farmer_id=farmer.farmer_id,
            mandi_id=mandi.mandi_id,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_moisture_pct=13.00,  # dry crop
            net_weight_qt=40.00,
            current_state="QUALITY_APPROVED",
            token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 40.0),
            created_at=datetime.fromtimestamp(fixed_eval_time - 900, tz=timezone.utc)
        ),
        ProcurementLog(
            transaction_id="TXN-ORD-C",
            farmer_id=farmer.farmer_id,
            mandi_id=mandi.mandi_id,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_moisture_pct=16.80,  # near limit moisture -> very high priority
            net_weight_qt=90.00,
            current_state="QUALITY_APPROVED",
            token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 90.0),
            created_at=datetime.fromtimestamp(fixed_eval_time - 3600, tz=timezone.utc)
        ),
    ]
    for t in txns:
        db_session.add(t)
    db_session.commit()

    # Reconstruct 1st time
    q1 = reconstruct_mandi_queue(db_session, mandi.mandi_id, current_time=fixed_eval_time)
    order1 = [(txn_id, round(score, 4)) for txn_id, score in q1]

    # Wipe and reconstruct 2nd time
    queue_manager.clear(mandi.mandi_id)
    q2 = reconstruct_mandi_queue(db_session, mandi.mandi_id, current_time=fixed_eval_time)
    order2 = [(txn_id, round(score, 4)) for txn_id, score in q2]

    # Wipe and reconstruct 3rd time
    queue_manager.clear(mandi.mandi_id)
    q3 = reconstruct_mandi_queue(db_session, mandi.mandi_id, current_time=fixed_eval_time)
    order3 = [(txn_id, round(score, 4)) for txn_id, score in q3]

    assert order1 == order2 == order3
    # TXN-ORD-C (highest moisture + weight + longest wait) must be #1
    assert order1[0][0] == "TXN-ORD-C"


def test_deterministic_tie_breaking(db_session: Session, queue_env):
    """
    Test 6: Under equal DCDQ priority scores, ties are broken deterministically:
    1. Earlier arrival timestamp first (FIFO)
    2. Alphabetical transaction ID if arrival timestamps are also identical
    """
    mandi, _, _, _ = queue_env
    mandi_id = mandi.mandi_id
    queue_manager.clear(mandi_id)

    # Tie-breaking 1: Same score, different arrival times
    queue_manager.enqueue(mandi_id, "TXN-LATE-ARRIVAL", 50.00, arrival_ts=2000.0)
    queue_manager.enqueue(mandi_id, "TXN-EARLY-ARRIVAL", 50.00, arrival_ts=1000.0)

    q = queue_manager.get_queue(mandi_id)
    assert q[0][0] == "TXN-EARLY-ARRIVAL"
    assert q[1][0] == "TXN-LATE-ARRIVAL"

    # Tie-breaking 2: Same score AND same arrival time -> Alphabetical
    queue_manager.clear(mandi_id)
    queue_manager.enqueue(mandi_id, "TXN-ZETA", 50.00, arrival_ts=1000.0)
    queue_manager.enqueue(mandi_id, "TXN-ALPHA", 50.00, arrival_ts=1000.0)

    q_alpha = queue_manager.get_queue(mandi_id)
    assert q_alpha[0][0] == "TXN-ALPHA"
    assert q_alpha[1][0] == "TXN-ZETA"


def test_dispatch_pops_highest_priority(db_session: Session, queue_env):
    """
    Test 7: dispatch_top_vehicle_from_queue pops the winner from queue
    and transitions transaction state to ROUTED_TO_WEIGHBRIDGE.
    """
    mandi, crop, farmer, slot = queue_env
    today = date.today()

    txn_top = ProcurementLog(
        transaction_id="TXN-TOP-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_moisture_pct=16.50,
        net_weight_qt=80.00,
        current_state="QUALITY_APPROVED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 80.0),
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(txn_top)
    db_session.commit()

    # Seed queue
    reconstruct_mandi_queue(db_session, mandi.mandi_id)
    assert queue_manager.queue_length(mandi.mandi_id) == 1

    # Dispatch
    dispatch_res = dispatch_top_vehicle_from_queue(db=db_session, mandi_id=mandi.mandi_id)
    assert dispatch_res.transaction_id == "TXN-TOP-001"
    assert dispatch_res.new_state == "ROUTED_TO_WEIGHBRIDGE"

    # Verify popped from queue
    assert queue_manager.queue_length(mandi.mandi_id) == 0

    # Verify DB state updated
    db_session.refresh(txn_top)
    assert txn_top.current_state == "ROUTED_TO_WEIGHBRIDGE"


def test_quality_rejection_removes_queue_item(db_session: Session, queue_env):
    """
    Test 8: If a lot fails quality testing (moisture > 17.0%), it is excluded
    from the queue and removed if previously present.
    """
    mandi, crop, farmer, slot = queue_env
    today = date.today()

    txn = ProcurementLog(
        transaction_id="TXN-MOIST-HIGH",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_moisture_pct=None,
        net_weight_qt=50.00,
        current_state="GATE_ENTRY_VERIFIED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 50.0),
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(txn)
    db_session.commit()

    # Assess with excessive moisture (18.5% > 17.0%)
    req = QualityAssessmentRequest(
        transaction_id="TXN-MOIST-HIGH",
        crop_moisture_pct=18.50
    )
    resp = assess_quality_and_enqueue(db=db_session, request=req)

    assert resp.status == "QUALITY_REJECTED"
    assert resp.eligible_for_queue is False
    assert queue_manager.get_rank(mandi.mandi_id, "TXN-MOIST-HIGH") is None

    db_session.refresh(txn)
    assert txn.current_state == "QUALITY_REJECTED"


def test_quality_approval_and_override_re_adds_queue_item(db_session: Session, queue_env):
    """
    Test 9: Quality approval adds item to queue. Quality rejection followed by
    authorized supervisor override re-admits vehicle to active queue.
    """
    mandi, crop, farmer, slot = queue_env
    today = date.today()

    supervisor = User(
        username="sup_test_001",
        hashed_password="hash",
        full_name="Supervisor Test",
        role="SUPERVISOR",
        mandi_id=mandi.mandi_id
    )
    db_session.add(supervisor)

    txn = ProcurementLog(
        transaction_id="TXN-OVERRIDE-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_moisture_pct=18.20,
        net_weight_qt=60.00,
        current_state="QUALITY_REJECTED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 60.0),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=45)
    )
    db_session.add(txn)
    db_session.commit()

    # Lot is not in queue
    assert queue_manager.get_rank(mandi.mandi_id, "TXN-OVERRIDE-001") is None

    # Supervisor override
    override_req = QualityOverrideRequest(
        transaction_id="TXN-OVERRIDE-001",
        calibrated_moisture_pct=15.00,
        reason="Drying apron aeration cycle completed; verified 15.0% moisture."
    )
    override_res = override_quality_and_admit(db=db_session, request=override_req, current_user=supervisor)

    assert override_res.status == "QUALITY_APPROVED"
    assert override_res.queue_position == 1

    # Verify in active queue with authoritative score
    score = queue_manager.get_score(mandi.mandi_id, "TXN-OVERRIDE-001")
    assert score is not None
    assert score > 0.0


def test_missing_data_raises_queue_data_integrity_error(db_session: Session, queue_env):
    """
    Test 10: Authoritative Reconstruction — If required queue data (moisture or weight)
    is missing for a QUALITY_APPROVED vehicle, system NEVER fabricates values (14.0%, 50.0 qt, 15 min).
    Instead, it raises a controlled QueueDataIntegrityError.
    """
    mandi, crop, farmer, slot = queue_env
    today = date.today()

    # Case A: Missing moisture
    txn_no_moist = ProcurementLog(
        transaction_id="TXN-CORRUPT-NO-MOIST",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_moisture_pct=None,  # MISSING! Must not fabricate 14.0%
        net_weight_qt=70.00,
        current_state="QUALITY_APPROVED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 70.0),
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(txn_no_moist)
    db_session.commit()

    with pytest.raises(QueueDataIntegrityError) as exc_info:
        reconstruct_mandi_queue(db_session, mandi.mandi_id)
    assert "TXN-CORRUPT-NO-MOIST" in str(exc_info.value.detail)
    assert "moisture" in str(exc_info.value.detail).lower()

    # Case B: Missing net weight
    txn_no_moist.crop_moisture_pct = 14.00
    txn_no_moist.net_weight_qt = None  # MISSING! Must not fabricate 50.0 qt
    db_session.commit()

    with pytest.raises(QueueDataIntegrityError) as exc_info_w:
        reconstruct_mandi_queue(db_session, mandi.mandi_id)
    assert "TXN-CORRUPT-NO-MOIST" in str(exc_info_w.value.detail)
    assert "quantity" in str(exc_info_w.value.detail).lower() or "weight" in str(exc_info_w.value.detail).lower()
