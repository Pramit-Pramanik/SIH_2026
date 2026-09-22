import time
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.models.weighbridge import WeighbridgeEvent
from backend.app.services.queue_manager import queue_manager
from backend.app.services.eta_service import (
    get_active_scales,
    set_active_scales,
    reset_active_scales,
    record_weighbridge_completion,
    calculate_service_rate_mu,
    calculate_queue_etas
)
from backend.app.schemas.queue import QueueItem
from backend.app.services.auth_service import create_user_token



@pytest.fixture
def eta_test_env(db_session: Session):
    """
    Sets up isolated test mandi, users, and transactions for ETA testing.
    """
    reset_active_scales()

    mandi = Mandi(
        mandi_id=1,
        name="Test Mandi Bhopal",
        district="Bhopal",
        state="Madhya Pradesh",
        daily_capacity_qt=2000.0,
        active_weighbridges=2,
        is_operational=True
    )
    db_session.add(mandi)

    farmer1 = Farmer(
        farmer_id=101,
        name="Farmer One",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_101",
        ifsc_code="SBIN0001042",
        land_area_hectares=5.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=200.0,
        aadhaar_hash="hash_farmer_101"
    )
    farmer2 = Farmer(
        farmer_id=102,
        name="Farmer Two",
        mobile_number="9876543211",
        bank_account_hash="bank_hash_102",
        ifsc_code="SBIN0001042",
        land_area_hectares=4.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=160.0,
        aadhaar_hash="hash_farmer_102"
    )
    farmer3 = Farmer(
        farmer_id=103,
        name="Farmer Three",
        mobile_number="9876543212",
        bank_account_hash="bank_hash_103",
        ifsc_code="SBIN0001042",
        land_area_hectares=3.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=120.0,
        aadhaar_hash="hash_farmer_103"
    )
    db_session.add_all([farmer1, farmer2, farmer3])

    op_user = User(
        user_id=10,
        username="op_eta_test",
        hashed_password="fake_hash",
        full_name="Operator ETA",
        role="OPERATOR",
        mandi_id=1
    )
    admin_user = User(
        user_id=11,
        username="admin_eta_test",
        hashed_password="fake_hash",
        full_name="Admin ETA",
        role="ADMIN"
    )
    db_session.add_all([op_user, admin_user])
    db_session.commit()

    op_token = create_user_token(op_user).access_token
    admin_token = create_user_token(admin_user).access_token

    yield {
        "mandi_id": 1,
        "op_token": op_token,
        "admin_token": admin_token,
    }

    reset_active_scales()


def test_zero_vehicles_ahead_gives_zero_eta(db_session: Session, eta_test_env):
    """
    Test 1: Zero vehicles ahead (Rank 1 vehicle) has 0.0 qt payload ahead and 0.0 min ETA.
    """
    mandi_id = eta_test_env["mandi_id"]
    now = datetime.now(timezone.utc)

    # Ingest weighbridge telemetry: 60 qt across 2 scales in 15 min -> mu = 120 qt/hour/scale
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-COMP-01",
        gross_weight_qt=100.0,
        tare_weight_qt=40.0,
        net_weight_qt=60.0,
        completed_at=now - timedelta(minutes=5)
    )

    items = [
        QueueItem(
            rank=1,
            transaction_id="TXN-TOP-01",
            priority_score=95.0,
            quantity_qt=50.0
        )
    ]

    enriched = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)
    assert len(enriched) == 1
    assert enriched[0].rank == 1
    assert enriched[0].payload_ahead_qt == 0.0
    assert enriched[0].eta_minutes == 0.0
    assert enriched[0].eta_status == "CALCULATED"
    assert enriched[0].active_scales == 2
    assert enriched[0].service_rate_qt_per_hour_per_scale == 120.0


def test_one_and_multiple_vehicles_ahead_deterministic_eta(db_session: Session, eta_test_env):
    """
    Test 2: One and multiple vehicles ahead:
    Payload ahead sums correctly and ETA matches formula: W_i = (Payload_ahead) / (mu * N_s) * 60
    """
    mandi_id = eta_test_env["mandi_id"]
    now = datetime.now(timezone.utc)

    # 60 qt in 15 min (0.25h) on 2 scales -> mu = 60 / (0.25 * 2) = 120 qt/hour/scale
    # Total scale capacity = 120 * 2 = 240 qt/hour
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-COMP-01",
        gross_weight_qt=100.0,
        tare_weight_qt=40.0,
        net_weight_qt=60.0,
        completed_at=now - timedelta(minutes=7)
    )

    items = [
        QueueItem(rank=1, transaction_id="TXN-1", priority_score=90.0, quantity_qt=60.0),
        QueueItem(rank=2, transaction_id="TXN-2", priority_score=80.0, quantity_qt=40.0),
        QueueItem(rank=3, transaction_id="TXN-3", priority_score=70.0, quantity_qt=65.0),
        QueueItem(rank=4, transaction_id="TXN-4", priority_score=60.0, quantity_qt=50.0),
    ]

    enriched = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)

    # Vehicle 1 (Rank 1): 0 vehicles ahead, 0 qt payload ahead -> 0 min
    assert enriched[0].payload_ahead_qt == 0.0
    assert enriched[0].eta_minutes == 0.0

    # Vehicle 2 (Rank 2): 1 vehicle ahead (TXN-1: 60 qt)
    # ETA = (60 / 240) * 60 = 0.25 * 60 = 15.00 min
    assert enriched[1].payload_ahead_qt == 60.0
    assert enriched[1].eta_minutes == 15.00
    assert enriched[1].eta_status == "CALCULATED"

    # Vehicle 3 (Rank 3): 2 vehicles ahead (TXN-1: 60, TXN-2: 40 -> 100 qt)
    # ETA = (100 / 240) * 60 = 25.00 min
    assert enriched[2].payload_ahead_qt == 100.0
    assert enriched[2].eta_minutes == 25.00

    # Vehicle 4 (Rank 4): 3 vehicles ahead (60 + 40 + 65 = 165 qt)
    # Matches the exact user specification example: 165 qt ahead, mu=120, N_s=2 -> ETA 41.25 min!
    assert enriched[3].payload_ahead_qt == 165.0
    assert enriched[3].service_rate_qt_per_hour_per_scale == 120.0
    assert enriched[3].active_scales == 2
    assert enriched[3].eta_minutes == 41.25


def test_zero_service_telemetry_returns_insufficient_telemetry(db_session: Session, eta_test_env):
    """
    Test 3: When zero weighbridge telemetry exists, returns INSUFFICIENT_TELEMETRY without fabricating rates.
    """
    mandi_id = eta_test_env["mandi_id"]

    # Ensure zero weighbridge events
    db_session.query(WeighbridgeEvent).filter(WeighbridgeEvent.mandi_id == mandi_id).delete()
    db_session.commit()

    items = [
        QueueItem(rank=1, transaction_id="TXN-1", priority_score=90.0, quantity_qt=50.0),
        QueueItem(rank=2, transaction_id="TXN-2", priority_score=80.0, quantity_qt=40.0),
    ]

    enriched = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)

    assert enriched[0].eta_status == "INSUFFICIENT_TELEMETRY"
    assert enriched[1].eta_status == "INSUFFICIENT_TELEMETRY"
    assert enriched[1].eta_minutes is None
    assert enriched[1].service_rate_qt_per_hour_per_scale is None
    assert enriched[1].payload_ahead_qt == 50.0


def test_active_scale_scaling_2_scales_vs_1_scale_doubles_eta(db_session: Session, eta_test_env):
    """
    Test 4: Demonstrate:
    2 active scales -> ETA X
    1 active scale -> ETA approximately 2X for the same queue/service conditions.
    """
    mandi_id = eta_test_env["mandi_id"]
    now = datetime.now(timezone.utc)

    # Telemetry: 60 qt completed in previous 15 min on 2 scales -> mu = 120 qt/hour/scale
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-COMP-01",
        gross_weight_qt=100.0,
        tare_weight_qt=40.0,
        net_weight_qt=60.0,
        scale_id="SCALE-01",
        completed_at=now - timedelta(minutes=5)
    )

    items = [
        QueueItem(rank=1, transaction_id="TXN-1", priority_score=90.0, quantity_qt=165.0),
        QueueItem(rank=2, transaction_id="TXN-2", priority_score=80.0, quantity_qt=50.0),
    ]

    # Run with 2 active scales
    set_active_scales(db_session, mandi_id, 2)
    enriched_2_scales = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)
    eta_2_scales = enriched_2_scales[1].eta_minutes
    assert eta_2_scales == 41.25

    # Run with 1 active scale (one scale offline)
    set_active_scales(db_session, mandi_id, 1)
    enriched_1_scale = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)
    eta_1_scale = enriched_1_scale[1].eta_minutes
    assert eta_1_scale == 82.50

    # Verify exact 2X relationship: 82.50 / 41.25 == 2.0
    assert abs((eta_1_scale / eta_2_scales) - 2.0) < 1e-4


def test_service_rate_changes_recalculate_eta_proportionally(db_session: Session, eta_test_env):
    """
    Test 5: Service rate changes update mu and recalculate ETA proportionally.
    """
    mandi_id = eta_test_env["mandi_id"]
    now = datetime.now(timezone.utc)
    set_active_scales(db_session, mandi_id, 2)

    # 1. First condition: 60 qt in 15 min -> mu = 120 qt/hour/scale
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-COMP-A",
        gross_weight_qt=100.0,
        tare_weight_qt=40.0,
        net_weight_qt=60.0,
        completed_at=now - timedelta(minutes=6)
    )

    items = [
        QueueItem(rank=1, transaction_id="TXN-1", priority_score=90.0, quantity_qt=120.0),
        QueueItem(rank=2, transaction_id="TXN-2", priority_score=80.0, quantity_qt=50.0),
    ]

    res1 = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)
    # Payload ahead = 120. Rate = 120 * 2 = 240. ETA = (120/240)*60 = 30.0 min
    assert res1[1].service_rate_qt_per_hour_per_scale == 120.0
    assert res1[1].eta_minutes == 30.00

    # 2. Service speedup: Add another 60 qt completed within window -> Total 120 qt in 15 min
    # mu = 120 / (0.25 * 2) = 240 qt/hour/scale. Rate = 240 * 2 = 480 qt/hour.
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-COMP-B",
        gross_weight_qt=110.0,
        tare_weight_qt=50.0,
        net_weight_qt=60.0,
        completed_at=now - timedelta(minutes=3)
    )

    res2 = calculate_queue_etas(db=db_session, mandi_id=mandi_id, queue_items=items)
    assert res2[1].service_rate_qt_per_hour_per_scale == 240.0
    # ETA = (120 / 480) * 60 = 15.00 min (half the wait time!)
    assert res2[1].eta_minutes == 15.00


def test_15_minute_rolling_window_excludes_older_events(db_session: Session, eta_test_env):
    """
    Test 6: Weighbridge events older than 15 minutes are strictly excluded from rolling service rate.
    """
    mandi_id = eta_test_env["mandi_id"]
    now = datetime.now(timezone.utc)
    set_active_scales(db_session, mandi_id, 2)

    # Event 1: 16 minutes ago (OUTSIDE 15-minute window) -> 100 qt
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-OLD",
        gross_weight_qt=150.0,
        tare_weight_qt=50.0,
        net_weight_qt=100.0,
        completed_at=now - timedelta(minutes=16)
    )

    # Event 2: 10 minutes ago (INSIDE 15-minute window) -> 30 qt
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-NEW",
        gross_weight_qt=80.0,
        tare_weight_qt=50.0,
        net_weight_qt=30.0,
        completed_at=now - timedelta(minutes=10)
    )

    mu, active_scales, total_qt, event_count = calculate_service_rate_mu(
        db=db_session,
        mandi_id=mandi_id,
        current_time=now.timestamp(),
        window_minutes=15.0
    )

    # Only TXN-NEW (30 qt) should be included! TXN-OLD (100 qt) must be excluded.
    assert event_count == 1
    assert total_qt == 30.0
    # mu = 30 / (0.25 * 2) = 60 qt/hour/scale
    assert mu == 60.0


def test_scale_configuration_api(client: TestClient, eta_test_env):
    """
    Test 7: Scale configuration API (GET & POST /api/v1/queue/{mandi_id}/scales).
    """
    mandi_id = eta_test_env["mandi_id"]
    op_headers = {"Authorization": f"Bearer {eta_test_env['op_token']}"}

    # GET scales
    resp = client.get(f"/api/v1/queue/{mandi_id}/scales", headers=op_headers)
    assert resp.status_code == 200
    assert resp.json()["active_scales"] >= 1

    # POST update scales to 1 (one scale offline)
    resp = client.post(f"/api/v1/queue/{mandi_id}/scales", headers=op_headers, json={"active_scales": 1})
    assert resp.status_code == 200
    assert resp.json()["active_scales"] == 1

    # Verify GET reflects updated count
    resp = client.get(f"/api/v1/queue/{mandi_id}/scales", headers=op_headers)
    assert resp.status_code == 200
    assert resp.json()["active_scales"] == 1

    # Restore to 2 scales
    resp = client.post(f"/api/v1/queue/{mandi_id}/scales", headers=op_headers, json={"active_scales": 2})
    assert resp.status_code == 200
    assert resp.json()["active_scales"] == 2


def test_live_queue_api_returns_eta_and_telemetry(client: TestClient, db_session: Session, eta_test_env):
    """
    Test 8: GET /api/v1/queue/{mandi_id} returns enriched ETA and telemetry fields for each QueueItem.
    """
    mandi_id = eta_test_env["mandi_id"]
    op_headers = {"Authorization": f"Bearer {eta_test_env['op_token']}"}
    now = datetime.now(timezone.utc)

    # Ingest telemetry so ETA is CALCULATED
    record_weighbridge_completion(
        db=db_session,
        mandi_id=mandi_id,
        transaction_id="TXN-TEST-COMP-99",
        gross_weight_qt=100.0,
        tare_weight_qt=40.0,
        net_weight_qt=60.0,
        completed_at=now - timedelta(minutes=5)
    )

    # Put a QUALITY_APPROVED log in DB and queue
    log = ProcurementLog(
        transaction_id="TXN-ETA-LIVE-01",
        farmer_id=101,
        mandi_id=mandi_id,
        slot_id=None,
        scheduled_date=now.date(),
        crop_type="Wheat",
        crop_moisture_pct=12.0,
        net_weight_qt=45.0,
        current_state="QUALITY_APPROVED",
        token_signature="sig_eta_test",
        created_at=now
    )
    db_session.add(log)
    db_session.commit()

    queue_manager.enqueue(mandi_id, "TXN-ETA-LIVE-01", priority_score=85.0, arrival_ts=now.timestamp())

    resp = client.get(f"/api/v1/queue/{mandi_id}", headers=op_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_vehicles"] >= 1

    item = next((it for it in data["items"] if it["transaction_id"] == "TXN-ETA-LIVE-01"), None)
    assert item is not None
    assert "eta_minutes" in item
    assert "payload_ahead_qt" in item
    assert "service_rate_qt_per_hour_per_scale" in item
    assert "active_scales" in item
    assert "eta_status" in item
    assert item["active_scales"] == 2
    assert item["service_rate_qt_per_hour_per_scale"] == 120.0
