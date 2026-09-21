"""
MandiQ Offline WAL Synchronization & Authentication Recovery Test Suite.
Verifies backend invariants for ADR-002 offline WAL sync:
1. Offline provisional tokens (offline_pwa_token_*) MUST be rejected with HTTP 401.
2. Valid operator/supervisor/admin JWTs are accepted with HTTP 200 SYNCED.
3. Idempotent replay returns HTTP 200 IGNORED_DUPLICATE with preserved sequence.
4. Invalid domain mutations (e.g. non-existent foreign key) return HTTP 200 REJECTED.
5. Unauthorized roles (e.g. FARMER) receive HTTP 403 Forbidden.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from datetime import date
from backend.app.models.log import ProcurementLog
from backend.app.core.security import create_access_jwt
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.user import User
from backend.app.services.auth_service import ensure_default_operational_users
from backend.app.services.sync_service import _processed_mutations


def setup_wal_fixture(db: Session):
    _processed_mutations.clear()
    ensure_default_operational_users(db)

    mandi = Mandi(
        name="Karnal APMC Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=8000.0,
        active_weighbridges=2,
        is_operational=True
    )
    farmer = Farmer(
        name="Sukhwinder Singh",
        aadhaar_hash="aadhaar_hash_wal_recovery_01",
        mobile_number="9876543210",
        land_area_hectares=4.5,
        registered_crop_type="Paddy",
        production_ceiling_qt=120.0,
        bank_account_hash="bank_hash_wal_recovery_01",
        ifsc_code="SBIN0001001"
    )
    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    operator_user = db.query(User).filter(User.username == "operator").first()
    farmer_user = db.query(User).filter(User.username == "farmer").first()

    operator_jwt = create_access_jwt({
        "sub": str(operator_user.user_id),
        "user_id": operator_user.user_id,
        "username": operator_user.username,
        "role": operator_user.role,
        "mandi_id": mandi.mandi_id
    })
    farmer_jwt = create_access_jwt({
        "sub": str(farmer_user.user_id),
        "user_id": farmer_user.user_id,
        "username": farmer_user.username,
        "role": farmer_user.role
    })

    return mandi, farmer, operator_jwt, farmer_jwt


def test_sync_wal_rejects_offline_provisional_tokens(client: TestClient, db_session: Session):
    """
    Offline provisional tokens (offline_pwa_token_*) must fail closed with HTTP 401
    when submitted to /api/v1/sync/wal.
    """
    mandi, farmer, _, _ = setup_wal_fixture(db_session)

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-offline-token-01",
                "transaction_id": "TXN-OFFLINE-01",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "hmac_signature": "SIG_TEST_01",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_ENTRY_VERIFIED"
            }
        ]
    }

    # 1. Offline token from provisional farmer login
    r1 = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": "Bearer offline_pwa_token_farmer_1726000000"},
        json=payload
    )
    assert r1.status_code == 401
    assert "offline provisional" in r1.json()["detail"].lower()

    # 2. Offline token claiming operator
    r2 = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": "Bearer offline_pwa_token_operator_1726000000"},
        json=payload
    )
    assert r2.status_code == 401
    assert "offline provisional" in r2.json()["detail"].lower()


def test_sync_wal_accepts_valid_operator_jwt(client: TestClient, db_session: Session):
    """
    Once user is re-authenticated with a genuine server JWT, /sync/wal processes mutations
    and returns HTTP 200 with status SYNCED for an existing transaction.
    """
    mandi, farmer, operator_jwt, _ = setup_wal_fixture(db_session)

    init_log = ProcurementLog(
        transaction_id="TXN-VALID-01",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        crop_type="Paddy",
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="SIG_VALID_INIT"
    )
    db_session.add(init_log)
    db_session.commit()

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-valid-jwt-01",
                "transaction_id": "TXN-VALID-01",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 2, "verified_by": "OPERATOR_KARNAL"},
                "hmac_signature": "HMAC_SIG_VALID_01",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_ENTRY_VERIFIED"
            }
        ]
    }

    response = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {operator_jwt}"},
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] == "SYNCED"
    assert data["results"][0]["server_receive_sequence"] > 0


def test_sync_wal_idempotent_duplicate_replay(client: TestClient, db_session: Session):
    """
    Replaying an already synchronized mutation returns HTTP 200 IGNORED_DUPLICATE
    with the previously assigned sequence number preserved.
    """
    mandi, farmer, operator_jwt, _ = setup_wal_fixture(db_session)

    init_log = ProcurementLog(
        transaction_id="TXN-IDEMPOTENT-01",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        crop_type="Paddy",
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="SIG_IDEM_INIT"
    )
    db_session.add(init_log)
    db_session.commit()

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-idempotent-01",
                "transaction_id": "TXN-IDEMPOTENT-01",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "hmac_signature": "HMAC_SIG_01",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_ENTRY_VERIFIED"
            }
        ]
    }

    # First attempt -> SYNCED
    r1 = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {operator_jwt}"},
        json=payload
    )
    assert r1.status_code == 200
    assert r1.json()["results"][0]["status"] == "SYNCED"
    assigned_seq = r1.json()["results"][0]["server_receive_sequence"]

    # Replay attempt -> IGNORED_DUPLICATE with same sequence
    r2 = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {operator_jwt}"},
        json=payload
    )
    assert r2.status_code == 200
    assert r2.json()["results"][0]["status"] == "IGNORED_DUPLICATE"
    assert r2.json()["results"][0]["server_receive_sequence"] == assigned_seq


def test_sync_wal_domain_rejection_marks_failed(client: TestClient, db_session: Session):
    """
    Under AUD-002, submitting mutations for a nonexistent transaction returns HTTP 404.
    If the transaction exists but the farmer does not match, returns HTTP 403.
    """
    mandi, farmer, operator_jwt, _ = setup_wal_fixture(db_session)

    # 1. Nonexistent transaction -> 404
    payload_nonexistent = {
        "mutations": [
            {
                "client_mutation_id": "mut-bad-domain-01",
                "transaction_id": "TXN-NONEXISTENT-999",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "hmac_signature": "HMAC_BAD",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_ENTRY_VERIFIED"
            }
        ]
    }

    response_404 = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {operator_jwt}"},
        json=payload_nonexistent
    )
    assert response_404.status_code == 404
    assert "authoritative transaction does not exist" in response_404.json()["detail"].lower()

    # 2. Existing transaction with wrong farmer -> 403
    init_log = ProcurementLog(
        transaction_id="TXN-BAD-01",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        crop_type="Paddy",
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="SIG_BAD_INIT"
    )
    db_session.add(init_log)
    db_session.commit()

    payload_wrong_farmer = {
        "mutations": [
            {
                "client_mutation_id": "mut-bad-domain-02",
                "transaction_id": "TXN-BAD-01",
                "farmer_id": 999999,  # Mismatched farmer
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "hmac_signature": "HMAC_BAD",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_ENTRY_VERIFIED"
            }
        ]
    }

    response_403 = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {operator_jwt}"},
        json=payload_wrong_farmer
    )
    assert response_403.status_code == 403
    assert "does not match transaction farmer id" in response_403.json()["detail"].lower()


def test_sync_wal_farmer_role_forbidden(client: TestClient, db_session: Session):
    """
    A user authenticated as FARMER is forbidden (HTTP 403) from invoking /sync/wal.
    """
    mandi, farmer, _, farmer_jwt = setup_wal_fixture(db_session)

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-farmer-sync-01",
                "transaction_id": "TXN-FARMER-01",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {},
                "hmac_signature": "SIG",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_ENTRY_VERIFIED"
            }
        ]
    }

    response = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {farmer_jwt}"},
        json=payload
    )
    assert response.status_code == 403
    assert "not authorized for this operation" in response.json()["detail"].lower()
