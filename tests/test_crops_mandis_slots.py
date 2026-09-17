from datetime import date, time
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
def seed_test_data(db_session: Session):
    # Mandis
    mandi1 = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    mandi2 = Mandi(
        name="Karnal Grain Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=15000.0,
        active_weighbridges=4,
        is_operational=True
    )
    db_session.add_all([mandi1, mandi2])
    db_session.commit()
    db_session.refresh(mandi1)
    db_session.refresh(mandi2)

    # Crops
    crop1 = Crop(
        crop_name="Wheat (HD-2967)",
        crop_code="WHEAT_HD2967",
        category="CEREAL",
        msp_price_inr=2275.0,
        optimal_moisture_pct=14.0,
        max_moisture_pct=17.0,
        is_active=True
    )
    crop2 = Crop(
        crop_name="Paddy (Basmati)",
        crop_code="PADDY_BASMATI",
        category="CEREAL",
        msp_price_inr=2320.0,
        optimal_moisture_pct=15.0,
        max_moisture_pct=17.0,
        is_active=True
    )
    db_session.add_all([crop1, crop2])
    db_session.commit()

    # Farmers
    farmer1 = Farmer(
        name="Ramesh Kumar",
        aadhaar_hash="sha256_hash_1",
        mobile_number="9876543210",
        land_area_hectares=4.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.0,
        bank_account_hash="sha256_bank_1",
        ifsc_code="SBIN0001234"
    )
    farmer2 = Farmer(
        name="Balvinder Singh",
        aadhaar_hash="sha256_hash_2",
        mobile_number="9876543211",
        land_area_hectares=6.4,
        registered_crop_type="Wheat",
        production_ceiling_qt=160.0,
        bank_account_hash="sha256_bank_2",
        ifsc_code="SBIN0001235"
    )
    db_session.add_all([farmer1, farmer2])
    db_session.commit()
    db_session.refresh(farmer1)
    db_session.refresh(farmer2)

    # Slots
    today = date.today()
    slot1 = ProcurementSlot(
        mandi_id=mandi1.mandi_id,
        scheduled_date=today,
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=200.0,
        booked_capacity_qt=0.0
    )
    db_session.add(slot1)
    db_session.commit()
    db_session.refresh(slot1)

    # Default users
    ensure_default_operational_users(db_session)

    return {
        "mandi1": mandi1,
        "mandi2": mandi2,
        "crop1": crop1,
        "farmer1": farmer1,
        "farmer2": farmer2,
        "slot1": slot1
    }


def test_list_and_get_mandis(client: TestClient, seed_test_data):
    # List active mandis
    res = client.get("/api/v1/mandis")
    assert res.status_code == 200
    mandis = res.json()
    assert len(mandis) >= 2
    mandi_names = [m["name"] for m in mandis]
    assert "Sehore APMC Mandi" in mandi_names
    assert "Karnal Grain Mandi" in mandi_names

    # Get single mandi
    mandi_id = seed_test_data["mandi1"].mandi_id
    res_single = client.get(f"/api/v1/mandis/{mandi_id}")
    assert res_single.status_code == 200
    data = res_single.json()
    assert data["name"] == "Sehore APMC Mandi"
    assert data["daily_capacity_qt"] > 0

    # Non-existent mandi
    res_404 = client.get("/api/v1/mandis/99999")
    assert res_404.status_code == 404


def test_list_and_get_crops(client: TestClient, seed_test_data):
    # List active crops
    res = client.get("/api/v1/crops")
    assert res.status_code == 200
    crops = res.json()
    assert len(crops) >= 2
    crop_codes = [c["crop_code"] for c in crops]
    assert "WHEAT_HD2967" in crop_codes

    wheat = next(c for c in crops if c["crop_code"] == "WHEAT_HD2967")
    assert wheat["msp_price_inr"] == 2275.00
    assert wheat["optimal_moisture_pct"] == 14.0
    assert wheat["max_moisture_pct"] == 17.0

    # Get single crop
    res_single = client.get(f"/api/v1/crops/{wheat['crop_id']}")
    assert res_single.status_code == 200
    assert res_single.json()["crop_name"] == wheat["crop_name"]

    # Non-existent crop
    res_404 = client.get("/api/v1/crops/99999")
    assert res_404.status_code == 404


def test_farmer_profile_endpoints(client: TestClient, seed_test_data):
    farmer1_id = seed_test_data["farmer1"].farmer_id
    farmer2_id = seed_test_data["farmer2"].farmer_id

    # Specific farmer by query param
    res_1 = client.get(f"/api/v1/farmers/profile?farmer_id={farmer1_id}")
    assert res_1.status_code == 200
    profile = res_1.json()
    assert profile["farmer_id"] == farmer1_id
    assert profile["name"] == "Ramesh Kumar"
    assert profile["production_ceiling_qt"] == 100.0
    assert profile["remaining_ceiling_qt"] == 100.0

    # Specific farmer by query param
    res_2 = client.get(f"/api/v1/farmers/profile?farmer_id={farmer2_id}")
    assert res_2.status_code == 200
    assert res_2.json()["name"] == "Balvinder Singh"
    assert res_2.json()["production_ceiling_qt"] == 160.0

    # Specific farmer by path
    res_path = client.get(f"/api/v1/farmers/{farmer1_id}")
    assert res_path.status_code == 200
    assert res_path.json()["farmer_id"] == farmer1_id

    # Non-existent farmer
    res_404 = client.get("/api/v1/farmers/99999")
    assert res_404.status_code == 404


def test_slots_listing(client: TestClient, seed_test_data):
    mandi_id = seed_test_data["mandi1"].mandi_id
    today = date.today().isoformat()
    res = client.get(f"/api/v1/slots?mandi_id={mandi_id}&scheduled_date={today}")
    assert res.status_code == 200
    slots = res.json()
    assert len(slots) >= 1
    first_slot = slots[0]
    assert first_slot["mandi_id"] == mandi_id
    assert "start_time" in first_slot
    assert "remaining_capacity_qt" in first_slot

    # Single slot
    slot_id = first_slot["slot_id"]
    res_single = client.get(f"/api/v1/slots/{slot_id}")
    assert res_single.status_code == 200
    assert res_single.json()["slot_id"] == slot_id

    # Path-based slot querying for AdminDashboard
    res_path_slots = client.get(f"/api/v1/slots/mandi/{mandi_id}/date/{today}")
    assert res_path_slots.status_code == 200
    assert len(res_path_slots.json()) == len(slots)
    assert res_path_slots.json()[0]["slot_id"] == slot_id


def test_admin_endpoints_rbac(client: TestClient, seed_test_data):
    # Admin token
    admin_token = create_access_jwt(data={"sub": "admin", "role": "ADMIN", "user_id": 1})
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    # Operator token (not admin)
    operator_token = create_access_jwt(data={"sub": "operator", "role": "OPERATOR", "user_id": 4})
    headers_operator = {"Authorization": f"Bearer {operator_token}"}

    # 1. List users as Admin -> OK
    res_users = client.get("/api/v1/admin/users", headers=headers_admin)
    assert res_users.status_code == 200
    assert len(res_users.json()) >= 4

    # 2. List users as Operator -> Forbidden 403
    res_forbidden = client.get("/api/v1/admin/users", headers=headers_operator)
    assert res_forbidden.status_code == 403

    # 3. Create or update crop as Admin
    new_crop_payload = {
        "crop_name": "Gram (Desi)",
        "crop_code": "GRAM_DESI_TEST",
        "category": "PULSE",
        "msp_price_inr": 5440.00,
        "optimal_moisture_pct": 12.0,
        "max_moisture_pct": 14.0,
        "is_active": True
    }
    res_crop = client.post("/api/v1/admin/crops", json=new_crop_payload, headers=headers_admin)
    assert res_crop.status_code == 201
    assert res_crop.json()["crop_code"] == "GRAM_DESI_TEST"

    # 4. Attempt to create mandi as Operator -> Forbidden 403
    mandi_payload = {
        "name": "Unauthorized Mandi",
        "district": "Test",
        "state": "Test",
        "daily_capacity_qt": 5000,
        "active_weighbridges": 2,
        "is_operational": True
    }
    res_mandi_denied = client.post("/api/v1/admin/mandis", json=mandi_payload, headers=headers_operator)
    assert res_mandi_denied.status_code == 403

    # 5. Delete / Deactivate Crop as Admin -> OK
    crop_id = res_crop.json()["crop_id"]
    res_del = client.delete(f"/api/v1/admin/crops/{crop_id}", headers=headers_admin)
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "SUCCESS"


def test_gap_fixes_endpoints(client: TestClient, seed_test_data):
    today = date.today().isoformat()
    # 1. Test farmer latest booking endpoint
    res_latest = client.get("/api/v1/farmers/1/latest-booking")
    assert res_latest.status_code == 200
    assert "has_booking" in res_latest.json()

    # 2. Book a slot
    slots_res = client.get(f"/api/v1/slots?mandi_id=1&scheduled_date={today}")
    assert slots_res.status_code == 200
    slot_id = slots_res.json()[0]["slot_id"]
    initial_rem_cap = slots_res.json()[0]["remaining_capacity_qt"]

    book_res = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": 1,
            "slot_id": slot_id,
            "farmer_id": 1,
            "requested_qty_qt": 15.0
        }
    )
    assert book_res.status_code == 201
    txn_id = book_res.json()["transaction_id"]

    # 3. Test quality inspection endpoint for newly booked lot
    res_q = client.get(f"/api/v1/quality/{txn_id}")
    assert res_q.status_code == 200
    assert res_q.json()["transaction_id"] == txn_id

    # 4. Cancel slot appointment before gate check-in
    cancel_res = client.post("/api/v1/slots/cancel", json={"transaction_id": txn_id})
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "SUCCESS"

    # Verify slot capacity was restored
    slots_after = client.get(f"/api/v1/slots?mandi_id=1&scheduled_date={today}")
    assert slots_after.json()[0]["remaining_capacity_qt"] == initial_rem_cap

