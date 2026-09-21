"""
Test Suite for AUD-003: Remove Unknown-Mobile Farmer Fallback.

Verifies:
1. Known farmer mobile -> OTP allowed (HTTP 200, status=SUCCESS, otp_demo=123456).
2. Unknown mobile -> rejected:
   - lookup_farmer_by_mobile returns found=False with NO fabricated identity data.
   - send-otp returns HTTP 404.
   - verify-otp returns HTTP 400/404 (no active challenge, no bypass).
3. Wrong OTP -> rejected with HTTP 400.
4. Reused OTP -> rejected with HTTP 400.
5. Expired OTP -> rejected with HTTP 400.
6. Role mismatch -> rejected with HTTP 400.
7. Farmer profile returned must correspond to exact mobile:
   - Farmer 1 mobile (9876543210) resolves to Ramesh Kumar (ID: 1).
   - Farmer 2 mobile (9876543211) resolves to Balwinder Singh (ID: 2).
   - No hardcoded Hindi farmer names or Mandi names.
"""

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.services.auth_service import ensure_default_operational_users
from backend.app.routers.auth import _otp_store


@pytest.fixture(autouse=True)
def clean_otp_store():
    _otp_store.clear()
    yield
    _otp_store.clear()


@pytest.fixture(autouse=True)
def seed_test_farmers(db_session: Session):
    ensure_default_operational_users(db_session)
    mandi1 = Mandi(
        mandi_id=1,
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    mandi2 = Mandi(
        mandi_id=2,
        name="Karnal Grain Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=15000.0,
        active_weighbridges=4,
        is_operational=True
    )
    farmer1 = Farmer(
        farmer_id=1,
        name="Ramesh Kumar",
        aadhaar_hash="aadhaar_aud003_01",
        mobile_number="9876543210",
        bank_account_hash="bank_aud003_01",
        ifsc_code="SBIN0001040",
        land_area_hectares=12.5,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=600.0
    )
    farmer2 = Farmer(
        farmer_id=2,
        name="Balwinder Singh",
        aadhaar_hash="aadhaar_aud003_02",
        mobile_number="9876543211",
        bank_account_hash="bank_aud003_02",
        ifsc_code="SBIN0001042",
        land_area_hectares=8.0,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=350.0
    )
    db_session.add_all([mandi1, mandi2, farmer1, farmer2])
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Known Farmer Mobile -> OTP Allowed
# ------------------------------------------------------------------------------
def test_1_known_farmer_mobile_otp_allowed(client: TestClient):
    """Known farmer mobile is allowed to request and verify OTP."""
    mobile = "9876543210"
    res_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})
    assert res_send.status_code == 200
    send_data = res_send.json()
    assert send_data["status"] == "SUCCESS"
    assert send_data["otp_demo"] == "123456"
    assert send_data["linked_pass"] is not None
    assert send_data["linked_pass"]["farmer_id"] == 1
    assert send_data["linked_pass"]["name"] == "Ramesh Kumar"

    res_verify = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    assert verify_data["role"] == "FARMER"
    assert verify_data["farmer_id"] == 1
    assert "Ramesh Kumar" in verify_data["full_name"]


# ------------------------------------------------------------------------------
# 2. Unknown Mobile -> Rejected
# ------------------------------------------------------------------------------
def test_2_unknown_mobile_rejected(client: TestClient):
    """Unknown mobile number is rejected at lookup, send-otp, and verify-otp."""
    unknown_mobile = "9999999999"

    # A. Lookup returns found=False with NO fabricated identity data
    res_lookup = client.get(f"/api/v1/auth/farmer-by-mobile/{unknown_mobile}")
    assert res_lookup.status_code == 200
    lookup_data = res_lookup.json()
    assert lookup_data["found"] is False
    assert lookup_data["farmer_id"] is None
    assert lookup_data["name"] is None
    assert lookup_data["name_hi"] is None
    assert lookup_data["mandi_pass_id"] is None
    assert lookup_data["land_area_hectares"] is None
    assert lookup_data["registered_crop_type"] is None
    assert lookup_data["mandi_name"] is None

    # B. send-otp rejects unknown mobile with HTTP 404
    res_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": unknown_mobile, "role": "FARMER"})
    assert res_send.status_code == 404
    assert "not registered" in res_send.json()["detail"].lower()

    # C. verify-otp rejects unknown mobile without challenge (HTTP 400)
    res_verify = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": unknown_mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_verify.status_code == 400
    assert "no active otp challenge" in res_verify.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 3. Wrong OTP -> Rejected
# ------------------------------------------------------------------------------
def test_3_wrong_otp_rejected(client: TestClient):
    """Entering an incorrect OTP is rejected with HTTP 400."""
    mobile = "9876543210"
    res_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})
    assert res_send.status_code == 200

    res_wrong = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "999999",
        "role": "FARMER"
    })
    assert res_wrong.status_code == 400
    assert "invalid otp" in res_wrong.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 4. Reused OTP -> Rejected
# ------------------------------------------------------------------------------
def test_4_reused_otp_rejected(client: TestClient):
    """Once an OTP challenge is consumed, replaying the same OTP is rejected with HTTP 400."""
    mobile = "9876543210"
    client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})

    res_1 = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_1.status_code == 200

    res_2 = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_2.status_code == 400
    assert "already been used" in res_2.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 5. Expired OTP -> Rejected
# ------------------------------------------------------------------------------
def test_5_expired_otp_rejected(client: TestClient, monkeypatch):
    """An OTP past its TTL (300 seconds) is rejected with HTTP 400."""
    mobile = "9876543210"
    client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})

    # Advance time by 350 seconds
    orig_time = time.time
    monkeypatch.setattr(time, "time", lambda: orig_time() + 350)

    res = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 6. Role Mismatch -> Rejected
# ------------------------------------------------------------------------------
def test_6_role_mismatch_rejected(client: TestClient):
    """An OTP requested for FARMER cannot be verified as TRADER or OFFICIAL."""
    mobile = "9876543210"
    res_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})
    assert res_send.status_code == 200

    res_mismatch = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "TRADER"
    })
    assert res_mismatch.status_code == 400
    assert "role mismatch" in res_mismatch.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 7. Farmer Profile Returned Must Correspond to Exact Mobile
# ------------------------------------------------------------------------------
def test_7_farmer_profile_corresponds_to_exact_mobile(client: TestClient):
    """Each mobile number resolves strictly to its own authoritative database record."""
    # Farmer 1
    r1 = client.get("/api/v1/auth/farmer-by-mobile/9876543210")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["found"] is True
    assert d1["farmer_id"] == 1
    assert d1["name"] == "Ramesh Kumar"
    assert d1["mobile_number"] == "9876543210"
    assert d1["name_hi"] is None
    assert d1["mandi_pass_id"] == "00001"

    # Farmer 2
    r2 = client.get("/api/v1/auth/farmer-by-mobile/9876543211")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["found"] is True
    assert d2["farmer_id"] == 2
    assert d2["name"] == "Balwinder Singh"
    assert d2["mobile_number"] == "9876543211"
    assert d2["name_hi"] is None
    assert d2["mandi_pass_id"] == "00002"

    # Fabricated mobile does NOT resolve to either
    r_fab = client.get("/api/v1/auth/farmer-by-mobile/9999999999")
    assert r_fab.status_code == 200
    d_fab = r_fab.json()
    assert d_fab["found"] is False
    assert d_fab["farmer_id"] is None
    assert d_fab["name"] is None
