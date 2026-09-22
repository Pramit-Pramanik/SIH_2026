import time
import uuid
from datetime import datetime, timezone, time as dt_time, date as dt_date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.log import ProcurementLog
from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.user import User
from backend.app.core.security import create_access_jwt


def test_dynamic_crop_reservation_and_sync(client: TestClient, db_session: Session):
    """
    Verifies that:
    1. Reserving a slot with a specific crop (e.g. Mustard (Pusa Bold)) dynamically sets
       the crop on the authoritative transaction (does not default to Wheat (HD-2967)).
    2. Submitting offline WAL mutations (e.g. BILL_GENERATED, PAYMENT_SETTLED) with 0 or missing
       farmer_id / mandi_id inherits from the authoritative transaction and reconciles cleanly
       with HTTP 200 without HTTP 403.
    """
    # 1. Setup mandi, farmer, slot, crop, user
    mandi = db_session.query(Mandi).filter(Mandi.mandi_id == 1).first()
    if not mandi:
        mandi = Mandi(
            mandi_id=1,
            name="Sehore APMC Mandi",
            district="Sehore",
            state="Madhya Pradesh",
            daily_capacity_qt=1000.0,
            is_operational=True
        )
        db_session.add(mandi)
        db_session.commit()

    farmer = db_session.query(Farmer).filter(Farmer.farmer_id == 1).first()
    if not farmer:
        farmer = Farmer(
            farmer_id=1,
            aadhaar_hash="aadhaar_hash_ramesh_1",
            name="Ramesh Kumar",
            mobile_number="9876543210",
            bank_account_hash="bank_hash_ramesh_1",
            ifsc_code="SBIN0001042",
            land_area_hectares=5.0,
            registered_crop_type="Wheat (HD-2967)",
            production_ceiling_qt=600.0
        )
        db_session.add(farmer)
        db_session.commit()

    mustard = db_session.query(Crop).filter(Crop.crop_name == "Mustard (Pusa Bold)").first()
    if not mustard:
        mustard = Crop(
            crop_name="Mustard (Pusa Bold)",
            crop_code="MUSTARD_PUSA",
            category="OILSEED",
            msp_price_inr=5650.0,
            optimal_moisture_pct=10.0,
            max_moisture_pct=12.0,
            is_active=True
        )
        db_session.add(mustard)
        db_session.commit()

    today_date = datetime.now(timezone.utc).date()
    slot = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today_date
    ).first()
    if not slot:
        slot = ProcurementSlot(
            mandi_id=1,
            scheduled_date=today_date,
            start_time=dt_time(9, 0),
            end_time=dt_time(10, 0),
            allocated_capacity_qt=500.0,
            booked_capacity_qt=0.0
        )
        db_session.add(slot)
        db_session.commit()

    user = db_session.query(User).filter(User.username == "admin_dyn_test").first()
    if not user:
        user = User(
            username="admin_dyn_test",
            hashed_password="fake_hashed_pwd",
            full_name="Admin Test",
            role="ADMIN",
            mandi_id=1
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    admin_token = create_access_jwt({
        "sub": str(user.user_id),
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "mandi_id": user.mandi_id
    })
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    # 2. Test dynamic crop reservation
    reserve_payload = {
        "mandi_id": 1,
        "slot_id": slot.slot_id,
        "farmer_id": 1,
        "requested_qty_qt": 5.0,
        "crop_type": "Mustard (Pusa Bold)"
    }
    resp = client.post("/api/v1/slots/reserve", json=reserve_payload, headers=headers)
    assert resp.status_code == 201, f"Reserve failed: {resp.text}"
    res_data = resp.json()
    assert res_data["crop_type"] == "Mustard (Pusa Bold)", f"Expected Mustard (Pusa Bold), got {res_data['crop_type']}"
    txn_id = res_data["transaction_id"]

    # Verify authoritative transaction shows Mustard
    txn_resp = client.get(f"/api/v1/transactions/{txn_id}", headers=headers)
    assert txn_resp.status_code == 200
    assert txn_resp.json()["crop_type"] == "Mustard (Pusa Bold)"

    # Advance transaction through GATE, QUALITY, WEIGHBRIDGE so it reaches WEIGHED_TARE
    txn_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    txn_log.current_state = "WEIGHED_TARE"
    txn_log.gross_weight_qt = 55.0
    txn_log.tare_weight_qt = 50.0
    txn_log.net_weight_qt = 5.0
    db_session.commit()

    # 3. Test Offline WAL mutations with 0 or missing farmer_id/mandi_id (Issue 2)
    mutations_payload = {
        "mutations": [
            {
                "client_mutation_id": f"mut-test-bill-{uuid.uuid4().hex[:8]}",
                "transaction_id": txn_id,
                "farmer_id": 0,  # 0 passed from client
                "mandi_id": 0,   # 0 passed from client
                "current_state": "BILL_GENERATED",
                "payload": {
                    "net_weight_qt": 5.0,
                    "rate_per_qt": 5650.0,
                    "invoice_amount_inr": 28250.0,
                    "mutation_type": "BILL_GENERATION"
                },
                "client_timestamp": time.time()
            },
            {
                "client_mutation_id": f"mut-test-payout-{uuid.uuid4().hex[:8]}",
                "transaction_id": txn_id,
                "farmer_id": 0,
                "mandi_id": 0,
                "current_state": "PAYMENT_SETTLED",
                "payload": {
                    "amount_inr": 28250.0,
                    "dual_sig": True,
                    "mutation_type": "PAYOUT_STAGING"
                },
                "client_timestamp": time.time() + 1
            }
        ]
    }

    sync_resp = client.post("/api/v1/sync/wal", json=mutations_payload, headers=headers)
    assert sync_resp.status_code == 200, f"Sync returned error: {sync_resp.status_code} {sync_resp.text}"
    sync_data = sync_resp.json()
    assert sync_data["synced_count"] == 2, f"Expected 2 synced records, got {sync_data}"
    assert all(r["status"] in ("SYNCED", "CONFLICT_RESOLVED") for r in sync_data["results"])

    # Verify final transaction state
    db_session.expire_all()
    updated_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert updated_log.current_state == "PAYMENT_SETTLED"
    assert updated_log.crop_type == "Mustard (Pusa Bold)"
