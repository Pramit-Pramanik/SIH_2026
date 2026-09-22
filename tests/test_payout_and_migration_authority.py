"""
Tests for Payout Confirmation and Migration Authority.

Verifies:
1. Payout executes once via dual-signature staging and reaches PAYMENT_SETTLED.
2. Duplicate payout request is idempotent.
3. Settlement reference remains stable across staging and read-only confirmations.
4. Invalid or forged signatures are rejected with HTTP 403.
5. Migration from clean empty SQLite database succeeds to head.
6. Migration model comparison succeeds (zero schema drift between Base.metadata and migrations).
"""
import os
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from backend.app.core.security import (
    get_payout_secret_key,
    compute_role_signature,
    compute_payout_block_hash
)
from backend.app.db.base import Base
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
import backend.app.models  # Register all models on Base.metadata


def _setup_test_procurement(db_session: Session, txn_id: str, amount: float = 142187.50):
    """Helper to populate prerequisite database records in BILL_GENERATED state."""
    mandi = Mandi(
        name="Authority Test Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=5000.0,
        active_weighbridges=2,
        is_operational=True
    )
    db_session.add(mandi)
    db_session.flush()

    farmer = Farmer(
        aadhaar_hash=f"aadhaar_auth_{txn_id[-8:]}",
        name="Balvinder Singh",
        mobile_number="9876543210",
        bank_account_hash="b201f893cd7718919",
        ifsc_code="SBIN0001042",
        land_area_hectares=4.50,
        registered_crop_type="Wheat",
        production_ceiling_qt=300.00
    )
    db_session.add(farmer)
    db_session.flush()

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=datetime.now(timezone.utc).date(),
        start_time=datetime.now(timezone.utc).time(),
        end_time=datetime.now(timezone.utc).time(),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=62.50,
        version=1
    )
    db_session.add(slot)
    db_session.flush()

    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=slot.scheduled_date,
        gross_weight_qt=82.50,
        tare_weight_qt=20.00,
        net_weight_qt=62.50,
        crop_moisture_pct=11.5,
        total_payout_inr=amount,
        current_state="BILL_GENERATED",
        token_signature="test_token_sig_authority"
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return mandi, farmer, slot, log


def test_payout_executes_once(client: TestClient, db_session: Session):
    """
    Verifies that dual signature staging authoritatively executes DBT payout
    exactly once, settling the transaction to PAYMENT_SETTLED, and subsequent
    confirmation endpoints act as read-only queries without executing DBT again.
    """
    txn_id = "TXN-EXEC-ONCE-001"
    amount = 142187.50
    _, _, _, log = _setup_test_procurement(db_session, txn_id, amount)

    secret_key = get_payout_secret_key()
    insp_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    op_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")

    # Authoritative payout staging
    resp_stage = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": insp_sig,
            "operator_id": 202,
            "operator_sig_hash": op_sig
        }
    )
    assert resp_stage.status_code == 200
    stage_data = resp_stage.json()
    assert stage_data["status"] == "AUTHORIZED"
    assert stage_data["current_state"] == "PAYMENT_SETTLED"
    assert len(stage_data["payout_block_hash"]) == 64
    dbt_ref = stage_data["dbt_reference_id"]
    assert dbt_ref.startswith("DBT-")

    # Verify database persistence
    db_session.refresh(log)
    assert log.current_state == "PAYMENT_SETTLED"
    assert log.payout_block_hash == stage_data["payout_block_hash"]
    settled_updated_at = log.updated_at

    # Read-only confirmation via POST /mock/dbt/disburse
    resp_disburse = client.post(
        "/api/v1/mock/dbt/disburse",
        json={"transaction_id": txn_id, "amount_inr": amount}
    )
    assert resp_disburse.status_code == 200
    disburse_data = resp_disburse.json()
    assert disburse_data["status"] == "SUCCESS"
    assert disburse_data["dbt_reference_id"] == dbt_ref
    assert disburse_data["amount_inr"] == amount

    # Explicit read-only confirmation query via GET /mock/dbt/confirmation/{transaction_id}
    resp_confirm = client.get(f"/api/v1/mock/dbt/confirmation/{txn_id}")
    assert resp_confirm.status_code == 200
    confirm_data = resp_confirm.json()
    assert confirm_data["status"] == "SUCCESS"
    assert confirm_data["dbt_reference_id"] == dbt_ref
    assert confirm_data["amount_inr"] == amount

    # Verify no state or timestamp mutation occurred during confirmations
    db_session.refresh(log)
    assert log.current_state == "PAYMENT_SETTLED"
    assert log.updated_at == settled_updated_at


def test_duplicate_payout_request_is_idempotent(client: TestClient, db_session: Session):
    """
    Verifies that re-submitting an already settled payout request with the same
    valid dual signatures returns HTTP 200 AUTHORIZED idempotently with matching
    block hash and settlement reference.
    """
    txn_id = "TXN-IDEMPOTENT-001"
    amount = 142187.50
    _setup_test_procurement(db_session, txn_id, amount)

    secret_key = get_payout_secret_key()
    insp_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    op_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")

    payload = {
        "transaction_id": txn_id,
        "invoice_amount_inr": amount,
        "inspector_id": 101,
        "inspector_sig_hash": insp_sig,
        "operator_id": 202,
        "operator_sig_hash": op_sig
    }

    # Initial request
    resp1 = client.post("/api/v1/payout/stage", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Repeated identical request -> Idempotent
    resp2 = client.post("/api/v1/payout/stage", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["status"] == "AUTHORIZED"
    assert data2["transaction_id"] == txn_id
    assert data2["payout_block_hash"] == data1["payout_block_hash"]
    assert data2["dbt_reference_id"] == data1["dbt_reference_id"]
    assert "idempotent repeated request" in data2["message"]

    # Conflicting repeated request with wrong amount returns 409
    conflicting_payload = dict(payload, invoice_amount_inr=99999.00)
    resp_conflict = client.post("/api/v1/payout/stage", json=conflicting_payload)
    assert resp_conflict.status_code == 409


def test_settlement_reference_remains_stable(client: TestClient, db_session: Session):
    """
    Verifies that the settlement reference remains completely stable across:
    1. Initial payout staging
    2. Idempotent repeat staging
    3. Read-only POST /mock/dbt/disburse
    4. Explicit GET /mock/dbt/confirmation/{txn_id}
    """
    txn_id = "TXN-STABLE-REF-001"
    amount = 142187.50
    _setup_test_procurement(db_session, txn_id, amount)

    secret_key = get_payout_secret_key()
    insp_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    op_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")

    payload = {
        "transaction_id": txn_id,
        "invoice_amount_inr": amount,
        "inspector_id": 101,
        "inspector_sig_hash": insp_sig,
        "operator_id": 202,
        "operator_sig_hash": op_sig
    }

    # 1. Staging
    r_stage = client.post("/api/v1/payout/stage", json=payload)
    ref_stage = r_stage.json()["dbt_reference_id"]

    # 2. Idempotent staging
    r_stage_repeat = client.post("/api/v1/payout/stage", json=payload)
    ref_repeat = r_stage_repeat.json()["dbt_reference_id"]

    # 3. Disburse read-only confirmation
    r_disburse = client.post("/api/v1/mock/dbt/disburse", json={"transaction_id": txn_id})
    ref_disburse = r_disburse.json()["dbt_reference_id"]

    # 4. Explicit GET confirmation
    r_get = client.get(f"/api/v1/mock/dbt/confirmation/{txn_id}")
    ref_get = r_get.json()["dbt_reference_id"]

    # All references must be identical
    assert ref_stage == ref_repeat == ref_disburse == ref_get
    assert ref_stage.startswith("DBT-")


def test_invalid_signature_rejected(client: TestClient, db_session: Session):
    """
    Verifies that invalid or forged signatures are failed closed with HTTP 403,
    preserving transaction state in BILL_GENERATED.
    """
    txn_id = "TXN-BAD-SIG-001"
    amount = 142187.50
    _, _, _, log = _setup_test_procurement(db_session, txn_id, amount)

    secret_key = get_payout_secret_key()
    valid_insp = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    valid_op = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")

    # Forged Inspector Signature
    r_bad_insp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": "FORGED_INSPECTOR_HASH_0000000000000000000000000000000000000000",
            "operator_id": 202,
            "operator_sig_hash": valid_op
        }
    )
    assert r_bad_insp.status_code == 403
    assert "Invalid Inspector Signature" in r_bad_insp.json()["detail"]

    # Forged Operator Signature
    r_bad_op = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": valid_insp,
            "operator_id": 202,
            "operator_sig_hash": "FORGED_OPERATOR_HASH_0000000000000000000000000000000000000000"
        }
    )
    assert r_bad_op.status_code == 403
    assert "Invalid Operator Signature" in r_bad_op.json()["detail"]

    # Tampered amount with valid signatures for different amount
    tampered_amount = 100000.00
    r_tamper = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": tampered_amount,
            "inspector_id": 101,
            "inspector_sig_hash": valid_insp,
            "operator_id": 202,
            "operator_sig_hash": valid_op
        }
    )
    assert r_tamper.status_code == 403
    assert "Invoice amount mismatch / tamper detected" in r_tamper.json()["detail"]

    # Unsettled transaction confirmation fails with HTTP 409
    db_session.refresh(log)
    assert log.current_state == "BILL_GENERATED"
    r_premature_confirm = client.get(f"/api/v1/mock/dbt/confirmation/{txn_id}")
    assert r_premature_confirm.status_code == 409


def test_migration_from_empty_sqlite_succeeds(tmp_path):
    """
    Verifies that running Alembic migrations on a brand new empty SQLite database
    executes cleanly from version 0001 to head.
    """
    db_file = tmp_path / "fresh_migration_test.db"
    db_url = f"sqlite:///{db_file}"

    cfg = Config("backend/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", "backend/alembic")

    # Run upgrade head
    command.upgrade(cfg, "head")

    # Verify tables created
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected_tables = {
            "mandis",
            "farmers",
            "procurement_slots",
            "procurement_logs",
            "users",
            "crops",
            "wal_mutation_journal",
            "weighbridge_events",
            "alembic_version"
        }
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
    finally:
        engine.dispose()


def test_migration_model_comparison_succeeds(tmp_path):
    """
    Verifies that Alembic compare_metadata produces zero diffs against Base.metadata,
    proving that models and migrations are in complete structural agreement.
    """
    db_file = tmp_path / "model_comparison_test.db"
    db_url = f"sqlite:///{db_file}"

    cfg = Config("backend/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", "backend/alembic")

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diff = compare_metadata(ctx, Base.metadata)
            assert diff == [], f"Detected schema drift between migrations and Base.metadata: {diff}"
    finally:
        engine.dispose()
