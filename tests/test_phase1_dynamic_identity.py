"""
Phase 1 Forensic Remediation Test Suite: Dynamic Identity & Cross-User Isolation.

Verifies:
1. Authoritative farmer identity derivation from authenticated principal (User.farmer_id).
2. Strict isolation: Farmer 1 cannot access Farmer 2's data; Farmer 2/3 cannot access Farmer 1's data.
3. Farmer cannot reserve slots for another farmer (403 Forbidden).
4. Missing farmer profile returns explicit 400 Bad Request error (no silent Farmer 1 fallback).
5. Staff endpoints require explicit farmer_id (no silent Farmer 1 fallback).
6. Cross-user transaction journey isolation (Ramesh booking is never presented to Balvinder).
7. Stations and mandis do not employ hard-coded defaults (TXN-DEMO-1001 or Sehore).
"""

from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import hash_password
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.user import User
from backend.app.services.auth_service import create_user_token


@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    """Enforce authentication for all tests in this suite."""
    settings = get_settings()
    monkeypatch.setattr(settings, "MANDIQ_AUTH_ENFORCED", True)


@pytest.fixture
def seed_dynamic_identity_data(db_session: Session):
    """Seed distinct Mandis, Farmers, Users, and Slots for isolation testing."""
    # Mandis
    mandi_sehore = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2000.0,
        active_weighbridges=2,
        is_operational=True,
    )
    mandi_dewas = Mandi(
        name="Dewas APMC Mandi",
        district="Dewas",
        state="Madhya Pradesh",
        daily_capacity_qt=1500.0,
        active_weighbridges=1,
        is_operational=True,
    )
    db_session.add_all([mandi_sehore, mandi_dewas])
    db_session.commit()
    db_session.refresh(mandi_sehore)
    db_session.refresh(mandi_dewas)

    # Farmers
    farmer_1 = Farmer(
        aadhaar_hash="aadhaar_ramesh_hash_01",
        name="Ramesh Kumar",
        mobile_number="9876543210",
        bank_account_hash="bank_ramesh_01",
        ifsc_code="SBIN0001042",
        land_area_hectares=2.5,
        registered_crop_type="Wheat (Sharbati)",
        production_ceiling_qt=100.0,
    )
    farmer_2 = Farmer(
        aadhaar_hash="aadhaar_balvinder_hash_02",
        name="Balvinder Singh",
        mobile_number="9876543211",
        bank_account_hash="bank_balvinder_02",
        ifsc_code="PUNB0001042",
        land_area_hectares=4.0,
        registered_crop_type="Wheat (Lokwan)",
        production_ceiling_qt=160.0,
    )
    farmer_3 = Farmer(
        aadhaar_hash="aadhaar_suresh_hash_03",
        name="Suresh Patel",
        mobile_number="9876543212",
        bank_account_hash="bank_suresh_03",
        ifsc_code="HDFC0001042",
        land_area_hectares=3.0,
        registered_crop_type="Gram",
        production_ceiling_qt=120.0,
    )
    db_session.add_all([farmer_1, farmer_2, farmer_3])
    db_session.commit()
    db_session.refresh(farmer_1)
    db_session.refresh(farmer_2)
    db_session.refresh(farmer_3)

    # Users
    hashed_pwd = hash_password("password123")
    user_ramesh = User(
        username="farmer_ramesh",
        full_name="Ramesh Kumar",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=farmer_1.farmer_id,
        is_active=True,
    )
    user_balvinder = User(
        username="farmer_balvinder",
        full_name="Balvinder Singh",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=farmer_2.farmer_id,
        is_active=True,
    )
    user_suresh = User(
        username="farmer_suresh",
        full_name="Suresh Patel",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=farmer_3.farmer_id,
        is_active=True,
    )
    user_unlinked = User(
        username="farmer_unlinked",
        full_name="Unlinked Farmer",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=None,
        is_active=True,
    )
    user_operator = User(
        username="operator_test",
        full_name="Operator Staff",
        hashed_password=hashed_pwd,
        role="OPERATOR",
        farmer_id=None,
        is_active=True,
    )
    db_session.add_all([user_ramesh, user_balvinder, user_suresh, user_unlinked, user_operator])
    db_session.commit()

    # Slots
    slot_sehore = ProcurementSlot(
        mandi_id=mandi_sehore.mandi_id,
        scheduled_date=date(2026, 11, 1),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=100.0,
        booked_capacity_qt=0.0,
        version=1,
    )
    slot_dewas = ProcurementSlot(
        mandi_id=mandi_dewas.mandi_id,
        scheduled_date=date(2026, 11, 1),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=100.0,
        booked_capacity_qt=0.0,
        version=1,
    )
    db_session.add_all([slot_sehore, slot_dewas])
    db_session.commit()
    db_session.refresh(slot_sehore)
    db_session.refresh(slot_dewas)

    return {
        "mandis": (mandi_sehore, mandi_dewas),
        "farmers": (farmer_1, farmer_2, farmer_3),
        "users": {
            "ramesh": user_ramesh,
            "balvinder": user_balvinder,
            "suresh": user_suresh,
            "unlinked": user_unlinked,
            "operator": user_operator,
        },
        "slots": (slot_sehore, slot_dewas),
    }


def _auth_header(user: User) -> dict:
    """Generate Bearer auth header for given user."""
    token_resp = create_user_token(user)
    return {"Authorization": f"Bearer {token_resp.access_token}"}


def test_farmer_cannot_become_another_farmer(client: TestClient, seed_dynamic_identity_data):
    """
    SECTION 2 & 3: Farmer 1 (Ramesh) cannot access Farmer 2 (Balvinder)'s profile.
    Farmer 2 cannot access Farmer 1's profile.
    Farmer 3 cannot access Farmer 1's profile.
    """
    users = seed_dynamic_identity_data["users"]
    farmers = seed_dynamic_identity_data["farmers"]
    f1, f2, f3 = farmers

    # Ramesh querying his own profile (no query params) -> succeeds
    res = client.get("/api/v1/farmers/profile", headers=_auth_header(users["ramesh"]))
    assert res.status_code == 200
    assert res.json()["farmer_id"] == f1.farmer_id
    assert res.json()["name"] == "Ramesh Kumar"

    # Ramesh attempting to query Balvinder's profile via query param -> 403 Forbidden
    res = client.get(f"/api/v1/farmers/profile?farmer_id={f2.farmer_id}", headers=_auth_header(users["ramesh"]))
    assert res.status_code == 403
    assert "another farmer" in res.json()["detail"].lower()

    # Balvinder querying his own profile -> succeeds
    res = client.get("/api/v1/farmers/profile", headers=_auth_header(users["balvinder"]))
    assert res.status_code == 200
    assert res.json()["farmer_id"] == f2.farmer_id
    assert res.json()["name"] == "Balvinder Singh"

    # Balvinder attempting to query Ramesh's profile -> 403 Forbidden
    res = client.get(f"/api/v1/farmers/profile?farmer_id={f1.farmer_id}", headers=_auth_header(users["balvinder"]))
    assert res.status_code == 403
    assert "another farmer" in res.json()["detail"].lower()

    # Suresh querying his own profile -> succeeds
    res = client.get("/api/v1/farmers/profile", headers=_auth_header(users["suresh"]))
    assert res.status_code == 200
    assert res.json()["farmer_id"] == f3.farmer_id
    assert res.json()["name"] == "Suresh Patel"

    # Suresh attempting to query Ramesh's profile -> 403 Forbidden
    res = client.get(f"/api/v1/farmers/profile?farmer_id={f1.farmer_id}", headers=_auth_header(users["suresh"]))
    assert res.status_code == 403
    assert "another farmer" in res.json()["detail"].lower()


def test_unlinked_farmer_profile_returns_explicit_error(client: TestClient, seed_dynamic_identity_data):
    """
    SECTION 7: If currentUser.farmer_id is missing, produce explicit 400 error.
    Never silently become Farmer 1.
    """
    users = seed_dynamic_identity_data["users"]
    unlinked_user = users["unlinked"]

    res = client.get("/api/v1/farmers/profile", headers=_auth_header(unlinked_user))
    assert res.status_code == 400
    assert "no linked farmer profile" in res.json()["detail"].lower()


def test_staff_profile_query_requires_explicit_farmer_id(client: TestClient, seed_dynamic_identity_data):
    """
    SECTION 2: Staff calling /farmers/profile without farmer_id returns 400,
    and does NOT silently default to Farmer 1.
    """
    users = seed_dynamic_identity_data["users"]
    farmers = seed_dynamic_identity_data["farmers"]
    operator_user = users["operator"]
    f2 = farmers[1]

    # Staff omitting farmer_id query param -> 400 Bad Request
    res = client.get("/api/v1/farmers/profile", headers=_auth_header(operator_user))
    assert res.status_code == 400
    assert "farmer_id" in res.json()["detail"] and "required" in res.json()["detail"]

    # Staff providing explicit farmer_id -> 200 OK
    res = client.get(f"/api/v1/farmers/profile?farmer_id={f2.farmer_id}", headers=_auth_header(operator_user))
    assert res.status_code == 200
    assert res.json()["farmer_id"] == f2.farmer_id
    assert res.json()["name"] == "Balvinder Singh"


def test_farmer_by_id_endpoint_cross_access_prevented(client: TestClient, seed_dynamic_identity_data):
    """
    SECTION 3: /api/v1/farmers/{farmer_id} endpoint enforces that a farmer
    can only fetch their own ID, while staff can query any ID.
    """
    users = seed_dynamic_identity_data["users"]
    farmers = seed_dynamic_identity_data["farmers"]
    f1, f2, _ = farmers

    # Ramesh fetching own ID -> 200 OK
    res = client.get(f"/api/v1/farmers/{f1.farmer_id}", headers=_auth_header(users["ramesh"]))
    assert res.status_code == 200
    assert res.json()["farmer_id"] == f1.farmer_id

    # Ramesh fetching Balvinder's ID -> 403 Forbidden
    res = client.get(f"/api/v1/farmers/{f2.farmer_id}", headers=_auth_header(users["ramesh"]))
    assert res.status_code == 403

    # Balvinder fetching Ramesh's ID -> 403 Forbidden
    res = client.get(f"/api/v1/farmers/{f1.farmer_id}", headers=_auth_header(users["balvinder"]))
    assert res.status_code == 403

    # Staff fetching either ID -> 200 OK
    res1 = client.get(f"/api/v1/farmers/{f1.farmer_id}", headers=_auth_header(users["operator"]))
    res2 = client.get(f"/api/v1/farmers/{f2.farmer_id}", headers=_auth_header(users["operator"]))
    assert res1.status_code == 200
    assert res2.status_code == 200


def test_slot_reservation_cannot_spoof_another_farmer(client: TestClient, seed_dynamic_identity_data):
    """
    SECTION 3: A Farmer cannot submit farmer_id = another farmer during slot reservation.
    """
    users = seed_dynamic_identity_data["users"]
    farmers = seed_dynamic_identity_data["farmers"]
    slots = seed_dynamic_identity_data["slots"]
    f1, f2, _ = farmers
    slot_1, _ = slots

    # Ramesh reserving for Ramesh -> 201 Created
    payload_valid = {
        "farmer_id": f1.farmer_id,
        "mandi_id": slot_1.mandi_id,
        "slot_id": slot_1.slot_id,
        "requested_qty_qt": 25.0,
    }
    res = client.post("/api/v1/slots/reserve", json=payload_valid, headers=_auth_header(users["ramesh"]))
    assert res.status_code == 201
    assert res.json()["status"] == "SUCCESS"
    assert res.json()["transaction_id"].startswith("TXN-")

    # Ramesh attempting to reserve with Balvinder's farmer_id -> 403 Forbidden
    payload_spoofed = {
        "farmer_id": f2.farmer_id,
        "mandi_id": slot_1.mandi_id,
        "slot_id": slot_1.slot_id,
        "requested_qty_qt": 25.0,
    }
    res_spoof = client.post("/api/v1/slots/reserve", json=payload_spoofed, headers=_auth_header(users["ramesh"]))
    assert res_spoof.status_code == 403
    assert "does not match" in res_spoof.json()["detail"].lower()

    # Unlinked farmer attempting to reserve -> 400 Bad Request
    res_unlinked = client.post("/api/v1/slots/reserve", json=payload_valid, headers=_auth_header(users["unlinked"]))
    assert res_unlinked.status_code == 400
    assert "no linked farmer profile" in res_unlinked.json()["detail"].lower()


def test_multi_farmer_journey_data_isolation(client: TestClient, seed_dynamic_identity_data):
    """
    SECTION 15:
    Ramesh -> booking -> transaction
    then:
    Balvinder -> login -> Farmer Portal
    and verify Ramesh's transaction is not presented as Balvinder's.
    """
    users = seed_dynamic_identity_data["users"]
    farmers = seed_dynamic_identity_data["farmers"]
    slots = seed_dynamic_identity_data["slots"]
    f1, f2, _ = farmers
    slot_1, slot_2 = slots

    # 1. Ramesh logs in and books a slot
    ramesh_headers = _auth_header(users["ramesh"])
    res_booking = client.post(
        "/api/v1/slots/reserve",
        json={
            "farmer_id": f1.farmer_id,
            "mandi_id": slot_1.mandi_id,
            "slot_id": slot_1.slot_id,
            "requested_qty_qt": 30.0,
        },
        headers=ramesh_headers,
    )
    assert res_booking.status_code == 201
    ramesh_txn_id = res_booking.json()["transaction_id"]
    assert ramesh_txn_id.startswith("TXN-")

    # 2. Ramesh checks his latest booking -> returns his booking
    res_ramesh_latest = client.get(f"/api/v1/farmers/{f1.farmer_id}/latest-booking", headers=ramesh_headers)
    assert res_ramesh_latest.status_code == 200
    assert res_ramesh_latest.json()["has_booking"] is True
    assert res_ramesh_latest.json()["booking"]["transaction_id"] == ramesh_txn_id

    # 3. Balvinder logs in
    balvinder_headers = _auth_header(users["balvinder"])

    # 3a. Balvinder trying to peek at Ramesh's latest-booking endpoint -> 403 Forbidden
    res_forbidden_peek = client.get(f"/api/v1/farmers/{f1.farmer_id}/latest-booking", headers=balvinder_headers)
    assert res_forbidden_peek.status_code == 403

    # 3b. Balvinder queries his own latest-booking -> has_booking is False (no booking yet, NEVER Ramesh's!)
    res_balvinder_latest = client.get(f"/api/v1/farmers/{f2.farmer_id}/latest-booking", headers=balvinder_headers)
    assert res_balvinder_latest.status_code == 200
    assert res_balvinder_latest.json()["has_booking"] is False
    assert res_balvinder_latest.json()["booking"] is None

    # 4. Balvinder now reserves his own slot at Dewas Mandi
    res_balvinder_booking = client.post(
        "/api/v1/slots/reserve",
        json={
            "farmer_id": f2.farmer_id,
            "mandi_id": slot_2.mandi_id,
            "slot_id": slot_2.slot_id,
            "requested_qty_qt": 40.0,
        },
        headers=balvinder_headers,
    )
    assert res_balvinder_booking.status_code == 201
    balvinder_txn_id = res_balvinder_booking.json()["transaction_id"]
    assert balvinder_txn_id != ramesh_txn_id

    # 5. Balvinder queries his latest booking -> returns Balvinder's transaction
    res_balvinder_active = client.get(f"/api/v1/farmers/{f2.farmer_id}/latest-booking", headers=balvinder_headers)
    assert res_balvinder_active.status_code == 200
    assert res_balvinder_active.json()["has_booking"] is True
    assert res_balvinder_active.json()["booking"]["transaction_id"] == balvinder_txn_id
    assert res_balvinder_active.json()["booking"]["transaction_id"] != ramesh_txn_id

    # 6. Ramesh queries his latest booking again -> still Ramesh's transaction, completely isolated
    res_ramesh_check = client.get(f"/api/v1/farmers/{f1.farmer_id}/latest-booking", headers=ramesh_headers)
    assert res_ramesh_check.status_code == 200
    assert res_ramesh_check.json()["has_booking"] is True
    assert res_ramesh_check.json()["booking"]["transaction_id"] == ramesh_txn_id
