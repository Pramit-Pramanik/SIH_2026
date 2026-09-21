"""
MandiQ AUD-004: Isolate Showcase Reset from Operational Data — Forensic Verification Script.

Executes the exact 7 verification steps from the specification:
1. create real transaction
2. create showcase transaction
3. reset showcase
4. verify showcase transaction reset
5. verify real transaction still exists and retains state
6. repeat reset three times
7. verify idempotency
8. verify no silent fallbacks (404/422 on invalid targets)
"""

import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.log import ProcurementLog
from backend.app.models.slot import ProcurementSlot
from backend.app.core.security import generate_booking_signature
from backend.app.services.seed_service import bootstrap_database
from backend.app.services.queue_manager import queue_manager


def main():
    print("=" * 80)
    print("AUD-004 FORENSIC VERIFICATION: ISOLATE SHOWCASE RESET FROM OPERATIONAL DATA")
    print("=" * 80)

    db = SessionLocal()
    client = TestClient(app)

    try:
        # Initial baseline setup
        bootstrap_database(db, reset=False)

        # Authenticate as ADMIN
        login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@MandiQ2026"})
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        admin_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        today = date.today()
        slot = db.query(ProcurementSlot).filter(
            ProcurementSlot.mandi_id == 1,
            ProcurementSlot.scheduled_date == today
        ).order_by(ProcurementSlot.start_time.asc()).first()
        assert slot is not None, "Failed to resolve today's slot for Mandi 1"

        # --------------------------------------------------------------------------
        # Step 1: Create Real Transaction
        # --------------------------------------------------------------------------
        real_txn_id = "TXN-REAL-OP-FORENSIC-001"
        real_sig = generate_booking_signature(1, 1, slot.slot_id, 55.0)

        # Clean up any leftover from previous runs
        db.query(ProcurementLog).filter(ProcurementLog.transaction_id == real_txn_id).delete()
        db.commit()

        real_txn = ProcurementLog(
            transaction_id=real_txn_id,
            farmer_id=1,
            mandi_id=1,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_type="Wheat (HD-2967)",
            crop_moisture_pct=11.2,
            gross_weight_qt=85.0,
            tare_weight_qt=30.0,
            net_weight_qt=55.0,
            total_payout_inr=125125.00,
            current_state="PAYMENT_SETTLED",
            token_signature=real_sig,
            payout_block_hash="PFMS_BLOCK_HASH_OPERATIONAL_REAL_001",
            is_showcase=False,
            demo_run_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(real_txn)
        db.commit()
        print(f"[STEP 1 SUCCESS] Created real operational transaction: {real_txn_id} (is_showcase=False, state=PAYMENT_SETTLED)")

        # --------------------------------------------------------------------------
        # Step 2: Create Showcase Transaction
        # --------------------------------------------------------------------------
        showcase_dyn_id = "TXN-DEMO-SIM-TEMP-FORENSIC-002"
        showcase_sig = generate_booking_signature(1, 1, slot.slot_id, 30.0)

        # Clean up any leftover
        db.query(ProcurementLog).filter(ProcurementLog.transaction_id == showcase_dyn_id).delete()
        db.commit()

        showcase_txn = ProcurementLog(
            transaction_id=showcase_dyn_id,
            farmer_id=1,
            mandi_id=1,
            slot_id=slot.slot_id,
            scheduled_date=today,
            crop_type="Wheat (HD-2967)",
            net_weight_qt=30.0,
            current_state="GATE_ENTRY_VERIFIED",
            token_signature=showcase_sig,
            is_showcase=True,
            demo_run_id="DEMO_E2E_SHOWCASE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(showcase_txn)

        # Mutate canonical showcase transaction TXN-DEMO-1001 to dirty state
        c1 = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == "TXN-DEMO-1001").first()
        c1.current_state = "PAYMENT_SETTLED"
        db.commit()

        # Enqueue vehicles in DCDQ queue
        queue_manager.enqueue(mandi_id=1, transaction_id=real_txn_id, priority_score=80.0, arrival_ts=1000.0)
        queue_manager.enqueue(mandi_id=1, transaction_id=showcase_dyn_id, priority_score=35.0, arrival_ts=1050.0)
        print(f"[STEP 2 SUCCESS] Created showcase transaction: {showcase_dyn_id} (is_showcase=True), dirtied TXN-DEMO-1001")

        # --------------------------------------------------------------------------
        # Step 3: Reset Showcase
        # --------------------------------------------------------------------------
        r_reset = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1}, headers=headers)
        assert r_reset.status_code == 200, f"Reset showcase failed: {r_reset.text}"
        print(f"[STEP 3 SUCCESS] Executed POST /api/v1/admin/reset-showcase -> HTTP 200")

        # --------------------------------------------------------------------------
        # Step 4: Verify Showcase Transaction Reset
        # --------------------------------------------------------------------------
        # Dynamic showcase transaction must be purged
        dyn_check = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == showcase_dyn_id).first()
        assert dyn_check is None, f"Dynamic showcase transaction {showcase_dyn_id} was NOT purged!"

        # Canonical showcase transaction must be reset to pristine initial state
        db.refresh(c1)
        assert c1.current_state == "GATE_ENTRY_VERIFIED", f"Canonical TXN-DEMO-1001 was not reset: {c1.current_state}"
        print(f"[STEP 4 SUCCESS] Showcase entities cleanly reset: dynamic purged, canonical restored to GATE_ENTRY_VERIFIED")

        # --------------------------------------------------------------------------
        # Step 5: Verify Real Transaction Still Exists and Retains State
        # --------------------------------------------------------------------------
        real_check = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == real_txn_id).first()
        assert real_check is not None, "FATAL FLAW: Showcase reset DELETED operational transaction!"
        assert real_check.current_state == "PAYMENT_SETTLED", f"State corrupted: {real_check.current_state}"
        assert float(real_check.total_payout_inr) == 125125.00, f"Payout corrupted: {real_check.total_payout_inr}"
        assert real_check.payout_block_hash == "PFMS_BLOCK_HASH_OPERATIONAL_REAL_001", "Payment hash corrupted!"
        assert real_check.is_showcase is False, "Showcase discriminator corrupted!"

        # Queue verification: real vehicle preserved, showcase vehicle purged
        active_q = [item[0] for item in queue_manager.get_queue(mandi_id=1)]
        assert real_txn_id in active_q, "Real queued vehicle was erroneously purged from active queue!"
        assert showcase_dyn_id not in active_q, "Showcase vehicle was not purged from active queue!"
        assert "TXN-DEMO-1002" in active_q, "Canonical showcase vehicle TXN-DEMO-1002 missing from queue!"
        print(f"[STEP 5 SUCCESS] Real transaction PRESERVED: state, payout, block hash, and queue entry 100% intact!")

        # --------------------------------------------------------------------------
        # Step 6 & 7: Repeat Reset Three Times and Verify Idempotency
        # --------------------------------------------------------------------------
        for i in range(1, 4):
            rep_resp = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1}, headers=headers)
            assert rep_resp.status_code == 200, f"Repeat reset {i} failed: {rep_resp.text}"

            rep_real = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == real_txn_id).first()
            assert rep_real is not None, f"Operational transaction purged on iteration {i}!"
            assert rep_real.current_state == "PAYMENT_SETTLED"
            assert float(rep_real.total_payout_inr) == 125125.00
            assert rep_real.payout_block_hash == "PFMS_BLOCK_HASH_OPERATIONAL_REAL_001"
            print(f"  -> Repeat reset iteration {i}/3 passed: operational transaction fully preserved.")

        print(f"[STEP 6 & 7 SUCCESS] Triple repeat reset executed successfully. Absolute idempotency verified.")

        # --------------------------------------------------------------------------
        # Step 8: Verify Fallback Removal (No silent mandi_id=1, farmer_id=1, slot_id=1)
        # --------------------------------------------------------------------------
        r_bad_mandi = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 99999}, headers=headers)
        assert r_bad_mandi.status_code == 404, f"Expected 404 for missing mandi, got {r_bad_mandi.status_code}"

        r_bad_farmer = client.post("/api/v1/admin/reset-showcase", json={"farmer_id": 88888}, headers=headers)
        assert r_bad_farmer.status_code == 404, f"Expected 404 for missing farmer, got {r_bad_farmer.status_code}"

        r_neg_mandi = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": -99}, headers=headers)
        assert r_neg_mandi.status_code == 422, f"Expected 422 for negative mandi, got {r_neg_mandi.status_code}"

        print(f"[STEP 8 SUCCESS] Silent fallbacks completely eliminated. Non-existent targets return HTTP 404/422.")

        print("=" * 80)
        print("ALL AUD-004 FORENSIC ACCEPTANCE TESTS PASSED!")
        print("Acceptance criteria satisfied: Showcase reset CANNOT delete a real procurement transaction.")
        print("=" * 80)

    finally:
        try:
            db.query(ProcurementLog).filter(
                ProcurementLog.transaction_id.in_([
                    "TXN-REAL-OP-FORENSIC-001",
                    "TXN-DEMO-SIM-TEMP-FORENSIC-002"
                ])
            ).delete()
            db.commit()
            queue_manager.remove(1, "TXN-REAL-OP-FORENSIC-001")
            queue_manager.remove(1, "TXN-DEMO-SIM-TEMP-FORENSIC-002")
        except Exception:
            pass
        db.close()


if __name__ == "__main__":
    main()
