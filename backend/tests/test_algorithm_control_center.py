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

    admin_user = db_session.query(User).filter(User.username == "admin_showcase_test").first()
    if not admin_user:
        admin_user = User(
            user_id=999,
            username="admin_showcase_test",
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


def test_hmac_verification_endpoint_success(client: TestClient):
    """
    Test POST /api/v1/admin/demo/hmac-verification
    Verifies authentic payload is validated, tampered payload is rejected,
    the signature is a valid 64-char SHA256 hex digest, and secret key is strictly protected.
    """
    req_data = {
        "farmer_id": 101,
        "mandi_id": 1,
        "slot_id": 5,
        "quantity_qt": 25.0,
        "tamper_quantity_qt": 250.0
    }
    response = client.post("/api/v1/admin/demo/hmac-verification", json=req_data)
    assert response.status_code == 200, f"Unexpected error: {response.text}"
    data = response.json()

    # 1. Verification assertions
    assert data["is_valid"] is True
    assert data["tamper_rejected"] is True
    assert data["signature_length_chars"] == 64
    assert len(data["signature_preview"]) >= 10

    # 2. Security assertions - zero secret leakage
    assert data["secret_key_status"].startswith("PROTECTED")
    assert "test-hmac-secret-key" not in str(data)

    # 3. Canonical payload check
    assert data["canonical_payload"] == "101:1:5:25.0"
    assert data["tampered_payload"] == "101:1:5:250.0"

    # 4. Execution trace assertions
    assert len(data["execution_trace"]) >= 4
    assert any("VALID_VERIFIED" in tr for tr in data["execution_trace"])
    assert any("REJECTED_SIGNATURE_MISMATCH" in tr for tr in data["execution_trace"])


def test_dcdq_reorder_demo_endpoint(client: TestClient):
    """
    Test POST /api/v1/admin/demo/dcdq-reorder
    Verifies DCDQ composite score formula: S = alpha*A + beta*D + gamma*M + lambda*W (with unit weights)
    and dynamic queue reordering when wait/moisture values shift.
    """
    # 1. Baseline calculation
    req_baseline = {
        "mandi_id": 1,
        "tweak_transaction_id": "TXN-DEMO-V05",
        "delta_wait_minutes": 10.0,
        "new_moisture_pct": 14.0
    }
    res_base = client.post("/api/v1/admin/demo/dcdq-reorder", json=req_baseline)
    assert res_base.status_code == 200
    data_base = res_base.json()

    assert len(data_base["before_queue"]) >= 3
    for v in data_base["before_queue"]:
        # Verify formula S = A + D + M + W (canonical weights 1.0)
        computed_s = round(v["score_a"] + v["score_d"] + v["score_m"] + v["score_w"], 4)
        assert abs(v["composite_score_s"] - computed_s) < 0.001, f"Formula mismatch for {v['transaction_id']}"

    # 2. Test reordering with extreme wait time
    req_reorder = {
        "mandi_id": 1,
        "tweak_transaction_id": "TXN-DEMO-V05",
        "delta_wait_minutes": 120.0,
        "new_moisture_pct": 19.5
    }
    res_reorder = client.post("/api/v1/admin/demo/dcdq-reorder", json=req_reorder)
    assert res_reorder.status_code == 200
    data_reorder = res_reorder.json()

    assert len(data_reorder["execution_trace"]) >= 3
    assert data_reorder["rank_changed"] is True
    assert data_reorder["new_rank"] < data_reorder["previous_rank"]
    assert "DYNAMIC_REORDER" in data_reorder["verification_status"]


def test_weighbridge_scales_controls(client: TestClient, admin_headers: dict):
    """
    Test GET and POST /api/v1/queue/{mandi_id}/scales
    Verifies multi-server scale adjustment for queue processing.
    """
    # GET active scales
    res_get = client.get("/api/v1/queue/1/scales", headers=admin_headers)
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert "active_scales" in get_data
    assert get_data["mandi_id"] == 1

    # POST update scales to 3
    res_post = client.post(
        "/api/v1/queue/1/scales",
        json={"active_scales": 3},
        headers=admin_headers
    )
    assert res_post.status_code == 200
    post_data = res_post.json()
    assert post_data["active_scales"] == 3

    # Verify updated scale persisted
    res_verify = client.get("/api/v1/queue/1/scales", headers=admin_headers)
    assert res_verify.status_code == 200
    assert res_verify.json()["active_scales"] == 3


def test_reset_algorithm_showcase_scoped(client: TestClient, admin_headers: dict):
    """
    Test POST /api/v1/admin/demo/reset-algorithm-showcase
    Verifies that only demo showcase records are purged, operational data is preserved,
    and scales are restored to default.
    """
    # First set scales to 4
    client.post("/api/v1/queue/1/scales", json={"active_scales": 4}, headers=admin_headers)

    # Call scoped reset
    res = client.post("/api/v1/admin/demo/reset-algorithm-showcase?mandi_id=1")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "SUCCESS"
    assert data["operational_data_protected"] is True
    assert data["scale_overrides_cleared"] is True
    assert "new_demo_run_id" in data
    assert data["new_demo_run_id"].startswith("DEMO-RUN-")

    # Scales should be reset back to baseline default (2)
    scales_res = client.get("/api/v1/queue/1/scales", headers=admin_headers)
    assert scales_res.status_code == 200
    assert scales_res.json()["active_scales"] == 2


def test_zero_magic_fallbacks_rejected(client: TestClient, admin_headers: dict):
    """
    Test DATA-001 Zero Magic Fallbacks invariant.
    Verifies that calling demo/algorithm endpoints without mandatory identity
    rejects with 422 and does NOT silently substitute farmer 1 or mandi 1.
    """
    # 1. Concurrent booking without mandi_id
    res_conc = client.post(
        "/api/v1/admin/demo/concurrent-booking",
        json={"concurrent_requests": 5},
        headers=admin_headers
    )
    assert res_conc.status_code == 422
    assert "mandi_id" in res_conc.text

    # 2. HMAC verification without farmer_id or mandi_id
    res_hmac_no_mandi = client.post(
        "/api/v1/admin/demo/hmac-verification",
        json={"farmer_id": 101, "slot_id": 5, "quantity_qt": 25.0}
    )
    assert res_hmac_no_mandi.status_code == 422
    assert "mandi_id" in res_hmac_no_mandi.text

    res_hmac_no_farmer = client.post(
        "/api/v1/admin/demo/hmac-verification",
        json={"mandi_id": 1, "slot_id": 5, "quantity_qt": 25.0}
    )
    assert res_hmac_no_farmer.status_code == 422
    assert "farmer_id" in res_hmac_no_farmer.text

    # 3. DCDQ reorder demo without mandi_id
    res_dcdq = client.post(
        "/api/v1/admin/demo/dcdq-reorder",
        json={"delta_wait_minutes": 20.0}
    )
    assert res_dcdq.status_code == 422
    assert "mandi_id" in res_dcdq.text

