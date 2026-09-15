from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.adapters.agmarknet_adapter import AgmarknetMockAdapter
from backend.app.adapters.uidai_adapter import UidaiMockAdapter
from backend.app.adapters.pfms_adapter import PfmsMockAdapter
from backend.app.services.queue_manager import queue_manager

def setup_ussd_environment(db: Session):
    """Sets up a complete mandi, slot, and farmer environment for USSD tests."""
    mandi = Mandi(
        name="Karnal Grain Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=10000.00,
        active_weighbridges=2,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="aadhaar_hash_ussd_test_001",
        name="Sukhbir Singh",
        mobile_number="9876500001",
        bank_account_hash="bank_hash_ussd_001",
        ifsc_code="SBIN0001234",
        land_area_hectares=3.00,
        registered_crop_type="Wheat",
        production_ceiling_qt=75.00
    )
    db.add(mandi)
    db.add(farmer)
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=50.00,
        booked_capacity_qt=10.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    return mandi, farmer, slot


def test_ussd_root_menu_initial_dial(client: TestClient):
    """Verifies that dialing *247# with empty text returns the root menu."""
    response = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-001",
        "phone_number": "9876500001",
        "service_code": "*247#",
        "text": ""
    })
    assert response.status_code == 200
    data = response.json()
    assert data["continue_session"] is True
    assert data["menu_level"] == "ROOT"
    assert "CON Welcome to MandiQ (*247#)" in data["message"]
    assert "1. Check MSP Rates" in data["message"]
    assert "2. Live Mandi Wait Time" in data["message"]
    assert "3. Check Payment Status" in data["message"]
    assert "4. Book Arrival Slot" in data["message"]
    assert "0. Exit" in data["message"]


def test_ussd_plain_text_telecom_response(client: TestClient):
    """
    Verifies that requesting Accept: text/plain returns standard telecom GSM MAP format
    (CON <text> or END <text>).
    """
    response = client.post(
        "/api/v1/ussd/session",
        headers={"Accept": "text/plain", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "sessionId": "sess-gsm-001",
            "phoneNumber": "9876500001",
            "serviceCode": "*247#",
            "text": ""
        }
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text
    assert text.startswith("CON ")
    assert "Welcome to MandiQ" in text


def test_ussd_option_1_check_msp_rates(client: TestClient):
    """Verifies Option 1 returns active MSP rates from the mock AGMARKNET adapter."""
    response = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-002",
        "phone_number": "9876500001",
        "service_code": "*247#",
        "text": "1"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["continue_session"] is True
    assert data["menu_level"] == "MSP_RATES"
    assert "Current MSP Rates" in data["message"]
    assert "Wheat: Rs.2,275.00/qt" in data["message"]
    assert "Mustard: Rs.5,650.00/qt" in data["message"]


def test_ussd_option_2_mandi_wait_time(client: TestClient, db_session: Session):
    """Verifies Option 2 prompts for Mandi ID and computes live queue wait time."""
    mandi, _, _ = setup_ussd_environment(db_session)

    # Prompt step
    res_prompt = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-003",
        "phone_number": "9876500001",
        "service_code": "*247#",
        "text": "2"
    })
    assert res_prompt.status_code == 200
    assert "Enter Mandi ID" in res_prompt.json()["message"]

    # Result step
    res_result = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-003",
        "phone_number": "9876500001",
        "service_code": "*247#",
        "text": f"2*{mandi.mandi_id}"
    })
    assert res_result.status_code == 200
    data = res_result.json()
    assert data["continue_session"] is True
    assert mandi.name in data["message"]
    assert "Active Queue:" in data["message"]
    assert "Est. Wait:" in data["message"]


def test_ussd_option_3_payment_status(client: TestClient, db_session: Session):
    """Verifies Option 3 queries procurement transactions and reports payment status."""
    mandi, farmer, slot = setup_ussd_environment(db_session)

    # Insert a settled transaction
    log = ProcurementLog(
        transaction_id="TXN-USSD-PAY-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        gross_weight_qt=100.00,
        tare_weight_qt=37.50,
        net_weight_qt=62.50,
        total_payout_inr=142187.50,
        current_state="PAYMENT_SETTLED",
        token_signature="SIG-PAY-001"
    )
    db_session.add(log)
    db_session.commit()

    # Query by mobile number
    response = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-004",
        "phone_number": farmer.mobile_number,
        "service_code": "*247#",
        "text": f"3*{farmer.mobile_number}"
    })
    assert response.status_code == 200
    data = response.json()
    assert "TXN-USSD-PAY-001" in data["message"]
    assert "PAYMENT_SETTLED" in data["message"]
    assert "142,187.50" in data["message"]
    assert "Settled (PFMS)" in data["message"]


def test_ussd_option_4_book_arrival_slot(client: TestClient, db_session: Session):
    """
    Verifies Option 4 executes atomic slot reservation via USSD and issues an HMAC token.
    """
    mandi, farmer, slot = setup_ussd_environment(db_session)

    # Book 20 quintals for Mandi
    response = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-005",
        "phone_number": farmer.mobile_number,
        "service_code": "*247#",
        "text": f"4*{mandi.mandi_id}*20.0"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["continue_session"] is False
    assert data["menu_level"] == "BOOKING_SUCCESS"
    assert "Slot Reserved Successfully!" in data["message"]
    assert "Token:" in data["message"]

    # Verify slot booked capacity incremented
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == 30.00  # 10 existing + 20 new


def test_ussd_option_0_exit(client: TestClient):
    """Verifies Option 0 terminates the session."""
    response = client.post("/api/v1/ussd/session", json={
        "session_id": "sess-test-006",
        "phone_number": "9876500001",
        "service_code": "*247#",
        "text": "0"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["continue_session"] is False
    assert data["menu_level"] == "EXIT"
    assert data["message"].startswith("END ")


def test_mock_adapters_isolation_and_determinism(db_session: Session):
    """
    Verifies that all mock adapters (AGMARKNET, UIDAI, PFMS) behave deterministically,
    are marked as mocks, and cannot be confused with live production integrations.
    """
    # 1. AGMARKNET
    agmarknet_res = AgmarknetMockAdapter.get_current_msp_rates()
    assert agmarknet_res["is_mock"] is True
    assert agmarknet_res["rates_inr_per_qt"]["Wheat"] == 2275.00
    assert AgmarknetMockAdapter.get_crop_msp("Wheat") == 2275.00
    assert AgmarknetMockAdapter.get_crop_msp("NonExistentCrop") is None

    # 2. UIDAI / AgriStack
    _, farmer, _ = setup_ussd_environment(db_session)
    uidai_res = UidaiMockAdapter.verify_aadhaar_and_fetch_land_record(db_session, farmer.aadhaar_hash)
    assert uidai_res is not None
    assert uidai_res["is_mock"] is True
    assert uidai_res["farmer_name"] == farmer.name
    assert uidai_res["production_ceiling_qt"] == float(farmer.production_ceiling_qt)

    # Non-existent Aadhaar
    assert UidaiMockAdapter.verify_aadhaar_and_fetch_land_record(db_session, "fake_aadhaar") is None

    # 3. PFMS Payout Rail
    pfms_res = PfmsMockAdapter.disburse_payout(
        transaction_id="TXN-PFMS-001",
        amount_inr=142187.50,
        payout_block_hash="HASH-BLOCK-001"
    )
    assert pfms_res["is_mock"] is True
    assert pfms_res["status"] == "INITIATED"
    assert pfms_res["settlement_rail"] == "PFMS-Aadhaar-Bridge"
    assert pfms_res["payout_reference_id"].startswith("PFMS-")


def test_ussd_menu_spec_and_agmarknet_endpoints(client: TestClient):
    """Verifies REST endpoints for USSD menu specification and mock AGMARKNET price board."""
    # USSD menu specification
    res_menu = client.get("/api/v1/ussd/menu")
    assert res_menu.status_code == 200
    data_menu = res_menu.json()
    assert data_menu["service_code"] == "*247#"
    assert len(data_menu["root_menu"]) == 5

    # AGMARKNET price board
    res_rates = client.get("/api/v1/ussd/mock/agmarknet/msp")
    assert res_rates.status_code == 200
    data_rates = res_rates.json()
    assert data_rates["is_mock"] is True
    assert "rates_inr_per_qt" in data_rates
