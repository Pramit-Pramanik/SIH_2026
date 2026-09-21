"""
Test Suite for Operational API Authentication Enforcement (P1-02).
Verifies:
1. Operational mutation endpoints reject requests lacking Authorization Bearer token with 401 Unauthorized.
2. Operational endpoints reject unauthorized roles with 403 Forbidden.
3. Operational endpoints accept valid JWT tokens for authorized roles.
4. Genuinely public endpoints (/health, /api/v1/mandis, /api/v1/crops) remain accessible without authentication.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.services.auth_service import ensure_default_operational_users, create_user_token
from backend.app.models.user import User
from backend.app.core.config import get_settings


@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MANDIQ_AUTH_ENFORCED", True)


def test_public_endpoints_accessible_without_auth(client: TestClient):
    """Verifies that /health, /api/v1/mandis, and /api/v1/crops remain accessible without auth."""
    res_health = client.get("/health")
    assert res_health.status_code == 200

    res_mandis = client.get("/api/v1/mandis")
    assert res_mandis.status_code == 200

    res_crops = client.get("/api/v1/crops")
    assert res_crops.status_code == 200


@pytest.mark.parametrize("method,endpoint,payload", [
    ("POST", "/api/v1/slots/reserve", {"farmer_id": 1, "mandi_id": 1, "slot_id": 1, "requested_qty_qt": 20.0}),
    ("POST", "/api/v1/slots/cancel", {"transaction_id": "TXN-TEST"}),
    ("POST", "/api/v1/gate/check-in", {"mandi_id": 1, "token_id": "MANDIQ-TEST", "farmer_id": 1, "slot_id": 1, "quantity_qt": 20.0, "token_signature": "sig"}),
    ("POST", "/api/v1/quality/assess", {"transaction_id": "TXN-TEST", "crop_moisture_pct": 12.5}),
    ("POST", "/api/v1/quality/override", {"transaction_id": "TXN-TEST", "reason": "Authorized override"}),
    ("POST", "/api/v1/queue/1/dispatch", {}),
    ("POST", "/api/v1/queue/1/rerank", {}),
    ("POST", "/api/v1/weighbridge/gross", {"transaction_id": "TXN-TEST", "gross_weight_qt": 150.0}),
    ("POST", "/api/v1/weighbridge/tare", {"transaction_id": "TXN-TEST", "tare_weight_qt": 50.0}),
    ("POST", "/api/v1/billing/generate", {"transaction_id": "TXN-TEST"}),
    ("POST", "/api/v1/payout/stage", {"transaction_id": "TXN-TEST", "total_payout_inr": 50000.0, "inspector_signature": "sig1", "operator_signature": "sig2"}),
    ("POST", "/api/v1/payout/demo-signatures", {"transaction_id": "TXN-TEST", "invoice_amount_inr": 50000.0, "inspector_id": 1, "operator_id": 2}),
    ("POST", "/api/v1/sync/wal", {"client_mutation_id": "MUT-TEST", "transaction_id": "TXN-TEST", "state": "SLOT_BOOKED", "payload": {}}),
    ("POST", "/api/v1/admin/mandis", {"name": "New Mandi", "district": "Dist", "state": "State", "daily_capacity_qt": 1000.0}),
    ("POST", "/api/v1/admin/reset-showcase", {}),
])
def test_operational_endpoints_require_auth(client: TestClient, method: str, endpoint: str, payload: dict):
    """Asserts that requests without Authorization header return 401 Unauthorized."""
    if method == "POST":
        res = client.post(endpoint, json=payload)
    elif method == "GET":
        res = client.get(endpoint)
    else:
        res = client.request(method, endpoint, json=payload)

    assert res.status_code == 401, f"{endpoint} returned {res.status_code} instead of 401: {res.text}"
    assert "WWW-Authenticate" in res.headers or "detail" in res.json()


def test_operational_endpoint_rejects_unauthorized_role(client: TestClient, db_session: Session):
    """Asserts that an operator trying to access strict admin endpoint receives 403 Forbidden."""
    users = ensure_default_operational_users(db_session)
    operator_user = next(u for u in users if u.role == "OPERATOR")
    token_resp = create_user_token(operator_user)
    headers = {"Authorization": f"Bearer {token_resp.access_token}"}

    res = client.post(
        "/api/v1/admin/mandis",
        json={"name": "Forbidden Mandi", "district": "D", "state": "S", "daily_capacity_qt": 500.0},
        headers=headers
    )
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_operational_endpoint_accepts_authorized_role(client: TestClient, db_session: Session):
    """Asserts that an admin token is authorized on admin endpoints."""
    from backend.app.services.seed_service import ensure_canonical_mandis
    ensure_canonical_mandis(db_session)
    users = ensure_default_operational_users(db_session)
    admin_user = next(u for u in users if u.role == "ADMIN")
    token_resp = create_user_token(admin_user)
    headers = {"Authorization": f"Bearer {token_resp.access_token}"}

    res = client.get("/api/v1/admin/metrics?mandi_id=1", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
