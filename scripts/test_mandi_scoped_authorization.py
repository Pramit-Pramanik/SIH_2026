"""
scripts/test_mandi_scoped_authorization.py

Comprehensive test suite verifying AUD-001: Enforce Mandi-Scoped Authorization.

Validates:
1. Mandi-1 OPERATOR -> Mandi-1 transaction = allowed
2. Mandi-1 OPERATOR -> Mandi-2 transaction = 403 Forbidden
3. Mandi-1 INSPECTOR -> Mandi-2 quality = 403 Forbidden
4. Mandi-1 SUPERVISOR -> Mandi-2 transaction = 403 Forbidden
5. ADMIN -> Mandi-2 transaction = allowed
6. FARMER 1 -> Farmer 2 transaction = 403 Forbidden

Repeats tests across all stations:
- Gate check-in & inspection
- Quality assessment & inspection
- Queue dispatch & rerank
- Weighbridge gross weight
- Weighbridge tare weight
- Unified weighbridge capture
- Weighbridge inspection
- Billing invoice generation & inspection
- Dual-signature payout staging
- Transaction authoritative inspection
- Slot reservation cancellation
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import date, datetime, timezone

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

BASE_URL = "http://127.0.0.1:8000/api/v1"


def make_request(method, endpoint, payload=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


def login(username, password):
    status, body = make_request("POST", "/auth/login", {"username": username, "password": password})
    if status != 200 or "access_token" not in body:
        raise RuntimeError(f"Login failed for {username}: {status} {body}")
    return body["access_token"]


def main():
    print("=" * 70)
    print("MANDIQ AUD-001: MANDI-SCOPED AUTHORIZATION TEST SUITE")
    print("=" * 70)

    sys.stdout.reconfigure(encoding='utf-8')
    # 1. Authenticate users
    print("\n[STEP 1] Authenticating Test Personas...")
    admin_token = login("admin", "Admin@MandiQ2026")
    supervisor_m1_token = login("supervisor", "Supervisor@MandiQ2026")
    inspector_m1_token = login("inspector", "Inspector@MandiQ2026")
    operator_m1_token = login("operator", "Operator@MandiQ2026")
    farmer1_token = login("farmer", "Farmer@MandiQ2026")

    print("  [OK] ADMIN logged in (Global scope)")
    print("  [OK] SUPERVISOR logged in (Mandi 1 scope)")
    print("  [OK] INSPECTOR logged in (Mandi 1 scope)")
    print("  [OK] OPERATOR logged in (Mandi 1 scope)")
    print("  [OK] FARMER 1 logged in (Farmer 1 scope)")

    # 2. Setup test transactions directly in DB
    from backend.app.dependencies.get_db import SessionLocal
    from backend.app.models.log import ProcurementLog
    from backend.app.core.security import generate_booking_signature

    db = SessionLocal()
    today_str = date.today().isoformat()

    # Create / ensure a clean test transaction for Mandi 1 (Farmer 1)
    txn_m1_id = "TXN-AUD-M1-F1-001"
    db.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_m1_id).delete()
    sig_m1 = generate_booking_signature(
        farmer_id=1, mandi_id=1, slot_id=1, quantity_qt=10.0
    )
    log_m1 = ProcurementLog(
        transaction_id=txn_m1_id,
        farmer_id=1,
        mandi_id=1,
        slot_id=1,
        scheduled_date=date.today(),
        crop_type="Wheat (HD-2967)",
        net_weight_qt=10.0,
        current_state="SLOT_BOOKED",
        token_signature=sig_m1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(log_m1)

    # Create / ensure a clean test transaction for Mandi 2 (Farmer 2)
    txn_m2_id = "TXN-AUD-M2-F2-002"
    db.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_m2_id).delete()
    sig_m2 = generate_booking_signature(
        farmer_id=2, mandi_id=2, slot_id=2, quantity_qt=15.0
    )
    log_m2 = ProcurementLog(
        transaction_id=txn_m2_id,
        farmer_id=2,
        mandi_id=2,
        slot_id=2,
        scheduled_date=date.today(),
        crop_type="Wheat (HD-2967)",
        net_weight_qt=15.0,
        current_state="SLOT_BOOKED",
        token_signature=sig_m2,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(log_m2)
    db.commit()
    db.close()

    print(f"\n[STEP 2] Initialized Test Fixtures:")
    print(f"  - Mandi 1 Transaction: {txn_m1_id} (Mandi 1, Farmer 1, State: SLOT_BOOKED)")
    print(f"  - Mandi 2 Transaction: {txn_m2_id} (Mandi 2, Farmer 2, State: SLOT_BOOKED)")

    results = []

    def assert_test(name, expected_status, actual_status, body):
        passed = actual_status == expected_status
        results.append((name, expected_status, actual_status, passed, body))
        symbol = "[PASS]" if passed else "[FAIL]"
        detail = body.get("detail", "") if isinstance(body, dict) else str(body)
        print(f"  {symbol} {name} -> Expected {expected_status}, Got {actual_status} ({detail[:60]}...)")
        if not passed:
            print(f"       ERROR BODY: {body}")

    # =========================================================================
    # 3. GATE STATION TESTS
    # =========================================================================
    print("\n[TEST GROUP 1] Gate Check-in & Gate Inspection")

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Transaction
    st, b = make_request("POST", "/gate/check-in", {
        "transaction_id": txn_m2_id,
        "farmer_id": 2,
        "mandi_id": 2,
        "slot_id": 2,
        "quantity_qt": 15.0,
        "token_signature": sig_m2
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Gate Check-in", 403, st, b)

    # Negative: Mandi 1 INSPECTOR -> Mandi 2 Gate Inspection
    st, b = make_request("GET", f"/gate/verify/{txn_m2_id}", token=inspector_m1_token)
    assert_test("Mandi-1 INSPECTOR -> Mandi-2 Gate Inspection", 403, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Gate Check-in
    st, b = make_request("POST", "/gate/check-in", {
        "transaction_id": txn_m1_id,
        "farmer_id": 1,
        "mandi_id": 1,
        "slot_id": 1,
        "quantity_qt": 10.0,
        "token_signature": sig_m1
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Gate Check-in", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Gate Check-in
    st, b = make_request("POST", "/gate/check-in", {
        "transaction_id": txn_m2_id,
        "farmer_id": 2,
        "mandi_id": 2,
        "slot_id": 2,
        "quantity_qt": 15.0,
        "token_signature": sig_m2
    }, token=admin_token)
    assert_test("ADMIN -> Mandi-2 Gate Check-in (Cross-Mandi Allowed)", 200, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Gate Inspection
    st, b = make_request("GET", f"/gate/verify/{txn_m1_id}", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Gate Inspection", 200, st, b)

    # =========================================================================
    # 4. QUALITY ASSESSMENT TESTS
    # =========================================================================
    print("\n[TEST GROUP 2] Quality Assessment & Inspection")

    # Negative: Mandi 1 INSPECTOR -> Mandi 2 Quality Assessment
    st, b = make_request("POST", "/quality/assess", {
        "transaction_id": txn_m2_id,
        "crop_moisture_pct": 13.5
    }, token=inspector_m1_token)
    assert_test("Mandi-1 INSPECTOR -> Mandi-2 Quality Assess", 403, st, b)

    # Negative: Mandi 1 SUPERVISOR -> Mandi 2 Quality Assessment
    st, b = make_request("POST", "/quality/assess", {
        "transaction_id": txn_m2_id,
        "crop_moisture_pct": 13.5
    }, token=supervisor_m1_token)
    assert_test("Mandi-1 SUPERVISOR -> Mandi-2 Quality Assess", 403, st, b)

    # Negative: Mandi 1 INSPECTOR -> Mandi 2 Quality Inspection
    st, b = make_request("GET", f"/quality/{txn_m2_id}", token=inspector_m1_token)
    assert_test("Mandi-1 INSPECTOR -> Mandi-2 Quality Inspection", 403, st, b)

    # Positive: Mandi 1 INSPECTOR -> Mandi 1 Quality Assessment
    st, b = make_request("POST", "/quality/assess", {
        "transaction_id": txn_m1_id,
        "crop_moisture_pct": 13.5
    }, token=inspector_m1_token)
    assert_test("Mandi-1 INSPECTOR -> Mandi-1 Quality Assess", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Quality Assessment
    st, b = make_request("POST", "/quality/assess", {
        "transaction_id": txn_m2_id,
        "crop_moisture_pct": 13.5
    }, token=admin_token)
    assert_test("ADMIN -> Mandi-2 Quality Assess (Allowed)", 200, st, b)

    # =========================================================================
    # 5. QUEUE DISPATCH & RERANK TESTS
    # =========================================================================
    print("\n[TEST GROUP 3] Queue Dispatch & Rerank")

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Queue Dispatch
    st, b = make_request("POST", "/queue/2/dispatch", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Queue Dispatch", 403, st, b)

    # Negative: Mandi 1 SUPERVISOR -> Mandi 2 Queue Dispatch
    st, b = make_request("POST", "/queue/2/dispatch", token=supervisor_m1_token)
    assert_test("Mandi-1 SUPERVISOR -> Mandi-2 Queue Dispatch", 403, st, b)

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Queue Rerank
    st, b = make_request("POST", "/queue/2/rerank", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Queue Rerank", 403, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Queue Dispatch
    st, b = make_request("POST", "/queue/1/dispatch", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Queue Dispatch", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Queue Dispatch
    st, b = make_request("POST", "/queue/2/dispatch", token=admin_token)
    assert_test("ADMIN -> Mandi-2 Queue Dispatch (Allowed)", 200, st, b)

    # =========================================================================
    # 6. WEIGHBRIDGE TELEMETRY TESTS
    # =========================================================================
    print("\n[TEST GROUP 4] Weighbridge Gross, Tare, Unified & Inspection")

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Weighbridge Gross
    st, b = make_request("POST", "/weighbridge/gross", {
        "transaction_id": txn_m2_id,
        "gross_weight_qt": 55.0
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Weighbridge Gross", 403, st, b)

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Weighbridge Tare
    st, b = make_request("POST", "/weighbridge/tare", {
        "transaction_id": txn_m2_id,
        "tare_weight_qt": 40.0
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Weighbridge Tare", 403, st, b)

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Unified Weighment
    st, b = make_request("POST", "/weighbridge/capture", {
        "transaction_id": txn_m2_id,
        "gross_weight_qt": 55.0,
        "tare_weight_qt": 40.0
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Unified Weighment", 403, st, b)

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Weighbridge Inspection
    st, b = make_request("GET", f"/weighbridge/{txn_m2_id}", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Weighbridge Inspection", 403, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Weighbridge Gross
    st, b = make_request("POST", "/weighbridge/gross", {
        "transaction_id": txn_m1_id,
        "gross_weight_qt": 50.0
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Weighbridge Gross", 200, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Weighbridge Tare
    st, b = make_request("POST", "/weighbridge/tare", {
        "transaction_id": txn_m1_id,
        "tare_weight_qt": 40.0
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Weighbridge Tare", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Unified Weighment
    st, b = make_request("POST", "/weighbridge/capture", {
        "transaction_id": txn_m2_id,
        "gross_weight_qt": 55.0,
        "tare_weight_qt": 40.0
    }, token=admin_token)
    assert_test("ADMIN -> Mandi-2 Unified Weighment (Allowed)", 200, st, b)

    # =========================================================================
    # 7. BILLING & INVOICE TESTS
    # =========================================================================
    print("\n[TEST GROUP 5] J-Form Billing & Inspection")

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Billing Generate
    st, b = make_request("POST", "/billing/generate", {
        "transaction_id": txn_m2_id
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Billing Generate", 403, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Billing Generate
    st, b = make_request("POST", "/billing/generate", {
        "transaction_id": txn_m1_id
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Billing Generate", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Billing Generate
    st, b = make_request("POST", "/billing/generate", {
        "transaction_id": txn_m2_id
    }, token=admin_token)
    assert_test("ADMIN -> Mandi-2 Billing Generate (Allowed)", 200, st, b)

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Billing Inspection
    st, b = make_request("GET", f"/billing/{txn_m2_id}", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Billing Inspection", 403, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Billing Inspection
    st, b = make_request("GET", f"/billing/{txn_m1_id}", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Billing Inspection", 200, st, b)

    # =========================================================================
    # 8. PAYOUT DUAL-SIGNATURE TESTS
    # =========================================================================
    print("\n[TEST GROUP 6] Dual-Signature DBT Payout Staging")

    # Generate demo signatures for both
    st, sigs_m1 = make_request("POST", "/payout/demo-signatures", {
        "transaction_id": txn_m1_id,
        "invoice_amount_inr": 22750.0,
        "inspector_id": 2,
        "operator_id": 3
    }, token=admin_token)

    st, sigs_m2 = make_request("POST", "/payout/demo-signatures", {
        "transaction_id": txn_m2_id,
        "invoice_amount_inr": 34125.0,
        "inspector_id": 2,
        "operator_id": 3
    }, token=admin_token)

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Payout Staging
    st, b = make_request("POST", "/payout/stage", {
        "transaction_id": txn_m2_id,
        "invoice_amount_inr": 34125.0,
        "inspector_id": 2,
        "inspector_sig_hash": sigs_m2["inspector_sig_hash"],
        "operator_id": 3,
        "operator_sig_hash": sigs_m2["operator_sig_hash"]
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Payout Stage", 403, st, b)

    # Positive: Mandi 1 OPERATOR -> Mandi 1 Payout Staging
    st, b = make_request("POST", "/payout/stage", {
        "transaction_id": txn_m1_id,
        "invoice_amount_inr": 22750.0,
        "inspector_id": 2,
        "inspector_sig_hash": sigs_m1["inspector_sig_hash"],
        "operator_id": 3,
        "operator_sig_hash": sigs_m1["operator_sig_hash"]
    }, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-1 Payout Stage", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Payout Staging
    st, b = make_request("POST", "/payout/stage", {
        "transaction_id": txn_m2_id,
        "invoice_amount_inr": 34125.0,
        "inspector_id": 2,
        "inspector_sig_hash": sigs_m2["inspector_sig_hash"],
        "operator_id": 3,
        "operator_sig_hash": sigs_m2["operator_sig_hash"]
    }, token=admin_token)
    assert_test("ADMIN -> Mandi-2 Payout Stage (Allowed)", 200, st, b)

    # =========================================================================
    # 9. AUTHORITATIVE TRANSACTION LEDGER INSPECTION
    # =========================================================================
    print("\n[TEST GROUP 7] Authoritative Transaction Inspection & Scoping")

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Transaction
    st, b = make_request("GET", f"/transactions/{txn_m2_id}", token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Ledger Inspection", 403, st, b)

    # Negative: Mandi 1 INSPECTOR -> Mandi 2 Transaction
    st, b = make_request("GET", f"/transactions/{txn_m2_id}", token=inspector_m1_token)
    assert_test("Mandi-1 INSPECTOR -> Mandi-2 Ledger Inspection", 403, st, b)

    # Negative: Mandi 1 SUPERVISOR -> Mandi 2 Transaction
    st, b = make_request("GET", f"/transactions/{txn_m2_id}", token=supervisor_m1_token)
    assert_test("Mandi-1 SUPERVISOR -> Mandi-2 Ledger Inspection", 403, st, b)

    # Negative: FARMER 1 -> Mandi 2 Transaction (Farmer 2)
    st, b = make_request("GET", f"/transactions/{txn_m2_id}", token=farmer1_token)
    assert_test("FARMER 1 -> Farmer 2 Ledger Inspection", 403, st, b)

    # Positive: FARMER 1 -> Mandi 1 Transaction (Farmer 1)
    st, b = make_request("GET", f"/transactions/{txn_m1_id}", token=farmer1_token)
    assert_test("FARMER 1 -> Farmer 1 Ledger Inspection", 200, st, b)

    # Positive: ADMIN -> Mandi 2 Transaction
    st, b = make_request("GET", f"/transactions/{txn_m2_id}", token=admin_token)
    assert_test("ADMIN -> Mandi-2 Ledger Inspection (Allowed)", 200, st, b)

    # =========================================================================
    # 10. SLOT RESERVATION CANCELLATION
    # =========================================================================
    print("\n[TEST GROUP 8] Slot Cancellation Scoping")

    # Create temporary booked transactions for cancellation testing
    db = SessionLocal()
    txn_cancel_m1 = "TXN-CANCEL-M1-F1"
    txn_cancel_m2 = "TXN-CANCEL-M2-F2"
    db.query(ProcurementLog).filter(ProcurementLog.transaction_id.in_([txn_cancel_m1, txn_cancel_m2])).delete()
    sig_c1 = generate_booking_signature(1, 1, 1, 5.0)
    sig_c2 = generate_booking_signature(2, 2, 2, 5.0)
    db.add(ProcurementLog(
        transaction_id=txn_cancel_m1, farmer_id=1, mandi_id=1, slot_id=1,
        scheduled_date=date.today(), current_state="SLOT_BOOKED", net_weight_qt=5.0,
        token_signature=sig_c1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    ))
    db.add(ProcurementLog(
        transaction_id=txn_cancel_m2, farmer_id=2, mandi_id=2, slot_id=2,
        scheduled_date=date.today(), current_state="SLOT_BOOKED", net_weight_qt=5.0,
        token_signature=sig_c2, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    ))
    db.commit()
    db.close()

    # Negative: Mandi 1 OPERATOR -> Mandi 2 Cancel
    st, b = make_request("POST", "/slots/cancel", {"transaction_id": txn_cancel_m2}, token=operator_m1_token)
    assert_test("Mandi-1 OPERATOR -> Mandi-2 Slot Cancel", 403, st, b)

    # Negative: FARMER 1 -> Farmer 2 Cancel
    st, b = make_request("POST", "/slots/cancel", {"transaction_id": txn_cancel_m2}, token=farmer1_token)
    assert_test("FARMER 1 -> Farmer 2 Slot Cancel", 403, st, b)

    # Positive: FARMER 1 -> Farmer 1 Cancel
    st, b = make_request("POST", "/slots/cancel", {"transaction_id": txn_cancel_m1}, token=farmer1_token)
    assert_test("FARMER 1 -> Farmer 1 Slot Cancel", 200, st, b)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r[3])
    failed = total - passed

    print("\n" + "=" * 70)
    print(f"TEST RUN COMPLETE: {passed}/{total} PASSED ({failed} FAILED)")
    print("=" * 70)

    if failed > 0:
        print("\nFailed Tests:")
        for r in results:
            if not r[3]:
                print(f"  - {r[0]}: Expected {r[1]}, got {r[2]}")
        sys.exit(1)
    else:
        print("\nALL CROSS-MANDI AUTHORIZATION AND SCOPING INVARIANTS VERIFIED!")
        sys.exit(0)


if __name__ == "__main__":
    main()
