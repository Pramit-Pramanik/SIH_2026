#!/usr/bin/env python3
"""
MandiQ Master Forensic Remediation & E2E Workflow Stabilizer Verification Script.
Authoritative Lifecycle Verification:
FARMER LOGIN -> PROFILE -> MANDI -> SLOT -> BOOKING -> HMAC GATE PASS ->
GATE ENTRY -> QUALITY ASSESSMENT -> LIVE DCDQ QUEUE -> DISPATCH ->
WEIGHBRIDGE -> NET WEIGHT -> J-FORM BILLING -> DUAL-SIGNATURE PAYOUT -> PAYMENT_SETTLED.
"""

import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.app.main import app
from datetime import date, timedelta

client = TestClient(app)

def run_e2e_forensic_suite():
    print("=" * 75)
    print("  MANDIQ AUTHORITATIVE TRANSACTION END-TO-END FORENSIC VERIFIER")
    print("=" * 75)

    # 1. AUTHENTICATION & SINGLE FARMER LOGIN VERIFICATION (Phase 1)
    print("\n[PHASE 1] Verifying Single FARMER Authentication Model...")
    farmer_login = client.post("/api/v1/auth/login", json={"username": "farmer", "password": "Farmer@MandiQ2026"})
    assert farmer_login.status_code == 200, f"Farmer login failed: {farmer_login.text}"
    farmer_token = farmer_login.json()["access_token"]
    
    # Check /auth/me returns role FARMER and farmer_id 1
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {farmer_token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["role"] == "FARMER"
    assert me_data["farmer_id"] == 1
    print(f"  [PASS] Logged in as authoritative FARMER '{me_data['username']}', farmer_id={me_data['farmer_id']}")

    # Pruned farmer logins MUST NOT exist
    for bad_user in ["farmer_balvinder", "farmer_suresh"]:
        bad_resp = client.post("/api/v1/auth/login", json={"username": bad_user, "password": "Farmer@MandiQ2026"})
        assert bad_resp.status_code in [400, 401], f"Unexpected login success for pruned user {bad_user}"
    print("  [PASS] Pruned duplicate farmer login accounts successfully reject authentication")

    # Operational roles login
    role_tokens = {}
    for role, user, pwd in [
        ("OPERATOR", "operator", "Operator@MandiQ2026"),
        ("INSPECTOR", "inspector", "Inspector@MandiQ2026"),
        ("SUPERVISOR", "supervisor", "Supervisor@MandiQ2026"),
        ("ADMIN", "admin", "Admin@MandiQ2026"),
    ]:
        resp = client.post("/api/v1/auth/login", json={"username": user, "password": pwd})
        assert resp.status_code == 200, f"Login failed for {user}: {resp.text}"
        role_tokens[role] = resp.json()["access_token"]
    print("  [PASS] All 4 operational roles (OPERATOR, INSPECTOR, SUPERVISOR, ADMIN) authenticated cleanly")

    # 2. MANDI & SLOT DISCOVERY
    print("\n[PHASE 2 & 3] Resolving Operational Mandi, Crops, and Hourly Slots...")
    mandis_resp = client.get("/api/v1/mandis")
    assert mandis_resp.status_code == 200
    mandis = mandis_resp.json()
    assert len(mandis) >= 1
    target_mandi = next((m for m in mandis if m["mandi_id"] == 1), mandis[0])
    mandi_id = target_mandi["mandi_id"]
    mandi_name = target_mandi["name"]
    print(f"  [PASS] Resolved target Mandi: ID #{mandi_id} ({mandi_name})")

    # Reserve Slot (2.5 Quintals)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slots_resp = client.get(f"/api/v1/slots?mandi_id={mandi_id}&scheduled_date={tomorrow}&auto_provision=true")
    assert slots_resp.status_code == 200
    slots_list = slots_resp.json()
    assert len(slots_list) >= 1, f"No slots available for mandi {mandi_id} on {tomorrow}"
    slot_id = slots_list[0]["slot_id"]
    print(f"  [PASS] Selected available slot ID #{slot_id} on {tomorrow}")

    # 3. BOOKING -> AUTHORITATIVE TRANSACTION CREATION (Phase 0, 8.1)
    print("\n[PHASE 0 & 8.1] Booking Harvest Delivery Slot (2.5 Qt)...")
    booking_resp = client.post(
        "/api/v1/slots/reserve",
        json={
            "farmer_id": 1,
            "mandi_id": mandi_id,
            "slot_id": slot_id,
            "requested_qty_qt": 2.5,
        },
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert booking_resp.status_code in [200, 201], f"Booking failed: {booking_resp.text}"
    booking_data = booking_resp.json()
    txn_id = booking_data["transaction_id"]
    token_obj = booking_data["token"]
    signature = token_obj["signature"]
    print(f"  [PASS] Booking Confirmed! Authoritative Transaction ID: {txn_id}")
    print(f"  [PASS] Cryptographic HMAC-SHA256 Token Signature: {signature[:24]}...")

    # 4. GATE ENTRY VERIFICATION (Phase 8.2)
    print("\n[PHASE 4 & 8.2] Operator Gate Entry Check-in...")
    gate_checkin = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": 1,
            "mandi_id": mandi_id,
            "slot_id": slot_id,
            "quantity_qt": 2.5,
            "token_signature": signature,
        },
        headers={"Authorization": f"Bearer {role_tokens['OPERATOR']}"},
    )
    assert gate_checkin.status_code in [200, 201], f"Gate check-in failed: {gate_checkin.text}"
    gate_data = gate_checkin.json()
    assert gate_data["current_state"] == "GATE_ENTRY_VERIFIED"
    print(f"  [PASS] Gate verified: Transaction {txn_id} advanced to 'GATE_ENTRY_VERIFIED'")

    # 5. QUALITY ASSESSMENT & DCDQ INSERTION (Phase 4, 4.5)
    print("\n[PHASE 4 & 4.5] Inspector Assaying Moisture (11.5% <= 17.0%)...")
    quality_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 11.5,
        },
        headers={"Authorization": f"Bearer {role_tokens['INSPECTOR']}"},
    )
    assert quality_resp.status_code == 200, f"Quality assaying failed: {quality_resp.text}"
    quality_data = quality_resp.json()
    assert quality_data["current_state"] == "QUALITY_APPROVED"
    assert quality_data["queue_position"] is not None
    priority_score = quality_data["priority_score"]
    print(f"  [PASS] Quality Approved! State: {quality_data['current_state']}, DCDQ Score: {priority_score}, Queue Position: #{quality_data['queue_position']}")

    # 6. LIVE QUEUE MONITOR & DISPATCH (Phase 5)
    print("\n[PHASE 5] Live Queue Monitor & Dispatch to Weighbridge...")
    queue_resp = client.get(f"/api/v1/queue/{mandi_id}", headers={"Authorization": f"Bearer {role_tokens['SUPERVISOR']}"})
    assert queue_resp.status_code == 200
    queue_items = queue_resp.json()["items"]
    matched_q = [item for item in queue_items if item["transaction_id"] == txn_id]
    assert len(matched_q) == 1, f"Transaction {txn_id} not found in active live queue!"
    print(f"  [PASS] Transaction confirmed active in Live Queue: {matched_q[0]['transaction_id']} (Score: {matched_q[0]['priority_score']})")

    # Dispatch vehicle
    dispatch_resp = client.post(
        f"/api/v1/queue/{mandi_id}/dispatch",
        json={"strategy": "DCDQ_PRIORITY"},
        headers={"Authorization": f"Bearer {role_tokens['OPERATOR']}"},
    )
    assert dispatch_resp.status_code == 200, f"Dispatch failed: {dispatch_resp.text}"
    dispatch_data = dispatch_resp.json()
    print(f"  [PASS] Dispatched from Queue: {dispatch_data['transaction_id']} -> {dispatch_data['new_state']}")

    # 7. WEIGHBRIDGE TELEMETRY: GROSS & TARE (Phase 6)
    print("\n[PHASE 6] Weighbridge Scale Gross & Tare Weighment...")
    # Gross Capture (Loaded Truck = 85.0 Qt)
    gross_resp = client.post(
        "/api/v1/weighbridge/gross",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 85.0,
            "scale_id": "WB-SCALE-01",
        },
        headers={"Authorization": f"Bearer {role_tokens['OPERATOR']}"},
    )
    assert gross_resp.status_code == 200, f"Gross weighment failed: {gross_resp.text}"
    assert gross_resp.json()["current_state"] == "WEIGHED_GROSS"
    print(f"  [PASS] Gross weight recorded: 85.0 Qt -> State: WEIGHED_GROSS")

    # Tare Capture (Empty Truck = 35.0 Qt -> Net = 50.0 Qt)
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 35.0,
            "scale_id": "WB-SCALE-01",
        },
        headers={"Authorization": f"Bearer {role_tokens['OPERATOR']}"},
    )
    assert tare_resp.status_code == 200, f"Tare weighment failed: {tare_resp.text}"
    tare_data = tare_resp.json()
    assert tare_data["current_state"] == "WEIGHED_TARE"
    assert tare_data["net_weight_qt"] == 50.0
    print(f"  [PASS] Tare weight recorded: 35.0 Qt -> Authoritative Net Weight: {tare_data['net_weight_qt']} Qt -> State: WEIGHED_TARE")

    # 8. J-FORM INVOICE GENERATION (Phase 7)
    print("\n[PHASE 7] J-Form Joint-Sale Billing & Authoritative MSP Resolution...")
    billing_resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2275.0,
            "deductions_inr": 0.0,
            "inspector_notes": "Forensic E2E Test Suite Validation",
        },
        headers={"Authorization": f"Bearer {role_tokens['OPERATOR']}"},
    )
    assert billing_resp.status_code in [200, 201], f"Billing failed: {billing_resp.text}"
    bill_data = billing_resp.json()
    assert bill_data["current_state"] == "BILL_GENERATED"
    invoice_amount = bill_data["invoice_amount_inr"]
    expected_amount = 50.0 * 2275.0  # 113,750.00
    assert abs(invoice_amount - expected_amount) < 0.01, f"Invoice amount mismatch: got {invoice_amount}, expected {expected_amount}"
    print(f"  [PASS] Official J-Form #{bill_data['invoice_id']} Generated: ₹{invoice_amount:,.2f} -> State: BILL_GENERATED")

    # 9. DUAL-SIGNATURE CRYPTOGRAPHIC PAYOUT (Phase 9)
    print("\n[PHASE 9] Cryptographic Dual-Signature Staging & DBT Disbursement...")
    # Admin-only demo-signatures endpoint test
    non_admin_attempt = client.post(
        "/api/v1/payout/demo-signatures",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": invoice_amount,
            "inspector_id": 101,
            "operator_id": 202,
        },
        headers={"Authorization": f"Bearer {role_tokens['OPERATOR']}"},
    )
    assert non_admin_attempt.status_code == 403, f"Non-admin should be rejected with 403 from demo-signatures, got {non_admin_attempt.status_code}"
    print("  [PASS] Non-admin (OPERATOR) correctly blocked (HTTP 403) from /payout/demo-signatures")

    admin_sig_resp = client.post(
        "/api/v1/payout/demo-signatures",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": invoice_amount,
            "inspector_id": 101,
            "operator_id": 202,
        },
        headers={"Authorization": f"Bearer {role_tokens['ADMIN']}"},
    )
    assert admin_sig_resp.status_code == 200, f"Admin demo signatures failed: {admin_sig_resp.text}"
    sigs = admin_sig_resp.json()

    # Stage Dual-Signature Payout
    stage_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": invoice_amount,
            "inspector_id": 101,
            "operator_id": 202,
            "inspector_sig_hash": sigs["inspector_sig_hash"],
            "operator_sig_hash": sigs["operator_sig_hash"],
        },
        headers={"Authorization": f"Bearer {role_tokens['ADMIN']}"},
    )
    assert stage_resp.status_code == 200, f"Payout staging failed: {stage_resp.text}"
    payout_data = stage_resp.json()
    assert payout_data["current_state"] == "PAYMENT_SETTLED"
    block_hash = payout_data["payout_block_hash"]
    print(f"  [PASS] Dual-Signature Payout Settled! Block Hash: {block_hash}")

    # Simulate PFMS / NPCI Direct Rail
    mock_dbt = client.post(
        "/api/v1/mock/dbt-payout",
        json={
            "farmer_id": 1,
            "transaction_amount_inr": invoice_amount,
            "bank_ifsc": "SBIN0001042",
            "account_number_hash": "bank_hash_001",
        },
        headers={"Authorization": f"Bearer {role_tokens['ADMIN']}"},
    )
    assert mock_dbt.status_code == 200, f"Mock DBT failed: {mock_dbt.text}"
    dbt_data = mock_dbt.json()
    print(f"  [PASS] PFMS Direct Rail Settlement Confirmed: Ref #{dbt_data['payout_reference_id']}")

    # 10. AUTHORITATIVE BACKEND TRANSACTION GET ROUTE (Phase 0.1)
    print("\n[PHASE 0.1] Testing GET /api/v1/transactions/{transaction_id} RBAC...")
    txn_get_farmer = client.get(f"/api/v1/transactions/{txn_id}", headers={"Authorization": f"Bearer {farmer_token}"})
    assert txn_get_farmer.status_code == 200
    t_data = txn_get_farmer.json()
    assert t_data["transaction_id"] == txn_id
    assert t_data["current_state"] == "PAYMENT_SETTLED"
    assert t_data["net_weight_qt"] == 50.0
    print(f"  [PASS] Farmer resolved authoritative transaction in state '{t_data['current_state']}'")

    # Nonexistent transaction test
    bad_txn_resp = client.get("/api/v1/transactions/TXN-DEMO-NONEXISTENT", headers={"Authorization": f"Bearer {role_tokens['ADMIN']}"})
    assert bad_txn_resp.status_code == 404
    print("  [PASS] Nonexistent transaction correctly returns HTTP 404")

    print("\n" + "=" * 75)
    print(f"  ALL 10 FORENSIC WORKFLOW STAGES PASSED ON TRANSACTION: {txn_id}")
    print("=" * 75)
    return True

if __name__ == "__main__":
    success = run_e2e_forensic_suite()
    sys.exit(0 if success else 1)
