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
