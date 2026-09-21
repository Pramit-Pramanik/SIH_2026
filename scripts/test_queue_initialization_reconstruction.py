#!/usr/bin/env python3
"""
MandiQ AUD-005 / AUD-006: Queue Initialization and Authoritative Reconstruction
Forensic Acceptance Verification Script.

Executes all 9 verification tests required by the specification:
1. bootstrap queue populated
2. Redis unavailable (in-memory fallback guarantees exact IDs, scores, and states)
3. backend restart (simulated restart / queue cache wipe)
4. queue reconstruction (authoritative derivation from persisted DB state)
5. same DB data produces same ordering (determinism across multiple reconstructions)
6. tie-breaking (FIFO by arrival timestamp, then alphabetical transaction ID)
7. dispatch (ZPOPMAX winner pops and transitions state to ROUTED_TO_WEIGHBRIDGE)
8. quality rejection removes queue item (moisture > 17.0% excludes from queue)
9. quality approval / supervisor override re-adds queue item
10. data integrity enforcement (controlled error on missing data; no 14.0%, 50.0 qt, 15 min fabrication)
"""

import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.log import ProcurementLog
from backend.app.models.slot import ProcurementSlot
from backend.app.core.security import generate_booking_signature
from backend.app.services.seed_service import bootstrap_database, ensure_showcase_queue_state
from backend.app.services.queue_manager import queue_manager, QueueDataIntegrityError
from backend.app.services.quality_service import (
    reconstruct_mandi_queue,
    get_mandi_queue_list,
    dispatch_top_vehicle_from_queue,
    get_vehicle_queue_status,
    assess_quality_and_enqueue,
    override_quality_and_admit
)
from backend.app.schemas.quality import QualityAssessmentRequest, QualityOverrideRequest


def main():
    print("=" * 80)
    print("AUD-005 / AUD-006: QUEUE INITIALIZATION AND RECONSTRUCTION VERIFIER")
    print("=" * 80)

    db = SessionLocal()
    client = TestClient(app)

    try:
        # Authenticate ADMIN
        login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@MandiQ2026"})
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        admin_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # --------------------------------------------------------------------------
        # Test 1: Bootstrap Queue Populated
        # --------------------------------------------------------------------------
        print("\n[Step 1] Verifying bootstrap queue populated authoritatively...")
        boot_res = bootstrap_database(db, reset=True)
        assert boot_res["status"] == "SUCCESS", "Bootstrap failed"

        q1 = queue_manager.get_queue(1)
        q1_ids = [item[0] for item in q1]
        assert "TXN-DEMO-1002" in q1_ids, f"TXN-DEMO-1002 missing from bootstrapped queue: {q1_ids}"
        score_1002 = queue_manager.get_score(1, "TXN-DEMO-1002")
        assert score_1002 is not None and score_1002 > 0.0
        print(f"  [+] PASS: Mandi 1 queue primed with TXN-DEMO-1002 (Score: {score_1002:.4f})")

        # --------------------------------------------------------------------------
        # Test 2: Redis Unavailable — In-Memory Fallback
        # --------------------------------------------------------------------------
        print("\n[Step 2] Verifying in-memory fallback when Redis is unavailable...")
        with patch.object(queue_manager, "_get_redis", return_value=None):
            mandi_id = 999
            queue_manager.clear(mandi_id)
            queue_manager.enqueue(mandi_id, "TXN-INMEM-1", 60.00, arrival_ts=500.0)
            queue_manager.enqueue(mandi_id, "TXN-INMEM-2", 80.00, arrival_ts=600.0)

            inmem_q = queue_manager.get_queue(mandi_id)
            assert len(inmem_q) == 2
            assert inmem_q[0] == ("TXN-INMEM-2", 80.00)
            assert inmem_q[1] == ("TXN-INMEM-1", 60.00)
            assert queue_manager.get_arrival_timestamp(mandi_id, "TXN-INMEM-1") == 500.0
            assert queue_manager.get_arrival_timestamp(mandi_id, "TXN-INMEM-2") == 600.0
            queue_manager.clear(mandi_id)
        print("  [+] PASS: In-memory fallback maintains exact IDs, scores, and arrival timestamps.")

        # --------------------------------------------------------------------------
        # Test 3 & 4: Backend Restart & Authoritative Queue Reconstruction
        # --------------------------------------------------------------------------
        print("\n[Step 3 & 4] Simulating backend restart and authoritative queue reconstruction...")
        today = date.today()
        slot = db.query(ProcurementSlot).filter(
            ProcurementSlot.mandi_id == 1,
            ProcurementSlot.scheduled_date == today
        ).first()
        assert slot is not None, "Slot for Mandi 1 missing"

        test_txn_id = "TXN-RESTART-RECONSTRUCT-001"
        existing = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == test_txn_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        txn_recon = ProcurementLog(
            transaction_id=test_txn_id,
            farmer_id=1,
            mandi_id=1,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_type="Wheat (HD-2967)",
            crop_moisture_pct=14.50,
            net_weight_qt=85.00,
            current_state="QUALITY_APPROVED",
            token_signature=generate_booking_signature(1, 1, slot.slot_id, 85.0),
            created_at=datetime.now(timezone.utc) - timedelta(minutes=15)
        )
        db.add(txn_recon)
        db.commit()

        # Simulate backend restart: Clear memory/Redis queue completely
        queue_manager.clear(1)
        assert queue_manager.queue_length(1) == 0, "Queue not empty after wipe"

        # Call endpoint to trigger reconstruction
        recon_resp = client.get("/api/v1/queue/1")
        assert recon_resp.status_code == 200, f"Queue retrieval failed: {recon_resp.text}"
        recon_data = recon_resp.json()
        recon_ids = [item["transaction_id"] for item in recon_data["items"]]
        assert test_txn_id in recon_ids, f"{test_txn_id} not reconstructed into active queue: {recon_ids}"

        # Verify no fabricated values
        item_obj = next(it for it in recon_data["items"] if it["transaction_id"] == test_txn_id)
        assert item_obj["quantity_qt"] == 85.00, f"Fabricated weight: expected 85.0, got {item_obj['quantity_qt']}"
        assert item_obj["arrival_timestamp"] is not None
        print(f"  [+] PASS: Queue reconstructed from DB after restart (Txn: {test_txn_id}, Rank: {item_obj['rank']}, Score: {item_obj['priority_score']})")

        # --------------------------------------------------------------------------
        # Test 5: Same DB Data Produces Same Ordering (Determinism)
        # --------------------------------------------------------------------------
        print("\n[Step 5] Verifying identical ordering across repeated reconstructions...")
        fixed_now = 1800000000.0
        q_pass1 = reconstruct_mandi_queue(db, mandi_id=1, current_time=fixed_now)
        queue_manager.clear(1)
        q_pass2 = reconstruct_mandi_queue(db, mandi_id=1, current_time=fixed_now)
        queue_manager.clear(1)
        q_pass3 = reconstruct_mandi_queue(db, mandi_id=1, current_time=fixed_now)

        assert q_pass1 == q_pass2 == q_pass3, "Reconstruction ordering is non-deterministic!"
        print(f"  [+] PASS: 3 sequential reconstructions produced 100% identical ordering ({len(q_pass1)} items).")

        # --------------------------------------------------------------------------
        # Test 6: Deterministic Tie-Breaking
        # --------------------------------------------------------------------------
        print("\n[Step 6] Verifying deterministic tie-breaking (FIFO by arrival, then alphabetical ID)...")
        queue_manager.clear(888)
        # Case A: Same score, different arrivals
        queue_manager.enqueue(888, "TXN-ARRIVE-LATE", 50.00, arrival_ts=2000.0)
        queue_manager.enqueue(888, "TXN-ARRIVE-EARLY", 50.00, arrival_ts=1000.0)
        q_tb1 = queue_manager.get_queue(888)
        assert q_tb1[0][0] == "TXN-ARRIVE-EARLY"
        assert q_tb1[1][0] == "TXN-ARRIVE-LATE"

        # Case B: Same score AND same arrival -> Alphabetical
        queue_manager.clear(888)
        queue_manager.enqueue(888, "TXN-BRAVO", 50.00, arrival_ts=1000.0)
        queue_manager.enqueue(888, "TXN-ALPHA", 50.00, arrival_ts=1000.0)
        q_tb2 = queue_manager.get_queue(888)
        assert q_tb2[0][0] == "TXN-ALPHA"
        assert q_tb2[1][0] == "TXN-BRAVO"
        queue_manager.clear(888)
        print("  [+] PASS: Deterministic tie-breaking strictly verified.")

        # --------------------------------------------------------------------------
        # Test 7: Dispatch Pop
        # --------------------------------------------------------------------------
        print("\n[Step 7] Verifying dispatch_top_vehicle_from_queue (ZPOPMAX with state mutation)...")
        # Mandi 1 has vehicles in queue
        pre_dispatch_q = queue_manager.get_queue(1)
        assert len(pre_dispatch_q) > 0
        top_expected = pre_dispatch_q[0][0]

        disp_resp = client.post("/api/v1/queue/1/dispatch", headers=headers)
        assert disp_resp.status_code == 200, f"Dispatch failed: {disp_resp.text}"
        disp_data = disp_resp.json()
        assert disp_data["transaction_id"] == top_expected
        assert disp_data["new_state"] == "ROUTED_TO_WEIGHBRIDGE"

        # Confirm popped from queue
        post_dispatch_q = queue_manager.get_queue(1)
        post_ids = [item[0] for item in post_dispatch_q]
        assert top_expected not in post_ids
        print(f"  [+] PASS: Dispatched '{top_expected}' to weighbridge; successfully removed from queue.")

        # --------------------------------------------------------------------------
        # Test 8: Quality Rejection Removes Queue Item
        # --------------------------------------------------------------------------
        print("\n[Step 8] Verifying quality rejection (moisture > 17.0%) excludes/removes queue item...")
        txn_rej_id = "TXN-REJECT-TEST-001"
        existing_rej = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_rej_id).first()
        if existing_rej:
            db.delete(existing_rej)
            db.commit()

        txn_rej = ProcurementLog(
            transaction_id=txn_rej_id,
            farmer_id=1,
            mandi_id=1,
            slot_id=slot.slot_id,
            scheduled_date=today,
            net_weight_qt=60.00,
            crop_moisture_pct=None,
            current_state="GATE_ENTRY_VERIFIED",
            token_signature=generate_booking_signature(1, 1, slot.slot_id, 60.0)
        )
        db.add(txn_rej)
        db.commit()

        rej_resp = client.post(
            "/api/v1/quality/assess",
            json={"transaction_id": txn_rej_id, "crop_moisture_pct": 18.50},
            headers=headers
        )
        assert rej_resp.status_code == 200, f"Quality assess failed: {rej_resp.text}"
        rej_data = rej_resp.json()
        assert rej_data["status"] == "QUALITY_REJECTED"
        assert rej_data["eligible_for_queue"] is False
        assert queue_manager.get_rank(1, txn_rej_id) is None
        print(f"  [+] PASS: Moisture 18.50% triggered QUALITY_REJECTED; vehicle excluded from queue.")

        # --------------------------------------------------------------------------
        # Test 9: Quality Approval / Supervisor Override Re-adds Queue Item
        # --------------------------------------------------------------------------
        print("\n[Step 9] Verifying supervisor override re-admits vehicle to active queue...")
        override_resp = client.post(
            "/api/v1/quality/override",
            json={
                "transaction_id": txn_rej_id,
                "calibrated_moisture_pct": 14.80,
                "reason": "Aeration drying cycle completed; moisture calibrated to 14.80%."
            },
            headers=headers
        )
        assert override_resp.status_code == 200, f"Override failed: {override_resp.text}"
        override_data = override_resp.json()
        assert override_data["status"] == "QUALITY_APPROVED"
        assert override_data["queue_position"] is not None
        assert queue_manager.get_rank(1, txn_rej_id) is not None
        print(f"  [+] PASS: Supervisor override re-admitted vehicle with queue rank {override_data['queue_position']}.")

        # --------------------------------------------------------------------------
        # Test 10: Data Integrity Enforcement (No Fabricated Fallbacks)
        # --------------------------------------------------------------------------
        print("\n[Step 10] Verifying controlled QueueDataIntegrityError when required data is missing...")
        corrupt_txn_id = "TXN-INTEGRITY-CORRUPT-001"
        existing_corrupt = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == corrupt_txn_id).first()
        if existing_corrupt:
            db.delete(existing_corrupt)
            db.commit()

        # Missing moisture: system must NEVER fabricate 14.0%
        corrupt_txn = ProcurementLog(
            transaction_id=corrupt_txn_id,
            farmer_id=1,
            mandi_id=1,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_moisture_pct=None,  # MISSING!
            net_weight_qt=75.00,
            current_state="QUALITY_APPROVED",
            token_signature=generate_booking_signature(1, 1, slot.slot_id, 75.0)
        )
        db.add(corrupt_txn)
        db.commit()

        try:
            reconstruct_mandi_queue(db, mandi_id=1)
            raise AssertionError("Expected QueueDataIntegrityError for missing moisture, but none was raised!")
        except QueueDataIntegrityError as err:
            assert "moisture" in str(err.detail).lower()
            print(f"  [+] PASS: Missing moisture rejected with controlled QueueDataIntegrityError: {err.detail}")

        # Missing weight: system must NEVER fabricate 50.0 qt
        corrupt_txn.crop_moisture_pct = 13.50
        corrupt_txn.net_weight_qt = None  # MISSING!
        db.commit()

        try:
            reconstruct_mandi_queue(db, mandi_id=1)
            raise AssertionError("Expected QueueDataIntegrityError for missing weight, but none was raised!")
        except QueueDataIntegrityError as err_w:
            assert "quantity" in str(err_w.detail).lower() or "weight" in str(err_w.detail).lower()
            print(f"  [+] PASS: Missing weight rejected with controlled QueueDataIntegrityError: {err_w.detail}")

        # Cleanup corrupt test record so queue remains pristine
        db.delete(corrupt_txn)
        db.commit()

        print("\n" + "=" * 80)
        print("ALL 10 VERIFICATION CHECKS PASSED: AUD-005/AUD-006 REMEDIATION 100% SUCCESSFUL")
        print("=" * 80)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
