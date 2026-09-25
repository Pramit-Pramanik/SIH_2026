#!/usr/bin/env python3
"""
MandiQ Production Container Entrypoint.
Orchestrates:
1. Pre-flight database connectivity verification with backoff retries.
2. Safe execution of Alembic migrations to head.
3. Idempotent canonical showcase dataset bootstrapping.
4. Production Uvicorn HTTP server execution with fail-closed security invariants.
"""

import os
import sys
import time
from pathlib import Path

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def wait_for_database(max_retries: int = 15, delay_seconds: float = 2.0) -> None:
    """
    Polls the target database until it accepts connections or timeouts.
    Prevents deployment failure when PostgreSQL container is in warm-up / recovery.
    """
    from backend.app.core.config import get_settings
    from sqlalchemy import create_engine, text

    settings = get_settings()
    db_url = settings.DATABASE_URL
    safe_display = db_url.split("@")[-1] if "@" in db_url else db_url.split("://")[0]
    print(f"[STARTUP] Step 1/4: Waiting for database readiness ({safe_display})...")

    connect_args = {"connect_timeout": 5} if ("postgres" in db_url or "postgresql" in db_url) else {}

    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(db_url, connect_args=connect_args)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            print(f"[STARTUP] [+] Database connection verified on attempt {attempt}.")
            return
        except Exception as exc:
            print(f"[STARTUP] [-] Attempt {attempt}/{max_retries}: Database not ready ({exc}). Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)

    print("[STARTUP] [!] FATAL: Database connection timed out after multiple attempts.", file=sys.stderr)
    sys.exit(1)


def run_migrations() -> None:
    """
    Applies Alembic migrations to head.
    Executes within the active Python process to eliminate CLI binary path dependencies.
    """
    print("[STARTUP] Step 2/4: Applying database migrations to head...")
    from alembic.config import Config
    from alembic import command

    ini_path = PROJECT_ROOT / "alembic.ini"
    if not ini_path.exists():
        ini_path = PROJECT_ROOT / "backend" / "alembic.ini"

    if not ini_path.exists():
        print(f"[STARTUP] [!] ERROR: alembic.ini not found in {PROJECT_ROOT}", file=sys.stderr)
        sys.exit(1)

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    try:
        command.upgrade(cfg, "head")
        print("[STARTUP] [+] Database migrations successfully applied to head.")
    except Exception as exc:
        print(f"[STARTUP] [!] ERROR applying migrations: {exc}", file=sys.stderr)
        sys.exit(1)


def run_bootstrap() -> None:
    """
    Executes canonical demonstration dataset bootstrapping.
    Idempotent: ensures mandis, crops, farmers, slots, and showcase records exist.
    """
    print("[STARTUP] Step 3/4: Bootstrapping canonical demonstration data...")
    from scripts.bootstrap_demo import run_bootstrap as execute_bootstrap

    try:
        code = execute_bootstrap(reset=False)
        if code != 0:
            print(f"[STARTUP] [!] WARNING: bootstrap_demo returned exit code {code}", file=sys.stderr)
        else:
            print("[STARTUP] [+] Canonical demonstration data verified.")
    except Exception as exc:
        print(f"[STARTUP] [!] ERROR in bootstrap_demo: {exc}", file=sys.stderr)
        # Continue to start uvicorn if schema is intact


def start_server() -> None:
    """
    Launches Uvicorn with production configuration.
    """
    port = int(os.environ.get("PORT", "8000"))
    host = "0.0.0.0"
    print(f"[STARTUP] Step 4/4: Launching MandiQ API server on {host}:{port}...")

    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )


def main():
    print("=" * 64)
    print("  MANDIQ PRODUCTION CONTAINER INITIALIZATION")
    print("=" * 64)
    wait_for_database()
    run_migrations()
    run_bootstrap()
    start_server()


if __name__ == "__main__":
    main()
