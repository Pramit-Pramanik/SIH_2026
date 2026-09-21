"""
MandiQ AUD-003: Remove Unknown-Mobile Farmer Fallback — Forensic Verification Script.
Directly exercises backend FastAPI endpoints to verify:
1. Known farmer mobile -> OTP allowed (HTTP 200, status=SUCCESS, otp_demo=123456)
2. Unknown mobile -> rejected:
   - lookup_farmer_by_mobile returns found=False with NO fabricated identity data
   - send-otp returns HTTP 404
   - verify-otp returns HTTP 400
3. Wrong OTP -> rejected (HTTP 400)
4. Reused OTP -> rejected (HTTP 400)
5. Expired OTP -> rejected (HTTP 400)
6. Role mismatch -> rejected (HTTP 400)
7. Farmer profile returned must correspond to exact mobile
8. No hardcoded Hindi farmer names or Mandi names returned
"""

import time
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.services.auth_service import ensure_default_operational_users
from backend.app.routers.auth import _otp_store


def main():
    print("=" * 80)
    print("AUD-003 FORENSIC VERIFICATION: REMOVE UNKNOWN-MOBILE FARMER FALLBACK")
    print("=" * 80)

    db = SessionLocal()
    client = TestClient(app)
    _otp_store.clear()

    try:
        ensure_default_operational_users(db)

        # 1. Ensure test farmers exist in database
        farmer1 = db.query(Farmer).filter_by(mobile_number="9876543210").first()
        if not farmer1:
            farmer1 = Farmer(
                name="Ramesh Kumar",
                aadhaar_hash="aadhaar_hash_aud003_s1",
                mobile_number="9876543210",
                bank_account_hash="bank_hash_aud003_s1",
                ifsc_code="SBIN0001040",
                land_area_hectares=12.5,
                registered_crop_type="Wheat (HD-2967)",
                production_ceiling_qt=600.0
            )
            db.add(farmer1)

        farmer2 = db.query(Farmer).filter_by(mobile_number="9876543211").first()
        if not farmer2:
            farmer2 = Farmer(
                name="Balwinder Singh",
                aadhaar_hash="aadhaar_hash_aud003_s2",
                mobile_number="9876543211",
                bank_account_hash="bank_hash_aud003_s2",
                ifsc_code="SBIN0001042",
                land_area_hectares=8.0,
                registered_crop_type="Wheat (HD-2967)",
                production_ceiling_qt=350.0
            )
            db.add(farmer2)

        db.commit()
        db.refresh(farmer1)
        db.refresh(farmer2)

        # ----------------------------------------------------------------------
        # TEST 1: Known farmer mobile -> OTP allowed
        # ----------------------------------------------------------------------
        print("\n[TEST 1] Known farmer mobile (9876543210) -> OTP allowed...")
        r1_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": "9876543210", "role": "FARMER"})
        assert r1_send.status_code == 200, f"Expected 200, got {r1_send.status_code}: {r1_send.text}"
        d1_send = r1_send.json()
        assert d1_send["status"] == "SUCCESS"
        assert d1_send["otp_demo"] == "123456"
        assert d1_send["linked_pass"]["farmer_id"] == farmer1.farmer_id

        r1_verify = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9876543210",
            "otp": "123456",
            "role": "FARMER"
        })
        assert r1_verify.status_code == 200, f"Expected 200, got {r1_verify.status_code}: {r1_verify.text}"
        d1_verify = r1_verify.json()
        assert d1_verify["role"] == "FARMER"
        assert d1_verify["farmer_id"] == farmer1.farmer_id
        print(f"  --> PASS: OTP allowed & verified. Token issued for Farmer #{farmer1.farmer_id} ({d1_verify['full_name']}).")

        # ----------------------------------------------------------------------
        # TEST 2: Unknown mobile -> Rejected
        # ----------------------------------------------------------------------
        print("\n[TEST 2] Unknown mobile (9999999999) -> Rejected...")
        # A. Identity lookup
        r2_lookup = client.get("/api/v1/auth/farmer-by-mobile/9999999999")
        assert r2_lookup.status_code == 200
        d2_lookup = r2_lookup.json()
        assert d2_lookup["found"] is False, f"Expected found=False, got {d2_lookup}"
        assert d2_lookup["farmer_id"] is None
        assert d2_lookup["name"] is None
        assert d2_lookup["mandi_pass_id"] is None
        assert d2_lookup["land_area_hectares"] is None
        assert d2_lookup["registered_crop_type"] is None
        assert d2_lookup["mandi_name"] is None
        print("  --> PASS: /farmer-by-mobile/9999999999 returned found=False with ZERO fabricated identity fields.")

        # B. send-otp
        r2_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": "9999999999", "role": "FARMER"})
        assert r2_send.status_code == 404, f"Expected 404, got {r2_send.status_code}: {r2_send.text}"
        print(f"  --> PASS: /send-otp for 9999999999 rejected with HTTP 404: {r2_send.json()['detail']}")

        # C. verify-otp without challenge
        r2_verify = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9999999999",
            "otp": "123456",
            "role": "FARMER"
        })
        assert r2_verify.status_code == 400, f"Expected 400, got {r2_verify.status_code}: {r2_verify.text}"
        print(f"  --> PASS: /verify-otp for 9999999999 rejected with HTTP 400: {r2_verify.json()['detail']}")

        # ----------------------------------------------------------------------
        # TEST 3: Wrong OTP -> Rejected
        # ----------------------------------------------------------------------
        print("\n[TEST 3] Wrong OTP (999999) -> Rejected...")
        client.post("/api/v1/auth/send-otp", json={"mobile_number": "9876543210", "role": "FARMER"})
        r3_wrong = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9876543210",
            "otp": "999999",
            "role": "FARMER"
        })
        assert r3_wrong.status_code == 400
        assert "invalid otp" in r3_wrong.json()["detail"].lower()
        print(f"  --> PASS: Wrong OTP rejected with HTTP 400: {r3_wrong.json()['detail']}")

        # ----------------------------------------------------------------------
        # TEST 4: Reused OTP -> Rejected
        # ----------------------------------------------------------------------
        print("\n[TEST 4] Reused OTP -> Rejected...")
        client.post("/api/v1/auth/send-otp", json={"mobile_number": "9876543210", "role": "FARMER"})
        r4_first = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9876543210",
            "otp": "123456",
            "role": "FARMER"
        })
        assert r4_first.status_code == 200

        r4_reused = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9876543210",
            "otp": "123456",
            "role": "FARMER"
        })
        assert r4_reused.status_code == 400
        assert "already been used" in r4_reused.json()["detail"].lower()
        print(f"  --> PASS: Reused OTP rejected with HTTP 400: {r4_reused.json()['detail']}")

        # ----------------------------------------------------------------------
        # TEST 5: Expired OTP -> Rejected
        # ----------------------------------------------------------------------
        print("\n[TEST 5] Expired OTP -> Rejected...")
        client.post("/api/v1/auth/send-otp", json={"mobile_number": "9876543210", "role": "FARMER"})
        # Force expiration in store
        with _otp_store._lock:
            if "9876543210" in _otp_store._challenges:
                _otp_store._challenges["9876543210"]["expires_at"] = time.time() - 10

        r5_expired = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9876543210",
            "otp": "123456",
            "role": "FARMER"
        })
        assert r5_expired.status_code == 400
        assert "expired" in r5_expired.json()["detail"].lower()
        print(f"  --> PASS: Expired OTP rejected with HTTP 400: {r5_expired.json()['detail']}")

        # ----------------------------------------------------------------------
        # TEST 6: Role Mismatch -> Rejected
        # ----------------------------------------------------------------------
        print("\n[TEST 6] Role mismatch (FARMER requested -> TRADER verify) -> Rejected...")
        client.post("/api/v1/auth/send-otp", json={"mobile_number": "9876543210", "role": "FARMER"})
        r6_mismatch = client.post("/api/v1/auth/verify-otp", json={
            "mobile_number": "9876543210",
            "otp": "123456",
            "role": "TRADER"
        })
        assert r6_mismatch.status_code == 400
        assert "role mismatch" in r6_mismatch.json()["detail"].lower()
        print(f"  --> PASS: Role mismatch rejected with HTTP 400: {r6_mismatch.json()['detail']}")

        # ----------------------------------------------------------------------
        # TEST 7: Farmer profile returned corresponds to exact mobile
        # ----------------------------------------------------------------------
        print("\n[TEST 7] Farmer profile returned corresponds to exact mobile...")
        f1_res = client.get("/api/v1/auth/farmer-by-mobile/9876543210").json()
        assert f1_res["found"] is True
        assert f1_res["farmer_id"] == farmer1.farmer_id
        assert f1_res["name"] == "Ramesh Kumar"
        assert f1_res["name_hi"] is None
        assert f1_res["mandi_pass_id"] == f"{farmer1.farmer_id:05d}"

        f2_res = client.get("/api/v1/auth/farmer-by-mobile/9876543211").json()
        assert f2_res["found"] is True
        assert f2_res["farmer_id"] == farmer2.farmer_id
        assert f2_res["name"] == "Balwinder Singh"
        assert f2_res["name_hi"] is None
        assert f2_res["mandi_pass_id"] == f"{farmer2.farmer_id:05d}"
        print("  --> PASS: Mobile 9876543210 -> Ramesh Kumar, Mobile 9876543211 -> Balwinder Singh strictly isolated.")

        # ----------------------------------------------------------------------
        # TEST 8: Zero hardcoded Hindi names or fallback Mandi names
        # ----------------------------------------------------------------------
        print("\n[TEST 8] Checking zero hardcoded Hindi strings in identity lookup...")
        assert f1_res.get("name_hi") is None
        assert f2_res.get("name_hi") is None
        assert "Khanna" not in str(f1_res.get("mandi_name", ""))
        print("  --> PASS: Identity lookup returns canonical DB values without hardcoded Hindi names or hardcoded Khanna.")

        print("\n" + "=" * 80)
        print("ALL AUD-003 TEST SCENARIOS PASSED SUCCESSFULLY!")
        print("ACCEPTANCE CRITERION MET: No arbitrary phone number can obtain a valid FARMER identity.")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()
