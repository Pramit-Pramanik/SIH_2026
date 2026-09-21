import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.services.billing_service import generate_jform_invoice
from backend.app.schemas.billing import JFormGenerationRequest
from tests.test_phase5_billing_payout import setup_weighed_lot_environment


def test_negative_deductions_rejected_http400(client: TestClient, db_session: Session):
    """
    Asserts that negative deductions are strictly rejected with HTTP 400
    and detail 'Deductions cannot be negative'.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)

    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2275.0,
            "deductions_inr": -150.00,
            "inspector_notes": "Test negative deduction"
        }
    )
    assert resp.status_code == 400, f"Expected HTTP 400, got {resp.status_code}: {resp.text}"
    assert "Deductions cannot be negative" in resp.json()["detail"]


def test_deductions_exceeding_gross_rejected_http400(client: TestClient, db_session: Session):
    """
    Asserts that deductions exceeding gross amount are rejected with HTTP 400
    and detail 'Deductions cannot exceed gross amount'.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=10.0)
    # Gross amount = 10.0 qt * 2275.0 = 22,750.0 INR

    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2275.0,
            "deductions_inr": 25000.00,  # Exceeds gross of 22,750.00
            "inspector_notes": "Test excessive deduction"
        }
    )
    assert resp.status_code == 400, f"Expected HTTP 400, got {resp.status_code}: {resp.text}"
    assert "Deductions cannot exceed gross amount" in resp.json()["detail"]


def test_valid_deductions_computes_correct_invoice_amount(client: TestClient, db_session: Session):
    """
    Asserts that valid deductions (0 <= deductions <= gross) correctly reduce invoice payable.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=50.0)
    # Gross amount = 50.0 qt * 2275.0 = 113,750.0 INR
    # Deductions = 1,750.0 INR -> Net Payable = 112,000.0 INR

    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2275.0,
            "deductions_inr": 1750.00,
            "inspector_notes": "Standard drying cess"
        }
    )
    assert resp.status_code == 200, f"Expected HTTP 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["gross_amount_inr"] == 113750.00
    assert data["deductions_inr"] == 1750.00
    assert data["invoice_amount_inr"] == 112000.00
    assert data["current_state"] == "BILL_GENERATED"


def test_authoritative_crop_msp_derived_from_crop_table(client: TestClient, db_session: Session):
    """
    Asserts that billing derives authoritative MSP from the Crop database table
    when client does not provide a rate.
    """
    from backend.app.models.crop import Crop
    # Insert custom crop in DB
    crop = Crop(
        crop_name="Premium Organic Wheat",
        crop_code="POWHT",
        category="CEREAL",
        msp_price_inr=2650.00,
        optimal_moisture_pct=14.0,
        max_moisture_pct=17.0,
        is_active=True
    )
    db_session.add(crop)
    db_session.commit()

    # Create lot with this crop
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(
        db_session, net_weight=50.0, crop_type="Premium Organic Wheat"
    )

    # Billing request without rate_per_qt
    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "deductions_inr": 0.0,
            "inspector_notes": "Authoritative MSP check"
        }
    )
    assert resp.status_code == 200, f"Expected HTTP 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["rate_per_qt"] == 2650.00
    assert data["standard_msp_rate"] == 2650.00
    assert data["is_rate_overridden"] is False
    assert data["gross_amount_inr"] == 132500.00  # 50 * 2650
    assert data["invoice_amount_inr"] == 132500.00


def test_unauthenticated_client_cannot_override_crop_msp(client: TestClient, db_session: Session):
    """
    Asserts that unauthenticated or non-privileged client cannot override MSP.
    Attempting to supply rate_per_qt != authoritative MSP returns HTTP 403 Forbidden.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=40.0)

    # Standard wheat MSP is 2275.00; client attempts 3000.00 without auth
    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 3000.00,
            "deductions_inr": 0.0,
            "inspector_notes": "Attempt unauthorized override"
        }
    )
    assert resp.status_code == 403, f"Expected HTTP 403, got {resp.status_code}: {resp.text}"
    assert "Unauthorized rate override" in resp.json()["detail"]


def test_supervisor_authorized_msp_override_with_audit(client: TestClient, db_session: Session):
    """
    Asserts that an authenticated supervisor CAN override MSP with an audited reason.
    Response marks is_rate_overridden=True and records both standard and overridden rates.
    """
    from backend.app.models.user import User
    from backend.app.core.security import create_access_jwt

    # Create supervisor user
    supervisor = User(
        username="mandi_supervisor_bill",
        full_name="Mandi Supervisor",
        hashed_password="dummy_hashed_password",
        role="SUPERVISOR",
        is_active=True
    )
    db_session.add(supervisor)
    db_session.commit()
    db_session.refresh(supervisor)

    token = create_access_jwt({
        "sub": str(supervisor.user_id),
        "user_id": supervisor.user_id,
        "username": supervisor.username,
        "role": supervisor.role
    })

    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=40.0)

    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2400.00,
            "rate_override_reason": "High protein grade bonus",
            "deductions_inr": 500.00,
            "inspector_notes": "Supervisor approved premium"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, f"Expected HTTP 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["rate_per_qt"] == 2400.00
    assert data["standard_msp_rate"] == 2275.00
    assert data["is_rate_overridden"] is True
    assert data["gross_amount_inr"] == 96000.00  # 40 * 2400
    assert data["deductions_inr"] == 500.00
    assert data["invoice_amount_inr"] == 95500.00


def test_weighment_tare_greater_than_gross_rejected(client: TestClient, db_session: Session):
    """
    Asserts that impossible weighment where tare_weight >= gross_weight is rejected with HTTP 422.
    """
    from backend.app.models.log import ProcurementLog
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    log.gross_weight_qt = 50.0
    log.tare_weight_qt = 60.0  # Tare > Gross is physically impossible
    log.net_weight_qt = 50.0
    db_session.commit()

    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "deductions_inr": 0.0
        }
    )
    assert resp.status_code == 422, f"Expected HTTP 422, got {resp.status_code}: {resp.text}"
    assert "Tare weight" in resp.json()["detail"]


def test_currency_deterministic_two_decimal_rounding(client: TestClient, db_session: Session):
    """
    Asserts deterministic rounding to 2 decimal places for financial calculations:
    net_weight = 33.33 qt, rate = 2275.00 -> gross = 75,825.75
    deductions = 123.456 -> 123.46 -> invoice = 75,702.29
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(
        db_session, net_weight=33.33, gross_weight=70.0
    )

    resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "deductions_inr": 123.456,
            "inspector_notes": "Fractional deduction rounding test"
        }
    )
    assert resp.status_code == 200, f"Expected HTTP 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["net_weight_qt"] == 33.33
    assert data["gross_amount_inr"] == 75825.75
    assert data["deductions_inr"] == 123.46
    assert data["invoice_amount_inr"] == 75702.29
