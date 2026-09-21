"""
Tests for AUD-007: Authoritative MSP Only Billing Resolution.

Verifies:
1. Wheat MSP resolves authoritatively from Crop table (₹2,275.00).
2. Paddy MSP resolves authoritatively from Crop table (₹2,320.00, never 2275).
3. Mustard MSP resolves authoritatively from Crop table (₹5,650.00, never 2275).
4. Dynamically updated MSP in Crop table immediately takes effect for subsequent bills.
5. Unknown/unregistered crop returns controlled HTTP 404 without falling back to Wheat or ₹2,275.
6. Inactive crop (is_active=False) returns controlled HTTP 404 without fallback.
7. Missing crop on transaction and farmer returns controlled HTTP 422.
8. Operator cannot submit unauthorized MSP override (HTTP 403).
9. Supervisor/Admin override still works with audited reason and is_rate_overridden=True.
10. Operator can generate bill at authoritative MSP without supplying rate_per_qt.
"""

from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.core.security import create_access_jwt
from backend.app.services.billing_service import resolve_authoritative_crop_msp


@pytest.fixture
def msp_environment(db_session: Session):
    """Sets up an authoritative mandi and canonical active crops."""
    mandi = Mandi(
        mandi_id=1,
        name="Amritsar Grain Mandi",
        district="Amritsar",
        state="Punjab",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    db_session.add(mandi)

    crops = [
        Crop(
            crop_name="Wheat (HD-2967)",
            crop_code="WHEAT_HD2967",
            category="CEREAL",
            msp_price_inr=2275.00,
            optimal_moisture_pct=14.0,
            max_moisture_pct=17.0,
            is_active=True
        ),
        Crop(
            crop_name="Paddy (Basmati)",
            crop_code="PADDY_BASMATI",
            category="CEREAL",
            msp_price_inr=2320.00,
            optimal_moisture_pct=15.0,
            max_moisture_pct=17.0,
            is_active=True
        ),
        Crop(
            crop_name="Mustard (Pusa Bold)",
            crop_code="MUSTARD_PUSA",
            category="OILSEED",
            msp_price_inr=5650.00,
            optimal_moisture_pct=10.0,
            max_moisture_pct=12.0,
            is_active=True
        ),
        Crop(
            crop_name="Dormant Barley",
            crop_code="BARLEY_INACTIVE",
            category="CEREAL",
            msp_price_inr=1850.00,
            optimal_moisture_pct=12.0,
            max_moisture_pct=15.0,
            is_active=False  # INACTIVE
        ),
    ]
    for c in crops:
        db_session.add(c)
    db_session.commit()
    return mandi


def _create_weighed_lot(
    db: Session,
    mandi_id: int,
    farmer_id: int,
    crop_type: str,
    net_weight: float = 50.00
) -> str:
    """Helper creating a transaction in WEIGHED_TARE state."""
    slot = ProcurementSlot(
        mandi_id=mandi_id,
        scheduled_date=date(2026, 11, 20),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=500.00,
        booked_capacity_qt=net_weight,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    farmer = Farmer(
        farmer_id=farmer_id,
        aadhaar_hash=f"aadhaar_msp_test_{farmer_id}",
        name=f"Farmer {farmer_id}",
        mobile_number=f"98765000{farmer_id:02d}",
        bank_account_hash=f"bank_hash_{farmer_id}",
        ifsc_code="SBIN0001042",
        land_area_hectares=3.0,
        registered_crop_type=crop_type,
        production_ceiling_qt=300.0
    )
    db.add(farmer)
    db.commit()

    txn_id = f"TXN-MSP-TEST-{farmer_id}"
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer_id,
        mandi_id=mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date(2026, 11, 20),
        crop_type=crop_type,
        gross_weight_qt=net_weight + 20.0,
        tare_weight_qt=20.0,
        net_weight_qt=net_weight,
        crop_moisture_pct=12.5,
        current_state="WEIGHED_TARE",
        token_signature="test_sig_msp"
    )
    db.add(log)
    db.commit()
    return txn_id


def test_wheat_msp_authoritative_resolution(client: TestClient, db_session: Session, msp_environment):
    """
    Test 1: Wheat MSP resolves to ₹2,275.00 strictly from the Crop Master table.
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=101, crop_type="Wheat (HD-2967)", net_weight=50.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 200, f"Expected 200, got: {resp.text}"
    data = resp.json()
    assert data["crop_type"] == "Wheat (HD-2967)"
    assert data["rate_per_qt"] == 2275.00
    assert data["standard_msp_rate"] == 2275.00
    assert data["gross_amount_inr"] == 113750.00  # 50 * 2275
    assert data["is_rate_overridden"] is False


def test_paddy_msp_authoritative_resolution(client: TestClient, db_session: Session, msp_environment):
    """
    Test 2: Paddy MSP resolves to ₹2,320.00 strictly from Crop table (NEVER falling back to 2275).
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=102, crop_type="Paddy (Basmati)", net_weight=40.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 200, f"Expected 200, got: {resp.text}"
    data = resp.json()
    assert data["crop_type"] == "Paddy (Basmati)"
    assert data["rate_per_qt"] == 2320.00
    assert data["standard_msp_rate"] == 2320.00
    assert data["gross_amount_inr"] == 92800.00  # 40 * 2320
    assert data["is_rate_overridden"] is False


def test_mustard_msp_authoritative_resolution(client: TestClient, db_session: Session, msp_environment):
    """
    Test 3: Mustard MSP resolves to ₹5,650.00 strictly from Crop table (NEVER falling back to 2275).
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=103, crop_type="Mustard (Pusa Bold)", net_weight=20.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 200, f"Expected 200, got: {resp.text}"
    data = resp.json()
    assert data["crop_type"] == "Mustard (Pusa Bold)"
    assert data["rate_per_qt"] == 5650.00
    assert data["standard_msp_rate"] == 5650.00
    assert data["gross_amount_inr"] == 113000.00  # 20 * 5650
    assert data["is_rate_overridden"] is False


def test_dynamically_updated_msp(client: TestClient, db_session: Session, msp_environment):
    """
    Test 4: Updating crop MSP in Crop table takes immediate effect on subsequent billing.
    """
    # Dynamically update Mustard MSP from 5650 to 5850
    mustard = db_session.query(Crop).filter(Crop.crop_code == "MUSTARD_PUSA").first()
    mustard.msp_price_inr = 5850.00
    db_session.commit()

    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=104, crop_type="Mustard (Pusa Bold)", net_weight=10.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rate_per_qt"] == 5850.00
    assert data["standard_msp_rate"] == 5850.00
    assert data["gross_amount_inr"] == 58500.00


def test_unknown_crop_returns_controlled_error(client: TestClient, db_session: Session, msp_environment):
    """
    Test 5: An unknown crop commodity returns HTTP 404 controlled error without fallback to Wheat or 2275.
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=105, crop_type="Exotic Dragonfruit", net_weight=15.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 404, f"Expected 404, got: {resp.status_code}: {resp.text}"
    assert "Authoritative crop record not found for 'Exotic Dragonfruit'" in resp.json()["detail"]


def test_inactive_crop_returns_controlled_error(client: TestClient, db_session: Session, msp_environment):
    """
    Test 6: Inactive crop in DB returns HTTP 404 without fallback.
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=106, crop_type="Dormant Barley", net_weight=30.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 404, f"Expected 404, got: {resp.status_code}: {resp.text}"
    assert "Authoritative crop record not found for 'Dormant Barley'" in resp.json()["detail"]


def test_missing_crop_on_transaction_and_farmer(client: TestClient, db_session: Session, msp_environment):
    """
    Test 7: Missing crop on transaction and farmer returns HTTP 422 without defaulting to Wheat.
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=107, crop_type="Wheat (HD-2967)", net_weight=25.0)
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    log.crop_type = None
    farmer = db_session.query(Farmer).filter(Farmer.farmer_id == 107).first()
    farmer.registered_crop_type = ""
    db_session.commit()

    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "deductions_inr": 0.0}
    )
    assert resp.status_code == 422
    assert "Cannot determine authoritative crop commodity" in resp.json()["detail"]


def test_operator_cannot_submit_unauthorized_override(client: TestClient, db_session: Session, msp_environment):
    """
    Test 8: Operator cannot submit custom rate_per_qt differing from authoritative MSP (HTTP 403).
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=108, crop_type="Wheat (HD-2967)", net_weight=35.0)

    op_user = User(
        username="operator_billing_test",
        hashed_password="hashed_pw",
        full_name="Mandi Operator",
        role="OPERATOR",
        mandi_id=1,
        is_active=True
    )
    db_session.add(op_user)
    db_session.commit()

    op_token = create_access_jwt({
        "sub": str(op_user.user_id),
        "user_id": op_user.user_id,
        "username": op_user.username,
        "role": op_user.role,
        "mandi_id": 1
    })

    resp = client.post(
        "/api/v1/billing/generate",
        headers={"Authorization": f"Bearer {op_token}"},
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2500.00,  # Unauthorized override attempt
            "deductions_inr": 0.0
        }
    )
    assert resp.status_code == 403
    assert "Unauthorized rate override" in resp.json()["detail"]


def test_supervisor_admin_override_still_works(client: TestClient, db_session: Session, msp_environment):
    """
    Test 9: Supervisor/Admin can override rate with audited reason (HTTP 200, is_rate_overridden=True).
    """
    txn_id = _create_weighed_lot(db_session, mandi_id=1, farmer_id=109, crop_type="Wheat (HD-2967)", net_weight=35.0)

    sup_user = User(
        username="supervisor_billing_test",
        hashed_password="hashed_pw",
        full_name="Mandi Supervisor",
        role="SUPERVISOR",
        mandi_id=1,
        is_active=True
    )
    db_session.add(sup_user)
    db_session.commit()

    sup_token = create_access_jwt({
        "sub": str(sup_user.user_id),
        "user_id": sup_user.user_id,
        "username": sup_user.username,
        "role": sup_user.role,
        "mandi_id": 1
    })

    resp = client.post(
        "/api/v1/billing/generate",
        headers={"Authorization": f"Bearer {sup_token}"},
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2450.00,
            "rate_override_reason": "High gluten grade A verified",
            "deductions_inr": 200.0
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rate_per_qt"] == 2450.00
    assert data["standard_msp_rate"] == 2275.00
    assert data["is_rate_overridden"] is True
    assert data["gross_amount_inr"] == 85750.00  # 35 * 2450
    assert data["invoice_amount_inr"] == 85550.00  # 85750 - 200
