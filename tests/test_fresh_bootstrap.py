"""
Tests for Fresh Database Migration, Authoritative Bootstrap, and Idempotency.

Verifies:
1. Migration from an empty SQLite database followed by bootstrap populates:
   - users >= 5 (required demo users)
   - farmers >= 3
   - mandis >= 2
   - crops >= 5 (required crops)
   - slots > 0
   - showcase transactions = canonical set (TXN-DEMO-1001 through TXN-DEMO-1006)
2. Triple-run idempotency:
   bootstrap -> bootstrap -> bootstrap
   produces:
   - zero duplicate users
   - zero duplicate farmers
   - zero duplicate transactions
   - zero duplicate slots
3. Reset flag deterministically restores baseline presentation state.
4. Bootstrap verification fails closed if database is unmigrated.
"""

import sys
import subprocess
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.user import User
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.crop import Crop
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.seed_service import (
    bootstrap_database,
    CANONICAL_MANDIS,
    CANONICAL_CROPS,
    CANONICAL_FARMERS,
    CANONICAL_USERS,
)


def apply_migrations(db_url: str):
    """Applies Alembic migrations from empty DB to head."""
    ini_path = PROJECT_ROOT / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    command.upgrade(cfg, "head")


def test_fresh_database_migrations_and_bootstrap(tmp_path):
    """
    Validates fresh-start reproducibility:
    Empty DB -> migrations -> bootstrap -> inspect DB.
    """
    db_file = tmp_path / "fresh_test.db"
    db_url = f"sqlite:///{db_file}"

    # 1. Migrations
    apply_migrations(db_url)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 2. Bootstrap
        result = bootstrap_database(db, reset=False)
        assert result["status"] == "SUCCESS"

        # 3. Inspect DB
        users_count = db.query(User).count()
        farmers_count = db.query(Farmer).count()
        mandis_count = db.query(Mandi).count()
        crops_count = db.query(Crop).count()
        slots_count = db.query(ProcurementSlot).count()
        txns = db.query(ProcurementLog).all()

        # Assertions per requirements:
        # users >= required demo users (5 operational roles)
        assert users_count >= 5, f"Expected users >= 5, found {users_count}"
        demo_usernames = {u.username for u in db.query(User).all()}
        for req_user in ["admin", "supervisor", "inspector", "operator", "farmer"]:
            assert req_user in demo_usernames, f"Missing required user: {req_user}"

        # farmers >= 3
        assert farmers_count >= 3, f"Expected farmers >= 3, found {farmers_count}"

        # mandis >= 2
        assert mandis_count >= 2, f"Expected mandis >= 2, found {mandis_count}"

        # crops >= required crops (5)
        assert crops_count >= 5, f"Expected crops >= 5, found {crops_count}"

        # slots > 0
        assert slots_count > 0, f"Expected slots > 0, found {slots_count}"

        # showcase transactions = canonical set
        canonical_txns = {
            "TXN-DEMO-1001",
            "TXN-DEMO-1002",
            "TXN-DEMO-1003",
            "TXN-DEMO-1004",
            "TXN-DEMO-1005",
            "TXN-DEMO-1006"
        }
        db_txn_ids = {t.transaction_id for t in txns}
        assert db_txn_ids == canonical_txns, (
            f"Showcase transactions must equal canonical set. Got {db_txn_ids}"
        )

        # Inspect initial pipeline states of canonical set
        txn_map = {t.transaction_id: t for t in txns}
        assert txn_map["TXN-DEMO-1001"].current_state == "GATE_ENTRY_VERIFIED"
        assert txn_map["TXN-DEMO-1002"].current_state == "QUALITY_APPROVED"
        assert txn_map["TXN-DEMO-1003"].current_state == "WEIGHED_TARE"
        assert txn_map["TXN-DEMO-1004"].current_state == "BILL_GENERATED"
        assert txn_map["TXN-DEMO-1005"].current_state == "PAYMENT_SETTLED"
        assert txn_map["TXN-DEMO-1006"].current_state == "QUALITY_REJECTED"
    finally:
        db.close()
        engine.dispose()


def test_bootstrap_idempotency_triple_run(tmp_path):
    """
    Validates idempotency:
    Run bootstrap -> bootstrap -> bootstrap.
    Assert zero duplicate users, farmers, transactions, or slots.
    """
    db_file = tmp_path / "idempotency_test.db"
    db_url = f"sqlite:///{db_file}"
    apply_migrations(db_url)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Run 1: Initial bootstrap
        bootstrap_database(db, reset=False)

        count_users_1 = db.query(User).count()
        count_farmers_1 = db.query(Farmer).count()
        count_mandis_1 = db.query(Mandi).count()
        count_crops_1 = db.query(Crop).count()
        count_slots_1 = db.query(ProcurementSlot).count()
        count_txns_1 = db.query(ProcurementLog).count()

        # Run 2: Second bootstrap
        bootstrap_database(db, reset=False)

        assert db.query(User).count() == count_users_1, "Duplicate users created in Run 2"
        assert db.query(Farmer).count() == count_farmers_1, "Duplicate farmers created in Run 2"
        assert db.query(Mandi).count() == count_mandis_1, "Duplicate mandis created in Run 2"
        assert db.query(Crop).count() == count_crops_1, "Duplicate crops created in Run 2"
        assert db.query(ProcurementSlot).count() == count_slots_1, "Duplicate slots created in Run 2"
        assert db.query(ProcurementLog).count() == count_txns_1, "Duplicate transactions created in Run 2"

        # Run 3: Third bootstrap
        bootstrap_database(db, reset=False)

        assert db.query(User).count() == count_users_1, "Duplicate users created in Run 3"
        assert db.query(Farmer).count() == count_farmers_1, "Duplicate farmers created in Run 3"
        assert db.query(Mandi).count() == count_mandis_1, "Duplicate mandis created in Run 3"
        assert db.query(Crop).count() == count_crops_1, "Duplicate crops created in Run 3"
        assert db.query(ProcurementSlot).count() == count_slots_1, "Duplicate slots created in Run 3"
        assert db.query(ProcurementLog).count() == count_txns_1, "Duplicate transactions created in Run 3"

        # Verify no duplicate unique keys exist
        usernames = [u.username for u in db.query(User).all()]
        assert len(usernames) == len(set(usernames)), "Duplicate usernames detected"

        aadhaar_hashes = [f.aadhaar_hash for f in db.query(Farmer).all()]
        assert len(aadhaar_hashes) == len(set(aadhaar_hashes)), "Duplicate farmer aadhaar hashes detected"

        txn_ids = [t.transaction_id for t in db.query(ProcurementLog).all()]
        assert len(txn_ids) == len(set(txn_ids)), "Duplicate transaction IDs detected"

        slot_tuples = [
            (s.mandi_id, s.scheduled_date, s.start_time)
            for s in db.query(ProcurementSlot).all()
        ]
        assert len(slot_tuples) == len(set(slot_tuples)), "Duplicate slots detected"
    finally:
        db.close()
        engine.dispose()


def test_bootstrap_reset_flag_restores_dataset(tmp_path):
    """
    Validates that bootstrap(reset=True) restores the canonical presentation dataset:
    - Removes temporary simulated transactions
    - Restores canonical showcase transactions to pristine state
    - Restores farmer ceilings
    - Resets booked capacity on slots
    """
    db_file = tmp_path / "reset_test.db"
    db_url = f"sqlite:///{db_file}"
    apply_migrations(db_url)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        bootstrap_database(db, reset=False)

        # Mutate database state:
        # 1. Advance a showcase transaction
        t1 = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == "TXN-DEMO-1001").first()
        t1.current_state = "PAYMENT_SETTLED"

        # 2. Add temporary simulated transaction
        sim_txn = ProcurementLog(
            transaction_id="TXN-SIM-TEMP-9999",
            farmer_id=1,
            mandi_id=1,
            scheduled_date=t1.scheduled_date,
            current_state="GATE_ENTRY_VERIFIED",
            token_signature="SIMULATED_TOKEN_SIG_FOR_RESET_TEST_ONLY_123456789012345678901234"
        )
        db.add(sim_txn)

        # 3. Change farmer ceiling
        f1 = db.query(Farmer).filter(Farmer.farmer_id == 1).first()
        f1.production_ceiling_qt = 50.00
        db.commit()

        assert db.query(ProcurementLog).count() == 7

        # Execute bootstrap with reset=True
        bootstrap_database(db, reset=True)

        # Assert simulated transaction was purged
        assert db.query(ProcurementLog).filter(
            ProcurementLog.transaction_id == "TXN-SIM-TEMP-9999"
        ).first() is None

        # Assert canonical count is exactly 6
        assert db.query(ProcurementLog).count() == 6

        # Assert TXN-DEMO-1001 state was restored to GATE_ENTRY_VERIFIED
        db.refresh(t1)
        assert t1.current_state == "GATE_ENTRY_VERIFIED"

        # Assert Farmer 1 ceiling was restored to 600.00 qt
        db.refresh(f1)
        assert float(f1.production_ceiling_qt) == 600.00
    finally:
        db.close()
        engine.dispose()


def test_bootstrap_cli_fails_on_unmigrated_db(tmp_path, monkeypatch):
    """
    Validates that bootstrap_demo.py fails closed with exit code 1 if Alembic migrations
    have not been run, adhering to the requirement:
    'Do NOT create schema silently from application startup.'
    """
    db_file = tmp_path / "unmigrated.db"
    db_url = f"sqlite:///{db_file}"

    # Do NOT run migrations
    engine = create_engine(db_url)
    engine.dispose()

    env = dict(subprocess.os.environ)
    env["DATABASE_URL"] = db_url

    res = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "bootstrap_demo.py")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(PROJECT_ROOT)
    )

    assert res.returncode == 1
    assert "Database has not been migrated" in (res.stdout + res.stderr) or "Alembic" in (res.stdout + res.stderr)
