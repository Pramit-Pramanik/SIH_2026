"""
Test Suite: Role RBAC Matrix (Section 3, 19, 34)
Verifies explicit role permissions and prohibited endpoint access across all 5 roles:
FARMER, OPERATOR, INSPECTOR, SUPERVISOR, ADMIN.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.mandi import Mandi
from backend.app.services.auth_service import ensure_default_operational_users

def setup_test_env(db: Session):
    mandi = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2500.0,
        active_weighbridges=2,
        is_operational=True
    )
    db.add(mandi)
    db.commit()
    db.refresh(mandi)
    ensure_default_operational_users(db, mandi_id=mandi.mandi_id)
    return mandi

def get_auth_token(client: TestClient, username: str, password: str = "Admin@MandiQ2026") -> str:
    if username == "farmer":
        password = "Farmer@MandiQ2026"
    elif username == "operator":
        password = "Operator@MandiQ2026"
    elif username == "inspector":
        password = "Inspector@MandiQ2026"
    elif username == "supervisor":
        password = "Supervisor@MandiQ2026"
    elif username == "admin":
        password = "Admin@MandiQ2026"

    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]

def test_unauthenticated_requests_return_401(client: TestClient, db_session: Session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MANDIQ_AUTH_ENFORCED", True)
    setup_test_env(db_session)

    endpoints = [
        ("GET", "/api/v1/admin/metrics"),
        ("POST", "/api/v1/admin/simulate-showcase"),
        ("POST", "/api/v1/admin/reset-showcase"),
        ("POST", "/api/v1/quality/assess"),
        ("POST", "/api/v1/weighbridge/capture"),
        ("POST", "/api/v1/billing/generate"),
        ("POST", "/api/v1/payout/stage"),
    ]
    for method, endpoint in endpoints:
        if method == "GET":
            resp = client.get(endpoint)
        else:
            resp = client.post(endpoint, json={})
        assert resp.status_code == 401, f"Expected 401 for unauthenticated {endpoint}, got {resp.status_code}"

def test_farmer_prohibitions(client: TestClient, db_session: Session):
    setup_test_env(db_session)
    token = get_auth_token(client, "farmer")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Admin endpoints
    r = client.get("/api/v1/admin/metrics", headers=headers)
    assert r.status_code == 403, f"Farmer admin metrics should be 403, got {r.status_code}"

    r = client.post("/api/v1/admin/simulate-showcase", json={"mandi_id": 1}, headers=headers)
    assert r.status_code == 403, f"Farmer simulate-showcase should be 403, got {r.status_code}"

    r = client.post("/api/v1/admin/reset-showcase", headers=headers)
    assert r.status_code == 403, f"Farmer reset-showcase should be 403, got {r.status_code}"

    # 2. Quality assessment
    r = client.post("/api/v1/quality/assess", json={"transaction_id": "T1", "crop_moisture_pct": 12.0}, headers=headers)
    assert r.status_code == 403, f"Farmer quality assess should be 403, got {r.status_code}"

    # 3. Weighbridge capture
    r = client.post("/api/v1/weighbridge/capture", json={"transaction_id": "T1", "gross_weight_qt": 50.0, "tare_weight_qt": 20.0}, headers=headers)
    assert r.status_code == 403, f"Farmer weighbridge should be 403, got {r.status_code}"

    # 4. Billing
    r = client.post("/api/v1/billing/generate", json={"transaction_id": "T1", "rate_per_qt": 2275.0}, headers=headers)
    assert r.status_code == 403, f"Farmer billing should be 403, got {r.status_code}"

    # 5. Payout
    r = client.post("/api/v1/payout/stage", json={"transaction_id": "T1"}, headers=headers)
    assert r.status_code == 403, f"Farmer payout should be 403, got {r.status_code}"

def test_operator_prohibitions(client: TestClient, db_session: Session):
    setup_test_env(db_session)
    token = get_auth_token(client, "operator")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/admin/metrics", headers=headers)
    assert r.status_code == 403, f"Operator admin metrics should be 403, got {r.status_code}"

    r = client.post("/api/v1/admin/simulate-showcase", json={"mandi_id": 1}, headers=headers)
    assert r.status_code == 403, f"Operator simulate-showcase should be 403, got {r.status_code}"

    r = client.post("/api/v1/admin/reset-showcase", headers=headers)
    assert r.status_code == 403, f"Operator reset-showcase should be 403, got {r.status_code}"

def test_inspector_prohibitions(client: TestClient, db_session: Session):
    setup_test_env(db_session)
    token = get_auth_token(client, "inspector")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/admin/metrics", headers=headers)
    assert r.status_code == 403, f"Inspector admin metrics should be 403, got {r.status_code}"

    r = client.post("/api/v1/admin/simulate-showcase", json={"mandi_id": 1}, headers=headers)
    assert r.status_code == 403, f"Inspector simulate-showcase should be 403, got {r.status_code}"

    r = client.post("/api/v1/admin/reset-showcase", headers=headers)
    assert r.status_code == 403, f"Inspector reset-showcase should be 403, got {r.status_code}"

    r = client.post("/api/v1/weighbridge/capture", json={"transaction_id": "T1", "gross_weight_qt": 50.0, "tare_weight_qt": 20.0}, headers=headers)
    assert r.status_code == 403, f"Inspector weighbridge should be 403, got {r.status_code}"

def test_admin_and_supervisor_authority(client: TestClient, db_session: Session):
    setup_test_env(db_session)

    admin_token = get_auth_token(client, "admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert r.status_code == 200, f"Admin metrics should be 200, got {r.status_code}"

    sup_token = get_auth_token(client, "supervisor")
    sup_headers = {"Authorization": f"Bearer {sup_token}"}
    r = client.get("/api/v1/admin/metrics", headers=sup_headers)
    assert r.status_code == 200, f"Supervisor metrics should be 200, got {r.status_code}"
