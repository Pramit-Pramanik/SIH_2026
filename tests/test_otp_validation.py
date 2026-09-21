"""
Test Suite for Mobile OTP Validation (P2-01).
Verifies:
1. Valid demo OTP '123456' is accepted in development/demo mode and returns JWT.
2. Short/malformed OTP (e.g. '1234') is rejected with 400 Bad Request.
3. Incorrect 6-digit OTP (e.g. '999999') is rejected with 400 Bad Request.
4. Expired OTP challenge is rejected with 400 Bad Request.
5. Verifying OTP for a mobile number with no active challenge is rejected with 400.
6. Reused OTP (verifying a second time) is rejected with 400 Bad Request.
"""
import time
import pytest
from fastapi.testclient import TestClient
from backend.app.routers.auth import _otp_store


@pytest.fixture(autouse=True)
def clear_otp_store():
    _otp_store.clear()
    yield
    _otp_store.clear()


def test_otp_happy_path_demo_mode(client: TestClient):
    """Verifies that requesting OTP and entering demo '123456' succeeds and returns JWT."""
    mobile = "9876543210"
    # 1. Request OTP
    res_send = client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})
    assert res_send.status_code == 200
    data = res_send.json()
    assert data["status"] == "SUCCESS"
    assert data["otp_demo"] == "123456"

    # 2. Verify with correct OTP
    res_verify = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_verify.status_code == 200
    token_data = res_verify.json()
    assert "access_token" in token_data
    assert token_data["role"] == "FARMER"


def test_otp_rejected_when_wrong_code(client: TestClient):
    """Verifies that incorrect OTPs ('1234' and '999999') are rejected with 400."""
    mobile = "9876543210"
    client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})

    # Test 1234
    res_1234 = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "1234",
        "role": "FARMER"
    })
    assert res_1234.status_code == 400
    assert "invalid otp" in res_1234.json()["detail"].lower()

    # Test 999999
    res_999999 = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "999999",
        "role": "FARMER"
    })
    assert res_999999.status_code == 400
    assert "invalid otp" in res_999999.json()["detail"].lower()


def test_otp_rejected_when_no_challenge_or_wrong_mobile(client: TestClient):
    """Verifies that verifying without requesting OTP or with different mobile returns 400."""
    res = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": "9999900000",
        "otp": "123456",
        "role": "FARMER"
    })
    assert res.status_code == 400
    assert "no active otp challenge" in res.json()["detail"].lower()


def test_otp_rejected_when_expired(client: TestClient, monkeypatch):
    """Verifies that an expired OTP challenge is rejected with 400."""
    mobile = "9876543210"
    client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})

    # Simulate passage of time beyond TTL (e.g. +301 seconds)
    original_time = time.time
    monkeypatch.setattr(time, "time", lambda: original_time() + 350)

    res = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_otp_rejected_on_reuse(client: TestClient):
    """Verifies that once an OTP is verified, a second attempt with the same OTP is rejected."""
    mobile = "9876543210"
    client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile, "role": "FARMER"})

    # First verification -> 200 OK
    res_1 = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_1.status_code == 200

    # Second verification with same OTP -> 400 Bad Request
    res_2 = client.post("/api/v1/auth/verify-otp", json={
        "mobile_number": mobile,
        "otp": "123456",
        "role": "FARMER"
    })
    assert res_2.status_code == 400
    assert "already been used" in res_2.json()["detail"].lower()
