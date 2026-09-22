"""
MandiQ Test Suite — AUD-003: Secure and Persist Live Queue Operations.

Tests:
1. Unauthenticated queue read -> 401
2. Mandi-1 operator -> Mandi-2 queue -> 403 (Admin cross-mandi allowed -> 200)
3. Farmer -> general queue -> 403
4. Farmer -> own vehicle status -> 200
5. Farmer -> other farmer transaction -> 403
6. Offline dispatch WAL sync -> transitions to ROUTED_TO_WEIGHBRIDGE & evicts from queue
7. Duplicate replay is idempotent
8. Server rejection restores/marks conflict correctly
"""

import time
import pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_jwt
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.crop import Crop
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.services.queue_manager import queue_manager


@pytest.fixture
def queue_sec_env(db_session: Session):
    """
    Sets up two Mandis (Mandi 1 & Mandi 2), Crops, Farmers, Slots, Transactions, and Users.
    """
    mandi_1 = Mandi(
        mandi_id=1,
        name="APMC Khanna",
        district="Ludhiana",
        state="Punjab",
        daily_capacity_qt=5000.0,
        is_operational=True
    )
    mandi_2 = Mandi(
        mandi_id=2,
        name="APMC Rajpura",
        district="Patiala",
        state="Punjab",
        daily_capacity_qt=4000.0,
        is_operational=True
    )
    db_session.add(mandi_1)
    db_session.add(mandi_2)

    crop = Crop(
        crop_id=1,
        crop_name="Wheat (HD-2967)",
        crop_code="WHEAT_HD2967",
        category="Cereal",
        msp_price_inr=2275.0,
        optimal_moisture_pct=12.0,
        max_moisture_pct=14.0,
        is_active=True
    )
    db_session.add(crop)
    db_session.commit()

    farmer_1 = Farmer(
        farmer_id=101,
        aadhaar_hash="aadhaar_sec_101",
        name="Balvinder Singh",
        mobile_number="9876543210",
        bank_account_hash="bank_sec_101",
        ifsc_code="SBIN0001042",
        land_area_hectares=5.0,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=500.0
    )
    farmer_2 = Farmer(
        farmer_id=102,
        aadhaar_hash="aadhaar_sec_102",
        name="Gurpreet Singh",
        mobile_number="9876543211",
        bank_account_hash="bank_sec_102",
        ifsc_code="SBIN0001042",
        land_area_hectares=4.0,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=400.0
    )
    db_session.add(farmer_1)
    db_session.add(farmer_2)
    db_session.commit()

    slot_1 = ProcurementSlot(
        slot_id=1,
        mandi_id=1,
        scheduled_date=date(2026, 11, 20),
        start_time=datetime.strptime("09:00:00", "%H:%M:%S").time(),
        end_time=datetime.strptime("10:00:00", "%H:%M:%S").time(),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=50.0,
        version=1
    )
    slot_2 = ProcurementSlot(
        slot_id=2,
        mandi_id=2,
        scheduled_date=date(2026, 11, 20),
        start_time=datetime.strptime("09:00:00", "%H:%M:%S").time(),
        end_time=datetime.strptime("10:00:00", "%H:%M:%S").time(),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=60.0,
        version=1
    )
    db_session.add(slot_1)
    db_session.add(slot_2)
    db_session.commit()

    # Active transaction in Mandi 1 belonging to Farmer 1
    txn_1 = ProcurementLog(
        transaction_id="TXN-SEC-M1-001",
        farmer_id=101,
        mandi_id=1,
        slot_id=1,
        scheduled_date=date(2026, 11, 20),
        crop_type="Wheat (HD-2967)",
        crop_moisture_pct=12.5,
        net_weight_qt=50.0,
        gross_weight_qt=70.0,
        tare_weight_qt=20.0,
        current_state="QUALITY_APPROVED",
        token_signature="test_sig_sec_1",
        created_at=datetime.now(timezone.utc)
    )
    # Active transaction in Mandi 2 belonging to Farmer 2
    txn_2 = ProcurementLog(
        transaction_id="TXN-SEC-M2-002",
        farmer_id=102,
        mandi_id=2,
        slot_id=2,
        scheduled_date=date(2026, 11, 20),
        crop_type="Wheat (HD-2967)",
        crop_moisture_pct=13.0,
        net_weight_qt=60.0,
        gross_weight_qt=85.0,
        tare_weight_qt=25.0,
        current_state="QUALITY_APPROVED",
        token_signature="test_sig_sec_2",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(txn_1)
    db_session.add(txn_2)
    db_session.commit()

    # Queue them in queue_manager
    queue_manager.clear(1)
    queue_manager.clear(2)
    queue_manager.enqueue(1, "TXN-SEC-M1-001", 55.0, arrival_ts=time.time() - 300)
    queue_manager.enqueue(2, "TXN-SEC-M2-002", 60.0, arrival_ts=time.time() - 300)

    # Users
    op_mandi_1 = User(
        username="op_mandi_1",
        hashed_password="pw",
        full_name="Operator Mandi 1",
        role="OPERATOR",
        mandi_id=1,
        is_active=True
    )
    admin_user = User(
        username="admin_sec",
        hashed_password="pw",
        full_name="System Admin",
        role="ADMIN",
        mandi_id=None,
        is_active=True
    )
    farmer_1_user = User(
        username="farmer_101",
        hashed_password="pw",
        full_name="Balvinder Singh",
        role="FARMER",
        farmer_id=101,
        is_active=True
    )
    farmer_2_user = User(
        username="farmer_102",
        hashed_password="pw",
        full_name="Gurpreet Singh",
        role="FARMER",
        farmer_id=102,
        is_active=True
    )
    db_session.add(op_mandi_1)
    db_session.add(admin_user)
    db_session.add(farmer_1_user)
    db_session.add(farmer_2_user)
    db_session.commit()

    return {
        "mandi_1": mandi_1,
        "mandi_2": mandi_2,
        "txn_1": txn_1,
        "txn_2": txn_2,
        "op_m1_token": create_access_jwt({"sub": str(op_mandi_1.user_id), "role": "OPERATOR", "mandi_id": 1}),
        "admin_token": create_access_jwt({"sub": str(admin_user.user_id), "role": "ADMIN"}),
        "farmer_1_token": create_access_jwt({"sub": str(farmer_1_user.user_id), "role": "FARMER", "farmer_id": 101}),
        "farmer_2_token": create_access_jwt({"sub": str(farmer_2_user.user_id), "role": "FARMER", "farmer_id": 102}),
    }


def test_unauthenticated_queue_read_returns_401(client: TestClient, queue_sec_env):
    """
    Test 1: Unauthenticated queue read endpoints strictly return 401 Unauthorized.
    """
    # 1. GET /api/v1/queue/state without auth
    resp = client.get("/api/v1/queue/state")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    # 2. GET /api/v1/queue/{mandi_id} without auth
    resp = client.get("/api/v1/queue/1")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    # 3. GET /api/v1/queue/{mandi_id}/status/{txn_id} without auth
    resp = client.get("/api/v1/queue/1/status/TXN-SEC-M1-001")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    # 4. POST /api/v1/queue/{mandi_id}/dispatch without auth
    resp = client.post("/api/v1/queue/1/dispatch")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    # 5. POST /api/v1/queue/{mandi_id}/rerank without auth
    resp = client.post("/api/v1/queue/1/rerank")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_mandi_1_operator_accessing_mandi_2_queue_returns_403(client: TestClient, queue_sec_env):
    """
    Test 2: Mandi-1 operator cannot access Mandi-2 queue (HTTP 403 Forbidden).
    Admin has cross-mandi authority and succeeds (HTTP 200).
    """
    op_m1_headers = {"Authorization": f"Bearer {queue_sec_env['op_m1_token']}"}
    admin_headers = {"Authorization": f"Bearer {queue_sec_env['admin_token']}"}

    # Mandi 1 Operator accessing Mandi 1 -> 200 OK
    resp = client.get("/api/v1/queue/1", headers=op_m1_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # Mandi 1 Operator accessing Mandi 2 -> 403 Forbidden
    resp = client.get("/api/v1/queue/2", headers=op_m1_headers)
    assert resp.status_code == 403
    assert "cannot perform read queue on Mandi 2" in resp.json()["detail"]

    # Mandi 1 Operator accessing /queue/state?mandi_id=2 -> 403 Forbidden
    resp = client.get("/api/v1/queue/state?mandi_id=2", headers=op_m1_headers)
    assert resp.status_code == 403

    # Mandi 1 Operator dispatching Mandi 2 -> 403 Forbidden
    resp = client.post("/api/v1/queue/2/dispatch", headers=op_m1_headers)
    assert resp.status_code == 403

    # Mandi 1 Operator reranking Mandi 2 -> 403 Forbidden
    resp = client.post("/api/v1/queue/2/rerank", headers=op_m1_headers)
    assert resp.status_code == 403

    # Admin accessing Mandi 2 queue -> 200 OK
    resp = client.get("/api/v1/queue/2", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # Admin accessing /queue/state?mandi_id=2 -> 200 OK
    resp = client.get("/api/v1/queue/state?mandi_id=2", headers=admin_headers)
    assert resp.status_code == 200


def test_farmer_cannot_access_general_queue(client: TestClient, queue_sec_env):
    """
    Test 3: Farmer role is strictly prohibited from accessing general queue listings (HTTP 403).
    """
    farmer_1_headers = {"Authorization": f"Bearer {queue_sec_env['farmer_1_token']}"}

    # Farmer accessing /queue/1 -> 403 Forbidden
    resp = client.get("/api/v1/queue/1", headers=farmer_1_headers)
    assert resp.status_code == 403
    assert "not authorized for this operation" in resp.json()["detail"]

    # Farmer accessing /queue/state -> 403 Forbidden
    resp = client.get("/api/v1/queue/state", headers=farmer_1_headers)
    assert resp.status_code == 403


def test_farmer_can_read_own_vehicle_status(client: TestClient, queue_sec_env):
    """
    Test 4: Farmer can read queue rank and priority score for their own transaction.
    """
    farmer_1_headers = {"Authorization": f"Bearer {queue_sec_env['farmer_1_token']}"}

    # Farmer 101 querying own transaction TXN-SEC-M1-001 in Mandi 1 -> 200 OK
    resp = client.get("/api/v1/queue/1/status/TXN-SEC-M1-001", headers=farmer_1_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_id"] == "TXN-SEC-M1-001"
    assert data["mandi_id"] == 1
    assert data["in_queue"] is True
    assert data["rank"] == 1


def test_farmer_cannot_read_other_farmer_transaction_status(client: TestClient, queue_sec_env):
    """
    Test 5: Farmer cannot read queue rank or status for another farmer's transaction (HTTP 403 Forbidden).
    """
    farmer_2_headers = {"Authorization": f"Bearer {queue_sec_env['farmer_2_token']}"}

    # Farmer 102 querying Farmer 101's transaction TXN-SEC-M1-001 in Mandi 1 -> 403 Forbidden
    resp = client.get("/api/v1/queue/1/status/TXN-SEC-M1-001", headers=farmer_2_headers)
    assert resp.status_code == 403
    assert "Authenticated farmer ID (102) does not match transaction farmer ID (101)" in resp.json()["detail"]


def test_offline_dispatch_wal_sync_transitions_to_routed_to_weighbridge(client: TestClient, db_session: Session, queue_sec_env):
    """
    Test 6: Offline dispatch WAL mutation synchronizes via /api/v1/sync/wal:
    - Authoritative lifecycle state transitions to ROUTED_TO_WEIGHBRIDGE
    - Dispatched transaction is evicted from Redis active queue
    """
    op_m1_headers = {"Authorization": f"Bearer {queue_sec_env['op_m1_token']}"}

    # Verify initially in queue
    assert queue_manager.get_score(1, "TXN-SEC-M1-001") is not None

    wal_mutation = {
        "client_mutation_id": "mut-offline-dispatch-001",
        "transaction_id": "TXN-SEC-M1-001",
        "farmer_id": 101,
        "mandi_id": 1,
        "current_state": "ROUTED_TO_WEIGHBRIDGE",
        "payload": {"dispatched_at": datetime.now(timezone.utc).isoformat(), "priority_score": 55.0},
        "payload_json": "{}",
        "hmac_signature": "LOCAL_HMAC_SIG_OFFLINE_001",
        "client_timestamp": int(time.time() * 1000)
    }

    resp = client.post(
        "/api/v1/sync/wal",
        headers=op_m1_headers,
        json={"mutations": [wal_mutation]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["synced_count"] == 1
    assert body["results"][0]["status"] in ("SYNCED", "CONFLICT_RESOLVED")
    assert body["results"][0]["current_state"] == "ROUTED_TO_WEIGHBRIDGE"

    # Verify DB transaction state
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == "TXN-SEC-M1-001").first()
    assert log.current_state == "ROUTED_TO_WEIGHBRIDGE"

    # Verify vehicle was evicted from queue
    assert queue_manager.get_score(1, "TXN-SEC-M1-001") is None


def test_duplicate_wal_replay_is_idempotent(client: TestClient, db_session: Session, queue_sec_env):
    """
    Test 7: Duplicate replay of an offline dispatch WAL mutation is idempotent:
    Returns IGNORED_DUPLICATE without errors or secondary state mutations.
    """
    op_m1_headers = {"Authorization": f"Bearer {queue_sec_env['op_m1_token']}"}

    wal_mutation = {
        "client_mutation_id": "mut-offline-dispatch-replay-002",
        "transaction_id": "TXN-SEC-M1-001",
        "farmer_id": 101,
        "mandi_id": 1,
        "current_state": "ROUTED_TO_WEIGHBRIDGE",
        "payload": {"dispatched_at": datetime.now(timezone.utc).isoformat()},
        "payload_json": "{}",
        "hmac_signature": "LOCAL_HMAC_SIG_OFFLINE_002",
        "client_timestamp": int(time.time() * 1000)
    }

    # First sync
    resp1 = client.post("/api/v1/sync/wal", headers=op_m1_headers, json={"mutations": [wal_mutation]})
    assert resp1.status_code == 200

    # Second sync (replay of identical mutation ID)
    resp2 = client.post("/api/v1/sync/wal", headers=op_m1_headers, json={"mutations": [wal_mutation]})
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["results"][0]["status"] == "IGNORED_DUPLICATE"
    assert "already processed" in body2["results"][0]["message"]


def test_server_rejection_marks_conflict(client: TestClient, db_session: Session, queue_sec_env):
    """
    Test 8: Server rejection for an invalid lifecycle transition returns REJECTED
    and preserves original state.
    """
    op_m1_headers = {"Authorization": f"Bearer {queue_sec_env['op_m1_token']}"}

    # Put a transaction in QUALITY_REJECTED state
    rejected_txn = ProcurementLog(
        transaction_id="TXN-SEC-REJECTED-003",
        farmer_id=101,
        mandi_id=1,
        slot_id=1,
        scheduled_date=date(2026, 11, 20),
        crop_type="Wheat (HD-2967)",
        crop_moisture_pct=18.5,
        net_weight_qt=40.0,
        current_state="QUALITY_REJECTED",
        token_signature="test_sig_sec_3",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(rejected_txn)
    db_session.commit()

    # Attempt illegal offline dispatch from QUALITY_REJECTED -> ROUTED_TO_WEIGHBRIDGE
    wal_mutation = {
        "client_mutation_id": "mut-illegal-transition-003",
        "transaction_id": "TXN-SEC-REJECTED-003",
        "farmer_id": 101,
        "mandi_id": 1,
        "current_state": "ROUTED_TO_WEIGHBRIDGE",
        "payload": {},
        "payload_json": "{}",
        "hmac_signature": "SIG_ILLEGAL_003",
        "client_timestamp": int(time.time() * 1000)
    }

    resp = client.post("/api/v1/sync/wal", headers=op_m1_headers, json={"mutations": [wal_mutation]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["results"][0]["status"] == "REJECTED"
    assert "Lifecycle transition rejected" in body["results"][0]["message"]

    # Ensure DB transaction is still in QUALITY_REJECTED
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == "TXN-SEC-REJECTED-003").first()
    assert log.current_state == "QUALITY_REJECTED"
