#!/usr/bin/env python3
"""
MandiQ Canonical Demonstration & Showcase Bootstrap Script.

Establishes the authoritative presentation dataset for local evaluation and judge demos.
Workflow:
1. Verify repository configuration and fail-closed cryptographic keys.
2. Verify Alembic database migrations are applied to head (fail if not at head).
3. Verify required database schema exists.
4. Idempotently populate canonical mandis, crops, farmers, operational users, slots,
   showcase transactions, and initial priority queue state via seed_service.
5. Deterministically reset presentation state when --reset is supplied.
"""

import sys
import argparse
from pathlib import Path
from typing import Tuple, List

# Ensure repository root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.services.seed_service import bootstrap_database


REQUIRED_TABLES = [
    "alembic_version",
    "mandis",
    "crops",
    "farmers",
    "users",
    "procurement_slots",
    "procurement_logs",
    "wal_mutation_journal"
]


def verify_configuration() -> Tuple[bool, str]:
    """
    Verifies that application settings and cryptographic secrets are properly configured.
    Enforces fail-closed security invariants.
    """
    try:
        settings = get_settings()
        settings.validate_secrets()
        return True, "Repository environment and cryptographic secrets verified."
    except Exception as exc:
        return False, f"Configuration verification failed: {exc}. Please run 'python scripts/setup_demo_env.py'."


def verify_alembic_at_head() -> Tuple[bool, str]:
    """
    Verifies that Alembic migrations have been executed and the database is at head.
    Application startup and bootstrap scripts must not silently create schemas.
    """
    settings = get_settings()
    ini_path = PROJECT_ROOT / "alembic.ini"
    if not ini_path.exists():
        ini_path = PROJECT_ROOT / "backend" / "alembic.ini"
    if not ini_path.exists():
        return False, "alembic.ini configuration file not found in repository."

    try:
        cfg = Config(str(ini_path))
        cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        head_rev = script.get_current_head()

        engine = create_engine(settings.DATABASE_URL)
        try:
            with engine.connect() as conn:
                ctx = MigrationContext.configure(conn)
                current_rev = ctx.get_current_revision()
        finally:
            engine.dispose()

        if not current_rev:
            return False, (
                f"Database has not been migrated (Current revision: None, Head: {head_rev}). "
                "Please run 'alembic upgrade head' before bootstrapping."
            )

        if current_rev != head_rev:
            return False, (
                f"Database migration is behind head (Current: {current_rev}, Head: {head_rev}). "
                "Please run 'alembic upgrade head' to apply pending migrations."
            )

        return True, f"Alembic migration is at head ({head_rev})."
    except Exception as exc:
        return False, f"Failed to verify Alembic migration state: {exc}. Run 'alembic upgrade head'."


def verify_schema_exists() -> Tuple[bool, str, List[str]]:
    """
    Verifies that all required canonical schema tables exist in the database.
    """
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        missing = [t for t in REQUIRED_TABLES if t not in existing_tables]
        if missing:
            return False, f"Missing required database tables: {missing}", missing
        return True, "All required database tables are present.", []
    except Exception as exc:
        return False, f"Schema inspection failed: {exc}", REQUIRED_TABLES
    finally:
        engine.dispose()


def run_bootstrap(reset: bool = False) -> int:
    """
    Executes the canonical bootstrap process.
    Returns 0 on success, 1 on failure.
    """
    print("=" * 72)
    print("  MANDIQ CANONICAL DEMONSTRATION & SHOWCASE BOOTSTRAP")
    print("=" * 72)

    # 1. Verify Configuration
    print("\n[Step 1/4] Verifying repository configuration & fail-closed keys...")
    cfg_ok, cfg_msg = verify_configuration()
    if not cfg_ok:
        print(f"  [-] ERROR: {cfg_msg}", file=sys.stderr)
        return 1
    print(f"  [+] {cfg_msg}")

    # 2. Verify Alembic is at Head
    print("\n[Step 2/4] Verifying database migration authority...")
    mig_ok, mig_msg = verify_alembic_at_head()
    if not mig_ok:
        print(f"  [-] ERROR: {mig_msg}", file=sys.stderr)
        return 1
    print(f"  [+] {mig_msg}")

    # 3. Verify Required Schema Exists
    print("\n[Step 3/4] Verifying required database schema tables...")
    schema_ok, schema_msg, missing_tables = verify_schema_exists()
    if not schema_ok:
        print(f"  [-] ERROR: {schema_msg}", file=sys.stderr)
        return 1
    print(f"  [+] {schema_msg}")

    # 4. Canonical Seeding / Reset via Single Source of Truth
    mode_label = "Resetting and Restoring Presentation Dataset" if reset else "Idempotent Showcase Seeding"
    print(f"\n[Step 4/4] Executing {mode_label}...")

    db = SessionLocal()
    try:
        result = bootstrap_database(db, reset=reset)
        print(f"  [+] Mandis ensured:       {result['mandis_count']}")
        print(f"  [+] Crops ensured:        {result['crops_count']}")
        print(f"  [+] Farmers ensured:      {result['farmers_count']}")
        print(f"  [+] Users ensured:        {result['users_count']}")
        print(f"  [+] Slots available:      {result['slots_count']} (newly added: {result['slots_newly_created']})")
        print(f"  [+] Showcase txns active: {result['transactions_count']}")
        print(f"  [+] DCDQ queue primed:    Mandi #1 queue loaded with TXN-DEMO-1002")
        print(f"\n[SUCCESS] MandiQ demo database successfully bootstrapped (reset={reset}).")
        print("          Ready for presentation and showcase evaluation.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"  [-] Bootstrap execution error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="MandiQ Authoritative Demonstration Bootstrap & Showcase Initializer."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Deterministically restore showcase transactions and farmer ceilings to pristine baseline."
    )
    args = parser.parse_args()
    sys.exit(run_bootstrap(reset=args.reset))


if __name__ == "__main__":
    main()
