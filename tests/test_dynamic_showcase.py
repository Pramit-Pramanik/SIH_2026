from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_jwt
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.crop import Crop
from backend.app.models.slot import ProcurementSlot
from backend.app.models.user import User
from backend.app.services.auth_service import ensure_default_operational_users


@pytest.fixture
def showcase_data(db_session: Session):
    mandi = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    db_session.add(mandi)

    farmer = Farmer(
        aadhaar_hash="sha256_ramesh_test",
        name="Ramesh Kumar",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_001",
        ifsc_code="SBIN0001040",
        land_area_hectares=10.0,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=500.0
    )
    db_session.add(farmer)

    crop = Crop(
        crop_name="Wheat (HD-2967)",
        crop_code="WHEAT_HD2967",
        category="CEREAL",
        msp_price_inr=2275.0,
        optimal_moisture_pct=14.0,
        max_moisture_pct=17.0,
        is_active=True
    )
    db_session.add(crop)
    db_session.commit()
    ensure_default_operational_users(db_session)
    return mandi


def test_dynamic_slot_auto_provisioning(client: TestClient, showcase_data):
    """
    Verifies that querying slots for an unseeded date defaults to pure read behavior
    (empty list), while explicitly requesting auto_provision=true provisions all 7
    standard operational slots dynamically for showcase presentation.
    """
    future_date = date.today() + timedelta(days=45)

    # 1. Ordinary read: no auto-provisioning side-effect
    resp_read = client.get(f"/api/v1/slots?mandi_id=1&scheduled_date={future_date}")
    assert resp_read.status_code == 200
    assert resp_read.json() == []

    # 2. Explicit showcase auto-provisioning
    resp = client.get(f"/api/v1/slots?mandi_id=1&scheduled_date={future_date}&auto_provision=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7
    assert data[0]["start_time"] == "09:00:00"
    assert data[0]["allocated_capacity_qt"] == 500.0
    assert data[0]["remaining_capacity_qt"] == 500.0


def test_live_mandi_metrics_endpoint(client: TestClient, showcase_data):
    """
    Verifies that /api/v1/admin/metrics aggregates live telemetry from the database.
    """
    token = create_access_jwt({"sub": "admin", "role": "ADMIN", "user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/admin/metrics?mandi_id=1", headers=headers)
    assert resp.status_code == 200
    metrics = resp.json()
    assert metrics["mandi_id"] == 1
    assert "total_registered_farmers" in metrics
    assert "active_transactions_total" in metrics
    assert "queued_vehicles_count" in metrics
    assert "total_volume_procured_qt" in metrics
    assert "total_payout_settled_inr" in metrics
    assert "quality_rejection_rate_pct" in metrics


def test_simulate_showcase_and_reset(client: TestClient, showcase_data):
    """
    Verifies that /api/v1/admin/simulate-showcase dynamically injects showcase vehicles
    with distinct moisture levels, updates the DCDQ queue, and resets cleanly.
    """
    token = create_access_jwt({"sub": "admin", "role": "ADMIN", "user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Inject live traffic
    sim_resp = client.post("/api/v1/admin/simulate-showcase", json={"mandi_id": 1}, headers=headers)
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["status"] == "SUCCESS"
    assert len(sim_data["simulated_vehicles"]) == 5

    # Verify quality rejection rule: 18.6% moisture lot excluded from queue
    rejected_veh = next(v for v in sim_data["simulated_vehicles"] if v["state"] == "QUALITY_REJECTED")
    assert rejected_veh["in_queue"] is False
    assert rejected_veh["moisture"] == 18.6

    # Verify queue query reflects injected approved vehicles
    queue_resp = client.get("/api/v1/queue/1")
    assert queue_resp.status_code == 200
    q_data = queue_resp.json()
    assert q_data["total_vehicles"] >= 2

    # 2. Reset showcase
    reset_resp = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1}, headers=headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "SUCCESS"
