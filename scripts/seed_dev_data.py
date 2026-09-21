#!/usr/bin/env python3
"""
MandiQ Deterministic Development & Demonstration Seed Data Script.

Delegates directly to the authoritative seed_service data-construction layer
to preserve a single source of truth across the platform.
"""

import sys
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.seed_service import bootstrap_database


def seed_database() -> None:
    """Executes authoritative database seeding via seed_service."""
    reset_mode = "--reset" in sys.argv
    db = SessionLocal()
    try:
        mode_str = "reset and restore" if reset_mode else "idempotent initialization"
        print(f"[MandiQ Seed] Starting deterministic database {mode_str} via seed_service...")
        result = bootstrap_database(db, reset=reset_mode)
        print(f"  + Mandis ensured:       {result['mandis_count']}")
        print(f"  + Crops ensured:        {result['crops_count']}")
        print(f"  + Farmers ensured:      {result['farmers_count']}")
        print(f"  + Users ensured:        {result['users_count']}")
        print(f"  + Procurement slots:    {result['slots_count']}")
        print(f"  + Showcase txns active: {result['transactions_count']}")
        print("[MandiQ Seed] Database seeding completed successfully.")
    except Exception as exc:
        db.rollback()
        print(f"[MandiQ Seed] ERROR during seeding: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
