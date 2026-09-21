"""
MandiQ Phase 6 Test Suite — Zero Operational Magic-Identity Fallbacks.

Verifies:
1. GET /api/v1/admin/showcase/farmers:
   - Strict RBAC: 401 unauthenticated, 403 for FARMER, OPERATOR, INSPECTOR, 200 for ADMIN/SUPERVISOR.
   - Returns live DB data (Ramesh, Balvinder, Suresh) with dynamic ceilings, bookings, and mandi associations.
2. Strict Mandi Validation (Zero Silent Fallback to Mandi 1):
   - /api/v1/queue/{mandi_id} returns 404 on invalid mandi.
   - /api/v1/slots returns 404 on invalid mandi.
   - /api/v1/slots/reserve returns 404 on invalid mandi.
   - /api/v1/admin/generate-slots returns 422 if mandi_id missing, 404 if not found in DB.
   - /api/v1/admin/metrics returns 404 on invalid mandi.
   - /api/v1/admin/reset-showcase returns 404 on invalid mandi, 422 on negative mandi_id.
3. Multi-Farmer Identity & Booking Isolation:
   - Farmer 1 (Ramesh), Farmer 2 (Balvinder), Farmer 3 (Suresh) records are strictly isolated.
4. Mandi Switching & Yard Resource Partitioning:
   - Slots and queue state are strictly isolated between Mandi 1 and Mandi 2.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.services.seed_service import bootstrap_database, CANONICAL_FARMERS
from backend.app.services.auth_service import create_user_token
from backend.app.models.user import User
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog


@pytest.fixture(autouse=True)
def seed_demo_data(db_session: Session):
    """Ensure database has canonical seed baseline for identity tests."""
    bootstrap_database(db_session, reset=True)


def get_token_for_role(db: Session, role: str, farmer_id: int = None, mandi_id: int = None) -> str:
    user = db.query(User).filter(User.role == role).first()
    if not user:
        raise ValueError(f"No user with role {role}")
    if mandi_id is not None:
        user.mandi_id = mandi_id
    token_resp = create_user_token(user, farmer_id=farmer_id)
    return token_resp.access_token


def test_showcase_farmers_endpoint_rbac(client: TestClient, db_session: Session):
    """GET /api/v1/admin/showcase/farmers must reject non-admin/supervisor with 401/403."""
    # 1. Unauthenticated -> 401
    r_unauth = client.get("/api/v1/admin/showcase/farmers")
    assert r_unauth.status_code == 401

    # 2. Farmer -> 403
    farmer_tok = get_token_for_role(db_session, "FARMER", farmer_id=1)
    r_farmer = client.get("/api/v1/admin/showcase/farmers", headers={"Authorization": f"Bearer {farmer_tok}"})
    assert r_farmer.status_code == 403

    # 3. Operator -> 403
    op_tok = get_token_for_role(db_session, "OPERATOR", mandi_id=1)
    r_op = client.get("/api/v1/admin/showcase/farmers", headers={"Authorization": f"Bearer {op_tok}"})
    assert r_op.status_code == 403

    # 4. Inspector -> 403
    insp_tok = get_token_for_role(db_session, "INSPECTOR", mandi_id=1)
    r_insp = client.get("/api/v1/admin/showcase/farmers", headers={"Authorization": f"Bearer {insp_tok}"})
    assert r_insp.status_code == 403

    # 5. Supervisor -> 200
    sup_tok = get_token_for_role(db_session, "SUPERVISOR", mandi_id=1)
    r_sup = client.get("/api/v1/admin/showcase/farmers", headers={"Authorization": f"Bearer {sup_tok}"})
    assert r_sup.status_code == 200

    # 6. Admin -> 200
    admin_tok = get_token_for_role(db_session, "ADMIN")
    r_admin = client.get("/api/v1/admin/showcase/farmers", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_admin.status_code == 200


def test_showcase_farmers_endpoint_returns_live_db_data(client: TestClient, db_session: Session):
    """GET /api/v1/admin/showcase/farmers returns authoritative live DB state."""
    admin_tok = get_token_for_role(db_session, "ADMIN")
    resp = client.get("/api/v1/admin/showcase/farmers", headers={"Authorization": f"Bearer {admin_tok}"})
    assert resp.status_code == 200
    data = resp.json()

    assert "farmers" in data
    assert data["count"] >= 3

    farmers_by_id = {f["farmer_id"]: f for f in data["farmers"]}

    # Verify Farmer 1: Ramesh Kumar
    f1 = farmers_by_id.get(1)
    assert f1 is not None
    assert f1["name"] == "Ramesh Kumar"
    assert f1["crop"] == "Wheat (HD-2967)"
    assert f1["ceiling_qt"] == 600.0
    assert f1["mandi_id"] == 1
    assert "Sehore" in f1["mandi_name"]
    assert f1["remaining_ceiling_qt"] > 0

    # Verify Farmer 2: Balvinder / Balwinder Singh
    f2 = farmers_by_id.get(2)
    assert f2 is not None
    assert "Balwinder" in f2["name"] or "Balvinder" in f2["name"]
    assert f2["ceiling_qt"] == 350.0
    assert f2["mandi_id"] == 1

    # Verify Farmer 3: Suresh Patel
    f3 = farmers_by_id.get(3)
    assert f3 is not None
    assert f3["name"] == "Suresh Patel"
    assert "Mustard" in f3["crop"]
    assert f3["ceiling_qt"] == 250.0
    assert f3["mandi_id"] in (1, 2)
    assert any(k in f3["mandi_name"] for k in ("Sehore", "Karnal"))


def test_mandi_strict_validation_no_silent_defaults(client: TestClient, db_session: Session):
    """Verifies that invalid or non-existent mandi_id returns 404/422, never silently defaulting to 1."""
    admin_tok = get_token_for_role(db_session, "ADMIN")
    admin_headers = {"Authorization": f"Bearer {admin_tok}"}

    # 1. Queue endpoints: non-existent mandi 99999 -> 404
    r_queue = client.get("/api/v1/queue/99999")
    assert r_queue.status_code == 404

    r_queue_state = client.get("/api/v1/queue/state?mandi_id=99999")
    assert r_queue_state.status_code == 404

    # 2. Slots listing: non-existent mandi 99999 -> 404
    r_slots = client.get("/api/v1/slots?mandi_id=99999")
    assert r_slots.status_code == 404

    # 3. Slot reservation: non-existent mandi 99999 -> 404
    farmer_tok = get_token_for_role(db_session, "FARMER", farmer_id=1)
    r_reserve = client.post(
        "/api/v1/slots/reserve",
        headers={"Authorization": f"Bearer {farmer_tok}"},
        json={"mandi_id": 99999, "slot_id": 1, "farmer_id": 1, "requested_qty_qt": 10.0}
    )
    assert r_reserve.status_code == 404

    # 4. Generate slots: missing mandi_id -> 422
    r_gen_missing = client.post(
        "/api/v1/admin/generate-slots",
        headers=admin_headers,
        json={"start_date": "2026-09-25", "num_days": 1}
    )
    assert r_gen_missing.status_code == 422

    # 5. Generate slots: non-existent mandi 99999 -> 404
    r_gen_invalid = client.post(
        "/api/v1/admin/generate-slots",
        headers=admin_headers,
        json={"mandi_id": 99999, "start_date": "2026-09-25", "num_days": 1}
    )
    assert r_gen_invalid.status_code == 404

    # 6. Admin metrics: non-existent mandi 99999 -> 404
    r_metrics = client.get("/api/v1/admin/metrics?mandi_id=99999", headers=admin_headers)
    assert r_metrics.status_code == 404

    # 7. Reset showcase: non-existent mandi 99999 -> 404
    r_reset_404 = client.post(
        "/api/v1/admin/reset-showcase",
        headers=admin_headers,
        json={"mandi_id": 99999}
    )
    assert r_reset_404.status_code == 404

    # 8. Reset showcase: negative mandi -> 422
    r_reset_422 = client.post(
        "/api/v1/admin/reset-showcase",
        headers=admin_headers,
        json={"mandi_id": -5}
    )
    assert r_reset_422.status_code == 422


def test_farmer_identity_and_booking_isolation(client: TestClient, db_session: Session):
    """Verifies that each farmer's profile, ceilings, and latest bookings are strictly isolated."""
    admin_tok = get_token_for_role(db_session, "ADMIN")
    admin_headers = {"Authorization": f"Bearer {admin_tok}"}

    # Fetch profile for Farmer 1 (Ramesh)
    r1 = client.get("/api/v1/farmers/profile?farmer_id=1", headers=admin_headers)
    assert r1.status_code == 200
    p1 = r1.json()
    assert p1["name"] == "Ramesh Kumar"
    assert p1["production_ceiling_qt"] == 600.0

    # Fetch profile for Farmer 2 (Balvinder / Balwinder)
    r2 = client.get("/api/v1/farmers/profile?farmer_id=2", headers=admin_headers)
    assert r2.status_code == 200
    p2 = r2.json()
    assert "Balwinder" in p2["name"] or "Balvinder" in p2["name"]
    assert p2["production_ceiling_qt"] == 350.0

    # Fetch profile for Farmer 3 (Suresh)
    r3 = client.get("/api/v1/farmers/profile?farmer_id=3", headers=admin_headers)
    assert r3.status_code == 200
    p3 = r3.json()
    assert p3["name"] == "Suresh Patel"
    assert p3["production_ceiling_qt"] == 250.0

    # Fetch latest booking for Farmer 1 vs Farmer 3
    b1 = client.get("/api/v1/farmers/1/latest-booking", headers=admin_headers).json()
    b3 = client.get("/api/v1/farmers/3/latest-booking", headers=admin_headers).json()

    assert b1["has_booking"] is True
    assert b1["booking"]["farmer_id"] == 1
    assert b1["booking"]["farmer_name"] == "Ramesh Kumar"

    if b3["has_booking"]:
        assert b3["booking"]["farmer_id"] == 3
        assert b3["booking"]["farmer_name"] == "Suresh Patel"
        assert b3["booking"]["transaction_id"] != b1["booking"]["transaction_id"]


def test_mandi_switching_isolation(client: TestClient, db_session: Session):
    """Verifies that Mandi 1 (Khanna) and Mandi 2 (Sirsa) resources and queues are isolated."""
    # 1. Mandi 1 Queue vs Mandi 2 Queue
    q1 = client.get("/api/v1/queue/1").json()
    q2 = client.get("/api/v1/queue/2").json()

    assert q1["mandi_id"] == 1
    assert q2["mandi_id"] == 2

    # TXN-DEMO-1002 is enqueued in Mandi 1, not Mandi 2
    q1_txns = [item["transaction_id"] for item in q1["items"]]
    q2_txns = [item["transaction_id"] for item in q2["items"]]

    assert "TXN-DEMO-1002" in q1_txns
    assert "TXN-DEMO-1002" not in q2_txns

    # 2. Mandi 1 Slots vs Mandi 2 Slots
    s1 = client.get("/api/v1/slots?mandi_id=1").json()
    s2 = client.get("/api/v1/slots?mandi_id=2").json()

    assert all(slot["mandi_id"] == 1 for slot in s1)
    assert all(slot["mandi_id"] == 2 for slot in s2)
