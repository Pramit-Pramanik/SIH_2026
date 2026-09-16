from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_jwt
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.auth_service import ensure_default_operational_users


@pytest.fixture
def seed_wal_test_data(db_session: Session):
    ensure_default_operational_users(db_session)

    mandi = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    db_session.add(mandi)
    db_session.commit()
    db_session.refresh(mandi)

    farmer = Farmer(
        name="Ramesh Kumar",
        aadhaar_hash="sha256_hash_wal_1",
        mobile_number="9876543210",
        land_area_hectares=4.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.0,
        bank_account_hash="sha256_bank_wal_1",
        ifsc_code="SBIN0001234"
    )
    db_session.add(farmer)
    db_session.commit()
    db_session.refresh(farmer)

    return {"mandi": mandi, "farmer": farmer}


def test_wal_sync_handles_permanent_domain_rejection(client: TestClient, seed_wal_test_data):
    """
    Verifies that WAL mutations with non-existent foreign keys or invalid domain parameters
    are rejected with status REJECTED (so client marks as permanent FAILED, not infinite retry).
    """
    token = create_access_jwt(data={"sub": "operator", "role": "OPERATOR", "user_id": 4})
    headers = {"Authorization": f"Bearer {token}"}

    # Mutation referencing non-existent farmer_id 99999
    bad_mutation = {
        "client_mutation_id": "mut-bad-farmer-99999",
        "transaction_id": "txn-wal-test-001",
        "farmer_id": 99999,
        "mandi_id": seed_wal_test_data["mandi"].mandi_id,
        "current_state": "GATE_ENTRY_VERIFIED",
        "hmac_signature": "0" * 64,
        "client_timestamp": 1700000000.0,
        "mutation_type": "GATE_ENTRY_VERIFIED"
    }

    res = client.post("/api/v1/sync/wal", json={"mutations": [bad_mutation]}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["status"] == "REJECTED"
    assert "Farmer" in result["message"] or "not found" in result["message"].lower()


def test_wal_sync_malformed_json_returns_400(client: TestClient, seed_wal_test_data):
    """
    Verifies that malformed JSON or corrupted Gzip payloads return HTTP 400.
    """
    token = create_access_jwt(data={"sub": "operator", "role": "OPERATOR", "user_id": 4})
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    res = client.post("/api/v1/sync/wal", content=b"{malformed json...", headers=headers)
    assert res.status_code == 400


def test_wal_sync_invalid_schema_returns_422(client: TestClient, seed_wal_test_data):
    """
    Verifies that schema violations return HTTP 422.
    """
    token = create_access_jwt(data={"sub": "operator", "role": "OPERATOR", "user_id": 4})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/v1/sync/wal", json="not an object or list", headers=headers)
    assert res.status_code == 422
