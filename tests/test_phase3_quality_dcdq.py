from datetime import date, time, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.gate_service import verify_and_check_in_gate
from backend.app.schemas.gate import GateCheckInRequest
from backend.app.services.dcdq_engine import (
    calculate_dcdq_priority_score,
    calculate_appointment_adherence,
    calculate_demurrage_score,
    calculate_moisture_risk,
    calculate_wait_bonus,
    is_quality_rejected
)
from backend.app.services.queue_manager import queue_manager, InMemoryQueueRegistry


def setup_phase3_environment(db: Session, farmer_ceiling: float = 100.0, slot_capacity: float = 100.0):
    """
    Sets up an operational mandi, farmer, slot, reservations, and performs gate check-in
    so the transaction is in GATE_ENTRY_VERIFIED state ready for quality assaying.
    """
    mandi = Mandi(
        name="Ujjain Krishi Upaj Mandi",
        district="Ujjain",
        state="Madhya Pradesh",
        daily_capacity_qt=5000.00,
        active_weighbridges=2,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="c7d8e9f0123456789abcd",
        name="Ramesh Patel",
        mobile_number="9876543212",
        bank_account_hash="bank_hash_ramesh_003",
        ifsc_code="SBIN0001040",
        land_area_hectares=4.00,
        registered_crop_type="Wheat (Sharbati)",
        production_ceiling_qt=farmer_ceiling
    )
    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 25),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=slot_capacity,
        booked_capacity_qt=0.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    # 1. Slot reservation (Phase 1)
    reservation = reserve_slot_atomic(
        db=db,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=30.0
    )

    # 2. Gate check-in (Phase 2)
    check_in_req = GateCheckInRequest(
        transaction_id=reservation.transaction_id,
        farmer_id=reservation.token.farmer_id,
        mandi_id=reservation.token.mandi_id,
        slot_id=reservation.token.slot_id,
        quantity_qt=reservation.token.quantity_qt,
        token_signature=reservation.token.signature
    )
    gate_res = verify_and_check_in_gate(db=db, request=check_in_req)
    assert gate_res.current_state == "GATE_ENTRY_VERIFIED"

    # Reset active queue for test isolation
    queue_manager.clear(mandi.mandi_id)

    return mandi, farmer, slot, reservation


def test_dcdq_formula_pure_math_ac006():
    """
    AC-006: Verifies exact multi-criteria DCDQ priority formulation.
    Vehicle A: Moisture 13.5% (M_A = 0.0), arrived 45 mins ago (W_A = 4.5), A_A = 35.0, D_A = 5.0 => S_A = 44.5.
    Vehicle B: Moisture 16.2% (M_B = 11.62), arrived 10 mins ago (W_B = 1.0), A_B = 35.0, D_B = 5.0 => S_B = 52.62.
    Asserts S_B > S_A.
    """
    now_ts = 10000.0

    # Vehicle A
    actual_a = now_ts - (45.0 * 60.0)
    planned_a = actual_a - (10.0 * 60.0)  # 10 mins lateness -> A_i = 40 - (10 * 0.5) = 35.0
    wait_a = 45.0
    score_a = calculate_dcdq_priority_score(
        planned_arrival_ts=planned_a,
        actual_arrival_ts=actual_a,
        moisture_pct=13.5,
        elapsed_wait_minutes=wait_a,
        demurrage_score=5.0
    )
    assert score_a == 44.5, f"Expected 44.5, got {score_a}"

    # Vehicle B
    actual_b = now_ts - (10.0 * 60.0)
    planned_b = actual_b - (10.0 * 60.0)  # 10 mins lateness -> A_i = 35.0
    wait_b = 10.0
    score_b = calculate_dcdq_priority_score(
        planned_arrival_ts=planned_b,
        actual_arrival_ts=actual_b,
        moisture_pct=16.2,
        elapsed_wait_minutes=wait_b,
        demurrage_score=5.0
    )
    # 35.0 + 5.0 + 1.0 + 2.0 * exp(0.8 * 2.2) = 41.0 + 11.6248 = 52.6248
    assert round(score_b, 2) == 52.62, f"Expected 52.62, got {score_b}"

    # Priority invariant: Higher score = Higher priority
    assert score_b > score_a


def test_quality_rejection_strictly_overrides_priority_ac007(client: TestClient, db_session: Session):
    """
    AC-007: Lot with moisture > 17.0% is disqualified from standard procurement.
    Transitions state immediately to QUALITY_REJECTED, routes to drying apron,
    and cannot enter active weighbridge dispatch queue regardless of priority score.
    """
    mandi, farmer, slot, reservation = setup_phase3_environment(db_session)
    txn_id = reservation.transaction_id

    # Submit moisture assay reading of 18.5% (> 17.0% limit)
    response = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 18.5
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUALITY_REJECTED"
    assert data["eligible_for_queue"] is False
    assert data["priority_score"] is None
    assert data["queue_position"] is None
    assert "drying apron" in data["advisory_notice"]

    # Verify DB transaction state
    db_session.expire_all()
    db_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert db_log.current_state == "QUALITY_REJECTED"
    assert float(db_log.crop_moisture_pct) == 18.5

    # Verify exclusion from active Redis queue
    assert queue_manager.get_score(mandi.mandi_id, txn_id) is None
    assert queue_manager.get_rank(mandi.mandi_id, txn_id) is None
    assert queue_manager.queue_length(mandi.mandi_id) == 0


def test_quality_approval_and_redis_queue_ranking_ac006(client: TestClient, db_session: Session):
    """
    AC-006: Vehicle B (higher perishable moisture) gets a higher priority score than
    Vehicle A (dry load) and is placed ahead of Vehicle A in the active Redis ZSET queue.
    """
    mandi, farmer, slot, res_a = setup_phase3_environment(db_session)
    txn_a = res_a.transaction_id

    # Reserve second slot for Vehicle B
    res_b = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=20.0
    )
    txn_b = res_b.transaction_id

    # Gate check-in for Vehicle B
    gate_res_b = verify_and_check_in_gate(
        db=db_session,
        request=GateCheckInRequest(
            transaction_id=res_b.transaction_id,
            farmer_id=res_b.token.farmer_id,
            mandi_id=res_b.token.mandi_id,
            slot_id=res_b.token.slot_id,
            quantity_qt=res_b.token.quantity_qt,
            token_signature=res_b.token.signature
        )
    )
    assert gate_res_b.current_state == "GATE_ENTRY_VERIFIED"

    now_ts = 20000.0

    # Assess Vehicle A: Moisture 13.5%, arrived 45 mins ago
    resp_a = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_a,
            "crop_moisture_pct": 13.5,
            "demurrage_score": 5.0,
            "elapsed_wait_minutes": 45.0,
            "actual_arrival_ts": now_ts - (45.0 * 60.0),
            "planned_arrival_ts": now_ts - (55.0 * 60.0)  # 10 min lateness
        }
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["status"] == "QUALITY_APPROVED"
    assert resp_a.json()["priority_score"] == 44.5

    # Assess Vehicle B: Moisture 16.2%, arrived 10 mins ago
    resp_b = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_b,
            "crop_moisture_pct": 16.2,
            "demurrage_score": 5.0,
            "elapsed_wait_minutes": 10.0,
            "actual_arrival_ts": now_ts - (10.0 * 60.0),
            "planned_arrival_ts": now_ts - (20.0 * 60.0)  # 10 min lateness
        }
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["status"] == "QUALITY_APPROVED"
    assert round(resp_b.json()["priority_score"], 2) == 52.62

    # Query full active queue via API
    queue_resp = client.get(f"/api/v1/queue/{mandi.mandi_id}")
    assert queue_resp.status_code == 200
    q_data = queue_resp.json()
    assert q_data["total_vehicles"] == 2

    # Vehicle B must be Rank 1, Vehicle A must be Rank 2
    assert q_data["items"][0]["transaction_id"] == txn_b
    assert q_data["items"][0]["rank"] == 1
    assert round(q_data["items"][0]["priority_score"], 2) == 52.62

    assert q_data["items"][1]["transaction_id"] == txn_a
    assert q_data["items"][1]["rank"] == 2
    assert q_data["items"][1]["priority_score"] == 44.5


def test_deterministic_tie_breaking_equal_scores():
    """
    Verifies that when two vehicles achieve the exact same DCDQ score,
    the queue deterministically orders the vehicle that arrived earlier first.
    If arrival times are also identical, alphabetical transaction_id tie-breaker applies.
    """
    queue = InMemoryQueueRegistry()
    queue_key = "mandi:queue:test_tie"

    # Two items with identical score 50.0000
    # Txn 1 arrived earlier at t=1000
    # Txn 2 arrived later at t=2000
    queue.zadd(queue_key, "TXN-LATER-002", 50.0, 2000.0)
    queue.zadd(queue_key, "TXN-EARLIER-001", 50.0, 1000.0)

    items = queue.get_sorted_items(queue_key)
    assert len(items) == 2
    # Earlier arrival should come first
    assert items[0][0] == "TXN-EARLIER-001"
    assert items[1][0] == "TXN-LATER-002"

    # Both have identical arrival time -> deterministic member string tie-break
    queue.clear(queue_key)
    queue.zadd(queue_key, "TXN-Z", 60.0, 1000.0)
    queue.zadd(queue_key, "TXN-A", 60.0, 1000.0)
    items2 = queue.get_sorted_items(queue_key)
    assert items2[0][0] == "TXN-A"
    assert items2[1][0] == "TXN-Z"


def test_queue_dispatch_pop_transitions_state(client: TestClient, db_session: Session):
    """
    Verifies that dispatching from the active queue pops the highest-priority vehicle
    and transitions its transaction record to ROUTED_TO_WEIGHBRIDGE.
    """
    mandi, farmer, slot, reservation = setup_phase3_environment(db_session)
    txn_id = reservation.transaction_id

    # Assess quality -> APPROVED -> enqueued
    client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 14.5
        }
    )
    assert queue_manager.queue_length(mandi.mandi_id) == 1

    # Check vehicle status in queue
    status_resp = client.get(f"/api/v1/queue/{mandi.mandi_id}/status/{txn_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["in_queue"] is True
    assert status_resp.json()["rank"] == 1
    assert status_resp.json()["total_ahead"] == 0

    # Dispatch vehicle to weighbridge
    disp_resp = client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")
    assert disp_resp.status_code == 200
    disp_data = disp_resp.json()
    assert disp_data["transaction_id"] == txn_id
    assert disp_data["new_state"] == "ROUTED_TO_WEIGHBRIDGE"

    # Verify DB transaction state transition
    db_session.expire_all()
    db_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert db_log.current_state == "ROUTED_TO_WEIGHBRIDGE"

    # Verify vehicle is popped from active queue
    assert queue_manager.queue_length(mandi.mandi_id) == 0


def test_supervisor_override_readmits_rejected_lot(client: TestClient, db_session: Session):
    """
    AC-007: An authenticated supervisor override token can re-admit a QUALITY_REJECTED
    lot with an auditable reason and optional recalibrated moisture.
    """
    mandi, farmer, slot, reservation = setup_phase3_environment(db_session)
    txn_id = reservation.transaction_id
    settings = get_settings()

    # Reject lot with 18.0% moisture
    client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 18.0
        }
    )

    # 1. Attempt override with invalid supervisor token -> 403
    bad_resp = client.post(
        "/api/v1/quality/override",
        json={
            "transaction_id": txn_id,
            "supervisor_token": "FORGED_INVALID_TOKEN",
            "reason": "Test unauthorized override"
        }
    )
    assert bad_resp.status_code == 403

    # 2. Attempt override with valid supervisor token -> 200
    good_resp = client.post(
        "/api/v1/quality/override",
        json={
            "transaction_id": txn_id,
            "supervisor_token": settings.MANDIQ_SECRET_HMAC_KEY,
            "reason": "Grain sun-dried on apron; re-tested moisture now 14.8%",
            "calibrated_moisture_pct": 14.8
        }
    )
    assert good_resp.status_code == 200
    good_data = good_resp.json()
    assert good_data["status"] == "QUALITY_APPROVED"
    assert good_data["priority_score"] > 0.0
    assert good_data["queue_position"] == 1

    # Verify DB updated state
    db_session.expire_all()
    db_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert db_log.current_state == "QUALITY_APPROVED"
    assert float(db_log.crop_moisture_pct) == 14.8

    # Verify vehicle is now in active queue
    assert queue_manager.queue_length(mandi.mandi_id) == 1


def test_quality_assessment_invalid_initial_state(client: TestClient, db_session: Session):
    """
    Verifies that a lot in SLOT_BOOKED (which has not checked in at the gate)
    cannot be assessed for quality, raising HTTP 409 Conflict.
    """
    mandi = Mandi(
        name="Sehore Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2000.00,
        active_weighbridges=1,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="d8e9f0123456789abcde0",
        name="Suresh Verma",
        mobile_number="9876543213",
        bank_account_hash="bank_hash_suresh_004",
        ifsc_code="SBIN0001050",
        land_area_hectares=2.00,
        registered_crop_type="Wheat",
        production_ceiling_qt=50.0
    )
    db_session.add_all([mandi, farmer])
    db_session.commit()

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=50.0,
        booked_capacity_qt=0.00,
        version=1
    )
    db_session.add(slot)
    db_session.commit()

    reservation = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=15.0
    )
    txn_id = reservation.transaction_id

    # Attempt quality assessment without gate check-in
    resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 13.0
        }
    )
    assert resp.status_code == 409
    assert "gate entry" in resp.json()["detail"].lower()


def test_anti_starvation_bonus_scales_with_wait_time():
    """
    Verifies anti-starvation bonus W_i = min(20.0, 0.1 * wait_minutes).
    Grows linearly by 0.1 points/min and caps at 20.0 points.
    """
    assert calculate_wait_bonus(0.0) == 0.0
    assert calculate_wait_bonus(10.0) == 1.0
    assert calculate_wait_bonus(50.0) == 5.0
    assert calculate_wait_bonus(100.0) == 10.0
    assert calculate_wait_bonus(200.0) == 20.0
    assert calculate_wait_bonus(300.0) == 20.0  # Capped at 20.0


def test_no_raw_secrets_exposed_in_quality_responses(client: TestClient, db_session: Session):
    """
    Verifies that cryptographic secrets are never exposed in quality or queue API responses.
    """
    mandi, farmer, slot, reservation = setup_phase3_environment(db_session)
    txn_id = reservation.transaction_id
    settings = get_settings()

    resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 14.2
        }
    )
    body = resp.text
    assert settings.MANDIQ_SECRET_HMAC_KEY not in body
    assert settings.MANDIQ_PAYOUT_SECRET_KEY not in body

    q_resp = client.get(f"/api/v1/queue/{mandi.mandi_id}")
    assert settings.MANDIQ_SECRET_HMAC_KEY not in q_resp.text
    assert settings.MANDIQ_PAYOUT_SECRET_KEY not in q_resp.text
