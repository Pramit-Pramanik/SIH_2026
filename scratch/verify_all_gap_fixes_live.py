import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_live_gap_fixes():
    session = httpx.Client()

    # 1. Test Health
    health = session.get(f"{BASE_URL}/health")
    assert health.status_code == 200, f"Health check failed: {health.status_code}"
    print("[PASS] 1. Health check 200 OK")

    # 2. Test GET /api/v1/quality/{transaction_id}
    # Quality for TXN-DEMO-1002 (IN_QA_QUEUE or QUALITY_APPROVED)
    q_resp = session.get(f"{BASE_URL}/quality/TXN-DEMO-1002")
    assert q_resp.status_code == 200, f"GET quality failed: {q_resp.status_code} {q_resp.text}"
    q_data = q_resp.json()
    assert q_data["transaction_id"] == "TXN-DEMO-1002"
    print(f"[PASS] 2. GET /quality/TXN-DEMO-1002 returned status: {q_data.get('status')}, moisture: {q_data.get('crop_moisture_pct')}%")

    # 3. Test GET /api/v1/farmers/{farmer_id}/latest-booking
    latest_resp = session.get(f"{BASE_URL}/farmers/1/latest-booking")
    assert latest_resp.status_code == 200, f"GET latest-booking failed: {latest_resp.status_code} {latest_resp.text}"
    latest_data = latest_resp.json()
    assert latest_data["has_booking"] is True
    booking = latest_data["booking"]
    print(f"[PASS] 3. GET /farmers/1/latest-booking returned: {booking.get('transaction_id')} in state {booking.get('current_state')}")

    # 4. Test Slot Reservation + Slot Cancellation lifecycle
    # Query available slots first
    slots_resp = session.get(f"{BASE_URL}/slots?mandi_id=1&scheduled_date=2026-09-18")
    assert slots_resp.status_code == 200, f"Slots listing failed: {slots_resp.status_code}"
    slots = slots_resp.json()
    assert len(slots) > 0, "No slots found for mandi 1"
    target_slot_id = slots[0]["slot_id"]

    reserve_payload = {
        "mandi_id": 1,
        "slot_id": target_slot_id,
        "farmer_id": 1,
        "requested_qty_qt": 2.0
    }
    res_resp = session.post(f"{BASE_URL}/slots/reserve", json=reserve_payload)
    assert res_resp.status_code == 201, f"Slot reserve failed: {res_resp.status_code} {res_resp.text}"
    res_data = res_resp.json()
    test_txn_id = res_data["transaction_id"]
    print(f"[PASS] 4a. POST /slots/reserve created: {test_txn_id}")

    # Now Cancel the slot
    cancel_resp = session.post(f"{BASE_URL}/slots/cancel", json={"transaction_id": test_txn_id})
    assert cancel_resp.status_code == 200, f"POST /slots/cancel failed: {cancel_resp.status_code} {cancel_resp.text}"
    cancel_data = cancel_resp.json()
    assert cancel_data["current_state"] == "CANCELLED"
    print(f"[PASS] 4b. POST /slots/cancel successfully cancelled {test_txn_id}: status={cancel_data['status']}")

    # 5. Test Admin Login and DELETE /api/v1/admin/crops/{crop_id}
    login_resp = session.post(f"{BASE_URL}/auth/token", json={"username": "admin1", "password": "password123"})
    assert login_resp.status_code == 200, f"Admin login failed: {login_resp.status_code} {login_resp.text}"
    admin_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # First add a test crop as admin
    new_crop_payload = {
        "crop_name": "Live Verification Crop",
        "commodity_code": "LIVE-VER-01",
        "standard_moisture_pct": 12.0,
        "max_moisture_pct": 16.0,
        "base_msp_inr": 2400.00
    }
    crop_create = session.post(f"{BASE_URL}/admin/crops", json=new_crop_payload, headers=headers)
    assert crop_create.status_code == 201, f"Crop creation failed: {crop_create.status_code} {crop_create.text}"
    created_crop_id = crop_create.json()["crop_id"]
    print(f"[PASS] 5a. Admin created test crop ID: {created_crop_id}")

    # Now DELETE the crop
    crop_del = session.delete(f"{BASE_URL}/admin/crops/{created_crop_id}", headers=headers)
    assert crop_del.status_code == 200, f"DELETE /admin/crops failed: {crop_del.status_code} {crop_del.text}"
    print(f"[PASS] 5b. Admin successfully deleted crop ID {created_crop_id}: {crop_del.json().get('detail')}")

    # Verify crop is deactivated/not active in crops list
    crops_resp = session.get(f"{BASE_URL}/crops")
    active_crop_ids = [c["crop_id"] for c in crops_resp.json()]
    assert created_crop_id not in active_crop_ids
    print(f"[PASS] 5c. Deactivated crop {created_crop_id} is excluded from active crop listings")

    print("\nALL LIVE ENDPOINT TESTS PASSED COMPLETELY!")

if __name__ == '__main__':
    test_live_gap_fixes()
