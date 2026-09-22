import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.models.mandi import Mandi
from backend.app.models.user import User
from backend.app.services.auth_service import create_user_token

@pytest.fixture
def admin_headers(db_session: Session) -> dict:
    """Creates an admin user and returns Authorization headers."""
    mandi = db_session.query(Mandi).filter(Mandi.mandi_id == 1).first()
    if not mandi:
        mandi = Mandi(
            mandi_id=1,
            name="Indore APMC Yard",
            district="Indore",
            state="Madhya Pradesh",
            daily_capacity_qt=5000.0,
            active_weighbridges=2,
            is_operational=True
        )
        db_session.add(mandi)
        db_session.commit()
        db_session.refresh(mandi)

    admin_user = db_session.query(User).filter(User.username == "admin_showcase_live").first()
    if not admin_user:
        admin_user = User(
            user_id=888,
            username="admin_showcase_live",
            hashed_password="fake_hash_pwd",
            full_name="Showcase Admin Tester",
            role="ADMIN",
            mandi_id=1
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

    token = create_user_token(admin_user).access_token
    return {"Authorization": f"Bearer {token}"}

def test_live_queue_showcase_flow(client: TestClient, admin_headers: dict):
    # 1. Reset showcase to start clean
    reset_resp = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1}, headers=admin_headers)
    assert reset_resp.status_code == 200

    sim_resp = client.post("/api/v1/admin/simulate-showcase", json={"mandi_id": 1}, headers=admin_headers)
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert len(sim_data["simulated_vehicles"]) >= 3

    # 3. Retrieve Live Queue
    queue_resp = client.get("/api/v1/queue/1", headers=admin_headers)
    assert queue_resp.status_code == 200
    queue_data = queue_resp.json()
    items = queue_data["items"]
    assert len(items) >= 3

    # 4. Verify all 9 required fields + 4 DCDQ component factors exist
    for item in items:
        assert item["rank"] is not None
        assert item["transaction_id"] is not None
        assert item["crop_type"] in ["Wheat", "Chana", "Mustard"]
        assert item["quantity_qt"] > 0
        assert item["moisture_pct"] is not None
        assert item["priority_score"] is not None
        assert item["eta_minutes"] is not None
        assert item["active_scales"] is not None
        assert item["status"] is not None

        # DCDQ score breakdown components
        assert item["score_a"] is not None
        assert item["score_d"] is not None
        assert item["score_m"] is not None
        assert item["score_w"] is not None

    # Verify rank 1 has 0 ETA
    assert items[0]["rank"] == 1
    assert items[0]["eta_minutes"] == 0.0

    # 5. Multi-Server Scale Dynamics: Test 1 Scale vs 3 Scales
    # Set to 1 scale
    s1_resp = client.post("/api/v1/queue/1/scales", json={"active_scales": 1}, headers=admin_headers)
    assert s1_resp.status_code == 200
    q1 = client.get("/api/v1/queue/1", headers=admin_headers).json()["items"]
    eta_scale1 = [it["eta_minutes"] for it in q1]

    # Set to 3 scales
    s3_resp = client.post("/api/v1/queue/1/scales", json={"active_scales": 3}, headers=admin_headers)
    assert s3_resp.status_code == 200
    q3 = client.get("/api/v1/queue/1", headers=admin_headers).json()["items"]
    eta_scale3 = [it["eta_minutes"] for it in q3]

    # With 3 scales, ETA for downstream vehicles (idx >= 1) must be strictly lower than with 1 scale
    for i in range(1, len(items)):
        assert eta_scale3[i] < eta_scale1[i]

    # 6. Advance Showcase Time: Anti-starvation wait increases and scores change dynamically
    pre_advance_scores = {it["transaction_id"]: it["priority_score"] for it in q3}
    pre_advance_wait = {it["transaction_id"]: it["score_w"] for it in q3}

    adv_resp = client.post("/api/v1/admin/advance-showcase-time", json={"mandi_id": 1, "minutes": 90.0}, headers=admin_headers)
    assert adv_resp.status_code == 200

    q_adv = client.get("/api/v1/queue/1", headers=admin_headers).json()["items"]
    for it in q_adv:
        txn = it["transaction_id"]
        # Score W must have increased by 0.1 * 90 = 9.0 points
        assert it["score_w"] > pre_advance_wait[txn]
        # Total priority score must have increased
        assert it["priority_score"] > pre_advance_scores[txn]
