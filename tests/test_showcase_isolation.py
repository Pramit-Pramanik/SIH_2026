"""
Test Suite: Showcase Reset Data Isolation (AUD-004)
Verifies that showcase database reset NEVER deletes arbitrary operational transactions,
strictly isolates showcase entities, preserves real transactions, real bookings,
and real payments, and rejects missing targets with clear errors instead of silent fallbacks.
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.log import ProcurementLog
from backend.app.models.slot import ProcurementSlot
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.core.security import generate_booking_signature
from backend.app.services.seed_service import (
    bootstrap_database,
    reset_showcase_data,
    ensure_canonical_slots
)
from backend.app.services.queue_manager import queue_manager


def get_admin_token(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@MandiQ2026"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def test_showcase_reset_isolates_and_preserves_real_data(client: TestClient, db_session: Session):
    """
    1. Create real operational transaction
    2. Create dynamic showcase transaction
    3. Reset showcase
    4. Verify showcase transaction reset
    5. Verify real transaction still exists and retains state, payments, and booking
    6. Repeat reset three times
    7. Verify idempotency
    """
    # Baseline setup
    bootstrap_database(db_session, reset=False)
    admin_token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    today = date.today()
    slot = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today
    ).order_by(ProcurementSlot.start_time.asc()).first()
    assert slot is not None

    real_txn_id = "TXN-REAL-OPERATIONAL-9901"
    real_sig = generate_booking_signature(1, 1, slot.slot_id, 50.0)

    # 1. Create real transaction (is_showcase=False, demo_run_id=None)
    real_txn = ProcurementLog(
        transaction_id=real_txn_id,
        farmer_id=1,
        mandi_id=1,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_type="Wheat (HD-2967)",
        crop_moisture_pct=11.5,
        gross_weight_qt=85.0,
        tare_weight_qt=35.0,
        net_weight_qt=50.0,
        total_payout_inr=113750.00,
        current_state="PAYMENT_SETTLED",
        token_signature=real_sig,
        payout_block_hash="AUTH_PFMS_REAL_PAYMENT_HASH_9901",
        is_showcase=False,
        demo_run_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(real_txn)

    # 2. Create dynamic showcase transaction (is_showcase=True, demo_run_id="SHOWCASE_TEMP")
    showcase_dyn_id = "TXN-DEMO-DYNAMIC-TEMP-8801"
    showcase_sig = generate_booking_signature(1, 1, slot.slot_id, 25.0)
    showcase_txn = ProcurementLog(
        transaction_id=showcase_dyn_id,
        farmer_id=1,
        mandi_id=1,
        slot_id=slot.slot_id,
        scheduled_date=today,
        crop_type="Wheat (HD-2967)",
        net_weight_qt=25.0,
        current_state="GATE_ENTRY_VERIFIED",
        token_signature=showcase_sig,
        is_showcase=True,
        demo_run_id="SHOWCASE_TEMP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(showcase_txn)

    # Mutate canonical showcase transaction TXN-DEMO-1001 to a non-starting state
    c1 = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == "TXN-DEMO-1001").first()
    c1.current_state = "PAYMENT_SETTLED"
    db_session.commit()

    # Enqueue both real and showcase vehicles in queue
    queue_manager.enqueue(mandi_id=1, transaction_id=real_txn_id, priority_score=85.0, arrival_ts=1000.0)
    queue_manager.enqueue(mandi_id=1, transaction_id=showcase_dyn_id, priority_score=40.0, arrival_ts=1050.0)

    # 3. Reset showcase via API
    resp = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1}, headers=headers)
    assert resp.status_code == 200, f"Reset failed: {resp.text}"

    # 4. Verify showcase transaction reset
    # Dynamic showcase transaction should be purged
    assert db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == showcase_dyn_id).first() is None

    # Canonical showcase transaction TXN-DEMO-1001 should be reset to GATE_ENTRY_VERIFIED
    db_session.refresh(c1)
    assert c1.current_state == "GATE_ENTRY_VERIFIED"

    # 5. Verify real transaction still exists and retains ALL state
    real_check = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == real_txn_id).first()
    assert real_check is not None, "FATAL: Showcase reset deleted operational transaction!"
    assert real_check.current_state == "PAYMENT_SETTLED"
    assert float(real_check.total_payout_inr) == 113750.00
    assert real_check.payout_block_hash == "AUTH_PFMS_REAL_PAYMENT_HASH_9901"
    assert real_check.is_showcase is False

    # Verify real queue entry was preserved while dynamic showcase was cleared
    active_q = [item[0] for item in queue_manager.get_queue(mandi_id=1)]
    assert real_txn_id in active_q, "Real queued vehicle was erroneously purged!"
    assert showcase_dyn_id not in active_q, "Showcase queued vehicle should have been purged!"
    assert "TXN-DEMO-1002" in active_q, "Canonical showcase vehicle should be enqueued!"

    # 6. Repeat reset 3 times to verify idempotency
    for i in range(3):
        r = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1}, headers=headers)
        assert r.status_code == 200, f"Repeat reset {i+1} failed: {r.text}"

        # 7. Verify idempotency
        real_check_repeat = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == real_txn_id).first()
        assert real_check_repeat is not None, f"Operational transaction missing after repeat reset {i+1}!"
        assert real_check_repeat.current_state == "PAYMENT_SETTLED"
        assert float(real_check_repeat.total_payout_inr) == 113750.00
        assert real_check_repeat.payout_block_hash == "AUTH_PFMS_REAL_PAYMENT_HASH_9901"


def test_showcase_reset_removes_silent_fallbacks(client: TestClient, db_session: Session):
    """
    Verifies that missing targets (mandi_id, farmer_id) produce explicit errors (404/422),
    never silently defaulting to mandi_id=1, farmer_id=1, or slot_id=1.
    """
    bootstrap_database(db_session, reset=False)
    admin_token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Non-existent mandi -> 404
    r_mandi_404 = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 99999}, headers=headers)
    assert r_mandi_404.status_code == 404
    assert "Mandi with ID 99999 not found" in r_mandi_404.json()["detail"]

    # 2. Non-existent farmer -> 404
    r_farmer_404 = client.post("/api/v1/admin/reset-showcase", json={"farmer_id": 88888}, headers=headers)
    assert r_farmer_404.status_code == 404
    assert "Farmer with ID 88888 not found" in r_farmer_404.json()["detail"]

    # 3. Negative mandi -> 422
    r_mandi_422 = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": -1}, headers=headers)
    assert r_mandi_422.status_code == 422

    # 4. Negative farmer -> 422
    r_farmer_422 = client.post("/api/v1/admin/reset-showcase", json={"farmer_id": -1}, headers=headers)
    assert r_farmer_422.status_code == 422


def test_direct_bootstrap_database_reset_never_deletes_operational_transactions(db_session: Session):
    """
    Verifies that direct invocation of bootstrap_database(reset=True) does not purge
    any transaction where is_showcase == False.
    """
    bootstrap_database(db_session, reset=False)

    today = date.today()
    real_id = "TXN-REAL-OP-RETAIN-TEST"
    real_sig = generate_booking_signature(2, 1, 1, 40.0)

    operational_txn = ProcurementLog(
        transaction_id=real_id,
        farmer_id=2,
        mandi_id=1,
        slot_id=1,
        scheduled_date=today,
        crop_type="Paddy (Common)",
        net_weight_qt=40.0,
        total_payout_inr=87500.00,
        current_state="BILL_GENERATED",
        token_signature=real_sig,
        is_showcase=False,
        demo_run_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(operational_txn)
    db_session.commit()

    # Call bootstrap_database with reset=True
    bootstrap_database(db_session, reset=True)

    # Operational transaction must remain
    fetched = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == real_id).first()
    assert fetched is not None, "FATAL: Direct bootstrap reset purged operational transaction!"
    assert fetched.current_state == "BILL_GENERATED"
    assert float(fetched.total_payout_inr) == 87500.00
