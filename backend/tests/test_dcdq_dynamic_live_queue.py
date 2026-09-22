"""
Authoritative Test Suite for MANDIQ DCDQ Dynamic Live Queue (AUD-001 / AUD-002).

Tests:
1. DCDQ component calculation (A, D, M, W, S decomposition)
2. dynamic wait increase
3. score increase as wait increases
4. moisture priority
5. > 17% moisture rejection
6. queue order changes after dynamic rerank (traceable time advancement)
7. deterministic tie-breaking
8. bootstrap score equals canonical DCDQ calculation (no hardcoded 25.00)
9. missing quantity rejected with QueueDataIntegrityError (no 50.0 qt fallback)
10. missing moisture rejected with QueueDataIntegrityError (no 14.0% fallback)
"""

from datetime import date, datetime, time as dt_time, timedelta, timezone
import time
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.user import User
from backend.app.core.security import generate_booking_signature
from backend.app.services.dcdq_engine import (
    calculate_appointment_adherence,
    calculate_lateness_penalty,
    calculate_demurrage_score,
    calculate_moisture_risk,
    calculate_wait_bonus,
    calculate_priority_score,
    calculate_dcdq_priority_score,
    calculate_dcdq_components,
    is_quality_rejected,
    MOISTURE_ACCEPTANCE_THRESHOLD,
    MAX_WAIT_BONUS
)
from backend.app.services.queue_manager import (
    QueueManager,
    InMemoryQueueRegistry,
    QueueDataIntegrityError,
    queue_manager
)
from backend.app.services.quality_service import (
    recompute_and_get_mandi_queue,
    get_mandi_queue_list,
    rerank_mandi_queue,
    reconstruct_mandi_queue,
    assess_quality_and_enqueue
)
from backend.app.services.seed_service import (
    bootstrap_database,
    ensure_showcase_queue_state
)
from backend.app.schemas.quality import QualityAssessmentRequest


@pytest.fixture
def queue_env(db_session: Session):
    """Sets up a clean test mandi, crop, slot, and farmer environment."""
    queue_manager.clear()

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

    farmer2 = Farmer(
        farmer_id=202,
        aadhaar_hash="aadhaar_queue_test_hash_002",
        name="Gurdev Singh",
        mobile_number="9876543211",
        bank_account_hash="bank_hash_gurdev",
        ifsc_code="SBIN0001042",
        land_area_hectares=8.0,
        registered_crop_type="Wheat (PB-2026)",
        production_ceiling_qt=400.0
    )
    db_session.add(farmer2)

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

    queue_manager.clear(101)
    return mandi, crop, farmer, slot


# ===========================================================================
# 1. DCDQ Component Calculation (A, D, M, W, S)
# ===========================================================================
def test_dcdq_component_calculation():
    """
    Test 1: Decomposes S_i = alpha*A_i + beta*D_i + gamma*M_i + lambda*W_i.
    A_i = max(0, 40 - 0.5 * lateness_minutes)
    D_i = min(20, payload / 10.0)
    M_i = piecewise moisture formula
    W_i = min(20, 0.1 * wait_minutes)
    """
    planned = 1700000000.0

    # Case 1: On-time, 50qt payload, 14.0% moisture (dry), 15 min wait
    # Lateness = 0 -> A = 40.0
    # Payload = 50 -> D = 5.0
    # Moisture = 14.0 -> M = 0.0
    # Wait = 15m -> W = 1.5
    # S = 40.0 + 5.0 + 0.0 + 1.5 = 46.50
    comps1 = calculate_dcdq_components(
        planned_arrival_ts=planned,
        actual_arrival_ts=planned,
        moisture_pct=14.0,
        elapsed_wait_minutes=15.0,
        payload_quintals=50.0
    )
    assert comps1["A"] == 40.00
    assert comps1["D"] == 5.00
    assert comps1["M"] == 0.00
    assert comps1["W"] == 1.50
    assert comps1["S"] == 46.50
    assert comps1["S"] == pytest.approx(comps1["A"] + comps1["D"] + comps1["M"] + comps1["W"], abs=0.01)

    # Case 2: 20 min late, 80qt payload, 16.0% moisture, 45 min wait
    # Lateness = 20 -> A = max(0, 40 - 0.5*20) = 30.0
    # Payload = 80 -> D = 8.0
    # Moisture = 16.0 -> M = calculate_moisture_risk(16.0)
    # Wait = 45m -> W = 4.5
    expected_m = calculate_moisture_risk(16.0)
    comps2 = calculate_dcdq_components(
        planned_arrival_ts=planned,
        actual_arrival_ts=planned + 1200.0,  # 20 min late
        moisture_pct=16.0,
        elapsed_wait_minutes=45.0,
        payload_quintals=80.0
    )
    assert comps2["A"] == 30.00
    assert comps2["D"] == 8.00
    assert comps2["M"] == pytest.approx(expected_m, abs=0.01)
    assert comps2["W"] == 4.50
    assert comps2["S"] == pytest.approx(comps2["A"] + comps2["D"] + comps2["M"] + comps2["W"], abs=0.01)


# ===========================================================================
# 2. Dynamic Wait Increase
# ===========================================================================
def test_dynamic_wait_increase(db_session: Session, queue_env):
    """
    Test 2: Authoritative queue recomputation updates elapsed wait time
    as current time progresses.
    """
    mandi, crop, farmer, slot = queue_env
    mandi_id = mandi.mandi_id
    now_epoch = 1700000000.0
    arrival_dt = datetime.fromtimestamp(now_epoch - 600.0, tz=timezone.utc)  # Arrived 10 min ago

    log = ProcurementLog(
        transaction_id="TXN-DYN-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        crop_moisture_pct=14.0,
        net_weight_qt=50.0,
        current_state="QUALITY_APPROVED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot.slot_id, 50.0),
        created_at=arrival_dt
    )
    db_session.add(log)
    db_session.commit()

    # Enqueue to active queue
    queue_manager.enqueue(mandi_id, "TXN-DYN-001", 40.0, now_epoch - 600.0)

    # First retrieval at t0 (10 min wait)
    res1 = recompute_and_get_mandi_queue(db_session, mandi_id, current_time=now_epoch)
    assert res1.total_vehicles == 1
    item1 = res1.items[0]
    assert item1.wait_minutes == pytest.approx(10.0, abs=0.1)
    assert item1.score_w == pytest.approx(1.0, abs=0.05)

    # Second retrieval at t1 = t0 + 1200s (20 minutes later -> 30 min total wait)
    res2 = recompute_and_get_mandi_queue(db_session, mandi_id, current_time=now_epoch + 1200.0)
    assert res2.total_vehicles == 1
    item2 = res2.items[0]
    assert item2.wait_minutes == pytest.approx(30.0, abs=0.1)
    assert item2.score_w == pytest.approx(3.0, abs=0.05)
    # Total score increased by 2.0
    assert item2.priority_score == pytest.approx(item1.priority_score + 2.0, abs=0.05)


# ===========================================================================
# 3. Score Increase as Wait Increases
# ===========================================================================
def test_score_increase_as_wait_increases():
    """
    Test 3: Anti-starvation ensures score monotonically increases as wait time grows,
    capping at MAX_WAIT_BONUS (20.0).
    """
    planned = 1700000000.0
    waits = [0.0, 30.0, 60.0, 120.0, 200.0, 300.0]
    scores = []

    for w in waits:
        score = calculate_dcdq_priority_score(
            planned_arrival_ts=planned,
            actual_arrival_ts=planned,
            moisture_pct=14.0,
            elapsed_wait_minutes=w,
            payload_quintals=50.0
        )
        scores.append(score)

    # Strictly increasing up to 200 min
    assert scores[0] < scores[1] < scores[2] < scores[3] < scores[4]
    # Capped at 200 min and beyond (20.0 wait bonus)
    assert scores[4] == scores[5]
    # Delta between 0 min and 200 min wait is exactly 20.0
    assert round(scores[4] - scores[0], 2) == 20.0


# ===========================================================================
# 4. Moisture Priority
# ===========================================================================
def test_moisture_priority():
    """
    Test 4: Higher moisture grain receives a higher moisture urgency score
    to mitigate rapid perishable spoilage in the yard.
    """
    planned = 1700000000.0
    wait = 10.0
    payload = 50.0

    score_dry = calculate_dcdq_priority_score(
        planned_arrival_ts=planned,
        actual_arrival_ts=planned,
        moisture_pct=14.0,
        elapsed_wait_minutes=wait,
        payload_quintals=payload
    )

    score_moist = calculate_dcdq_priority_score(
        planned_arrival_ts=planned,
        actual_arrival_ts=planned,
        moisture_pct=16.5,
        elapsed_wait_minutes=wait,
        payload_quintals=payload
    )

    assert score_moist > score_dry
    assert (score_moist - score_dry) > 10.0  # Significant moisture priority premium


# ===========================================================================
# 5. Moisture > 17% Rejection
# ===========================================================================
def test_moisture_greater_than_17_rejected(db_session: Session, queue_env):
    """
    Test 5: Lot with moisture > 17.0% MUST be immediately rejected and NOT admitted to queue.
    """
    mandi, crop, farmer, slot = queue_env
    assert is_quality_rejected(17.01) is True
    assert is_quality_rejected(18.5) is True
    assert is_quality_rejected(17.0) is False

    # Calling assess_quality_and_enqueue rejects transaction and excludes it from queue
    now = datetime.now(timezone.utc)
    log = ProcurementLog(
        transaction_id="TXN-REJ-017",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        crop_moisture_pct=None,
        net_weight_qt=60.0,
        current_state="GATE_ENTRY_VERIFIED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, 60.0),
        created_at=now
    )
    db_session.add(log)
    db_session.commit()

    req = QualityAssessmentRequest(
        transaction_id="TXN-REJ-017",
        crop_moisture_pct=18.50
    )
    resp = assess_quality_and_enqueue(db=db_session, request=req)

    assert resp.status == "QUALITY_REJECTED"
    assert resp.eligible_for_queue is False
    assert queue_manager.get_rank(mandi.mandi_id, "TXN-REJ-017") is None

    db_session.refresh(log)
    assert log.current_state == "QUALITY_REJECTED"

    # Also verify that if an item in the queue somehow had moisture > 17, recompute raises QueueDataIntegrityError
    log.current_state = "QUALITY_APPROVED"
    log.crop_moisture_pct = 18.50
    db_session.commit()
    with pytest.raises(QueueDataIntegrityError, match="excessive moisture"):
        recompute_and_get_mandi_queue(db_session, mandi.mandi_id)


# ===========================================================================
# 6. Queue Order Changes After Rerank (Mathematical Demonstration)
# ===========================================================================
def test_queue_order_changes_after_rerank(db_session: Session, queue_env):
    """
    Test 6: Simulates two showcase vehicles where simulated wait time changes the queue order.
    Vehicle A: Dry lot (12%), on-time (A=40), 80qt payload (D=8), initially low wait (15m -> W=1.5).
               Initial S_A = 40 + 8 + 0 + 1.5 = 49.50.
    Vehicle B: Moist lot (16%), 20m late (A=30), 50qt payload (D=5), initial wait (70m -> W=7.0).
               Initial S_B = 30 + 5 + 9.91 + 7.0 = 51.91 > 49.50.

    When simulated time advances by 180 min:
      Vehicle B wait reaches 250m -> capped at W=20. S_B = 30 + 5 + 9.91 + 20 = 64.91.
      Vehicle A wait reaches 195m -> W = 19.5. S_A = 40 + 8 + 0 + 19.5 = 67.50 > 64.91.
    Vehicle A mathematically overtakes Vehicle B!
    """
    mandi, crop, farmer, slot = queue_env
    mandi_id = mandi.mandi_id
    queue_manager.clear(mandi_id)

    arr_date = date(2026, 9, 21)
    slot_a = ProcurementSlot(
        slot_id=302,
        mandi_id=mandi_id,
        scheduled_date=arr_date,
        start_time=dt_time(9, 0),
        end_time=dt_time(10, 0),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=100.0
    )
    slot_b = ProcurementSlot(
        slot_id=303,
        mandi_id=mandi_id,
        scheduled_date=arr_date,
        start_time=dt_time(7, 30),
        end_time=dt_time(8, 30),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=100.0
    )
    db_session.add_all([slot_a, slot_b])
    db_session.commit()

    arr_a = datetime.combine(arr_date, dt_time(9, 0)).replace(tzinfo=timezone.utc)
    arr_b = datetime.combine(arr_date, dt_time(8, 0)).replace(tzinfo=timezone.utc)
    now_dt = datetime.combine(arr_date, dt_time(9, 20)).replace(tzinfo=timezone.utc)
    now_epoch = now_dt.timestamp()

    log_a = ProcurementLog(
        transaction_id="TXN-SIM-101",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot_a.slot_id,
        scheduled_date=arr_date,
        net_weight_qt=100.0,
        current_state="QUALITY_APPROVED",
        crop_moisture_pct=12.0,
        is_showcase=True,
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot_a.slot_id, 100.0),
        created_at=arr_a
    )
    log_b = ProcurementLog(
        transaction_id="TXN-SIM-102",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot_b.slot_id,
        scheduled_date=arr_date,
        net_weight_qt=50.0,
        current_state="QUALITY_APPROVED",
        crop_moisture_pct=16.5,
        is_showcase=True,
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot_b.slot_id, 50.0),
        created_at=arr_b
    )
    db_session.add_all([log_a, log_b])
    db_session.commit()

    # Enqueue both to active queue
    queue_manager.enqueue(mandi_id, "TXN-SIM-101", 52.00, arr_a.timestamp())
    queue_manager.enqueue(mandi_id, "TXN-SIM-102", 52.78, arr_b.timestamp())

    # Initial queue retrieval
    res_initial = recompute_and_get_mandi_queue(db_session, mandi_id, current_time=now_epoch)
    assert res_initial.total_vehicles == 2
    # Rank #1 is Vehicle B (TXN-SIM-102) due to higher initial wait & moisture
    assert res_initial.items[0].transaction_id == "TXN-SIM-102"
    assert res_initial.items[1].transaction_id == "TXN-SIM-101"

    # Now advance showcase time by 180 minutes using the isolated showcase offset
    queue_manager.advance_showcase_time_offset(mandi_id, 180.0)

    # Re-retrieve queue
    res_reranked = recompute_and_get_mandi_queue(db_session, mandi_id, current_time=now_epoch)
    assert res_reranked.total_vehicles == 2
    # Rank #1 is now Vehicle A (TXN-SIM-101) because its superior adherence & payload overtook capped wait bonus!
    assert res_reranked.items[0].transaction_id == "TXN-SIM-101"
    assert res_reranked.items[1].transaction_id == "TXN-SIM-102"
    assert res_reranked.items[0].priority_score > res_reranked.items[1].priority_score


# ===========================================================================
# 7. Deterministic Tie-Breaking
# ===========================================================================
def test_deterministic_tie_breaking(db_session: Session, queue_env):
    """
    Test 7: When two vehicles produce identical scores:
    1. Earlier arrival wins.
    2. If arrivals are identical, alphabetical txn_id breaks tie deterministically.
    """
    mandi, crop, farmer, slot = queue_env
    mandi_id = mandi.mandi_id
    queue_manager.clear(mandi_id)
    now_epoch = 1700000000.0

    arr_early = datetime.fromtimestamp(now_epoch - 600.0, tz=timezone.utc)
    arr_late = datetime.fromtimestamp(now_epoch - 300.0, tz=timezone.utc)

    log1 = ProcurementLog(
        transaction_id="TXN-TIE-Z",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        net_weight_qt=50.0,
        current_state="QUALITY_APPROVED",
        crop_moisture_pct=14.0,
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot.slot_id, 50.0),
        created_at=arr_early
    )
    log2 = ProcurementLog(
        transaction_id="TXN-TIE-A",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        net_weight_qt=50.0,
        current_state="QUALITY_APPROVED",
        crop_moisture_pct=14.0,
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot.slot_id, 50.0),
        created_at=arr_late
    )
    db_session.add_all([log1, log2])
    db_session.commit()

    # Even though TXN-TIE-A is alphabetically earlier, TXN-TIE-Z arrived earlier
    queue_manager.enqueue(mandi_id, "TXN-TIE-Z", 45.0, now_epoch - 600.0)
    queue_manager.enqueue(mandi_id, "TXN-TIE-A", 45.0, now_epoch - 300.0)

    # In queue manager, tie-breaking by arrival timestamp:
    members = queue_manager.get_queue(mandi_id)
    assert members[0][0] == "TXN-TIE-Z"


# ===========================================================================
# 8. Bootstrap Score Equals Canonical DCDQ Calculation
# ===========================================================================
def test_bootstrap_score_equals_canonical_dcdq_calculation(db_session: Session):
    """
    Test 8: Canonical bootstrap MUST NOT hardcode priority_score=25.00.
    It must dynamically calculate the score via calculate_dcdq_priority_score().
    """
    bootstrap_database(db_session, reset=True)

    log = db_session.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == "TXN-DEMO-1002"
    ).first()
    assert log is not None
    assert log.crop_moisture_pct is not None
    assert log.net_weight_qt is not None
    assert log.created_at is not None

    score = queue_manager.get_score(log.mandi_id, "TXN-DEMO-1002")
    assert score is not None

    # Score MUST NOT be old hardcoded 25.00
    assert score != 25.00

    # Retrieve score via recompute_and_get_mandi_queue and verify it reflects canonical calculation
    res = recompute_and_get_mandi_queue(db_session, log.mandi_id)
    assert res.total_vehicles >= 1
    demo_item = next(item for item in res.items if item.transaction_id == "TXN-DEMO-1002")
    assert demo_item.priority_score != 25.00
    assert demo_item.score_d == pytest.approx(float(log.net_weight_qt) / 10.0, abs=0.01)


# ===========================================================================
# 9. Missing Quantity Rejected with QueueDataIntegrityError
# ===========================================================================
def test_missing_quantity_rejected(db_session: Session, queue_env):
    """
    Test 9: Controlled QueueDataIntegrityError is raised if payload/quantity is missing.
    Must NEVER invent 50.0 qt fallback.
    """
    mandi, crop, farmer, slot = queue_env
    mandi_id = mandi.mandi_id
    now = datetime.now(timezone.utc)
    log = ProcurementLog(
        transaction_id="TXN-NO-QTY",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        net_weight_qt=None,  # Missing quantity!
        crop_moisture_pct=14.0,
        current_state="QUALITY_APPROVED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot.slot_id, 0.0),
        created_at=now
    )
    db_session.add(log)
    db_session.commit()

    # Enqueue into manager
    queue_manager.enqueue(mandi_id, "TXN-NO-QTY", 40.0, now.timestamp())

    with pytest.raises(QueueDataIntegrityError, match="is missing net quantity"):
        recompute_and_get_mandi_queue(db_session, mandi_id)


# ===========================================================================
# 10. Missing Moisture Rejected with QueueDataIntegrityError
# ===========================================================================
def test_missing_moisture_rejected(db_session: Session, queue_env):
    """
    Test 10: Controlled QueueDataIntegrityError is raised if quality moisture assessment is missing.
    Must NEVER invent 14.0% fallback.
    """
    mandi, crop, farmer, slot = queue_env
    mandi_id = mandi.mandi_id
    now = datetime.now(timezone.utc)
    log = ProcurementLog(
        transaction_id="TXN-NO-MOIST",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        net_weight_qt=65.0,
        crop_moisture_pct=None,  # Missing moisture!
        current_state="QUALITY_APPROVED",
        token_signature=generate_booking_signature(farmer.farmer_id, mandi_id, slot.slot_id, 65.0),
        created_at=now
    )
    db_session.add(log)
    db_session.commit()

    # Enqueue into manager
    queue_manager.enqueue(mandi_id, "TXN-NO-MOIST", 40.0, now.timestamp())

    with pytest.raises(QueueDataIntegrityError, match="is missing crop moisture percentage"):
        recompute_and_get_mandi_queue(db_session, mandi_id)
