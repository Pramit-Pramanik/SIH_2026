"""
Tests for Demo Packaging and Data Truthfulness.

Verifies:
1. Ordinary read GET /slots is side-effect free (no database mutations when auto_provision=False).
2. Explicit POST /slots/provision correctly provisions standard operational slots.
3. Showcase reset (POST /admin/reset-showcase) operates deterministically.
4. .env.example contains zero live/team secrets and documents all required Settings fields.
5. setup_demo_env script correctly generates an operational environment satisfying fail-closed security invariants.
"""
from datetime import date, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from scripts.setup_demo_env import generate_secure_hex


def test_ordinary_slots_read_has_no_side_effects(client: TestClient, db_session: Session):
    """
    Verifies that querying slots for an unseeded date does NOT insert rows
    into the database by default, maintaining pure read-only semantics.
    """
    mandi = Mandi(
        name="Packaging Test Mandi",
        district="Ujjain",
        state="Madhya Pradesh",
        daily_capacity_qt=5000.0,
        active_weighbridges=2,
        is_operational=True
    )
    db_session.add(mandi)
    db_session.commit()
    db_session.refresh(mandi)

    unseeded_date = date.today() + timedelta(days=90)

    # Initial count in database
    initial_count = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == mandi.mandi_id,
        ProcurementSlot.scheduled_date == unseeded_date
    ).count()
    assert initial_count == 0

    # Ordinary GET request
    resp = client.get(f"/api/v1/slots?mandi_id={mandi.mandi_id}&scheduled_date={unseeded_date}")
    assert resp.status_code == 200
    assert resp.json() == []

    # Database count must remain exactly 0 (no side-effects)
    after_count = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == mandi.mandi_id,
        ProcurementSlot.scheduled_date == unseeded_date
    ).count()
    assert after_count == 0


def test_explicit_slot_provisioning_endpoint(client: TestClient, db_session: Session):
    """
    Verifies that POST /api/v1/slots/provision explicitly provisions the standard
    hourly operational slots for a target mandi and date.
    """
    mandi = Mandi(
        name="Provision Test Mandi",
        district="Indore",
        state="Madhya Pradesh",
        daily_capacity_qt=5000.0,
        active_weighbridges=2,
        is_operational=True
    )
    db_session.add(mandi)
    db_session.commit()
    db_session.refresh(mandi)

    target_date = date.today() + timedelta(days=60)

    # Explicit provision call
    resp_provision = client.post(
        "/api/v1/slots/provision",
        json={"mandi_id": mandi.mandi_id, "scheduled_date": str(target_date)}
    )
    assert resp_provision.status_code == 201
    slots = resp_provision.json()
    assert len(slots) == 7
    assert slots[0]["start_time"] == "09:00:00"
    assert slots[0]["allocated_capacity_qt"] == 500.0

    # Subsequent ordinary GET now finds all 7 slots
    resp_get = client.get(f"/api/v1/slots?mandi_id={mandi.mandi_id}&scheduled_date={target_date}")
    assert resp_get.status_code == 200
    assert len(resp_get.json()) == 7


def test_showcase_reset_determinism(client: TestClient, db_session: Session):
    """
    Verifies that POST /api/v1/admin/reset-showcase deterministically seeds
    baseline showcase data without collision errors across multiple consecutive calls.
    """
    for _ in range(2):
        resp = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert "farmer_id" in data
        assert data["mandi_id"] == 1


def test_env_example_truthfulness_and_completeness():
    """
    Verifies that .env.example:
    1. Contains NO populated secret values (zero sensitive live hex strings).
    2. Documents all required runtime parameters declared in backend Settings.
    """
    repo_root = Path(__file__).resolve().parents[1]
    env_example_path = repo_root / ".env.example"
    assert env_example_path.exists(), ".env.example file must be preserved in repository root"

    content = env_example_path.read_text(encoding="utf-8")

    # 1. Zero live secret keys
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("MANDIQ_SECRET_HMAC_KEY=") or line.startswith("MANDIQ_PAYOUT_SECRET_KEY="):
            key, _, val = line.partition("=")
            assert val.strip() == "", f"Live secret exposed in .env.example: {key}={val}"

    # 2. Complete coverage of core Settings fields
    settings_fields = Settings.model_fields.keys()
    essential_fields = [
        "ENVIRONMENT",
        "DATABASE_URL",
        "REDIS_URL",
        "MANDIQ_SECRET_HMAC_KEY",
        "MANDIQ_PAYOUT_SECRET_KEY",
        "MANDIQ_AUTH_ENFORCED",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "MANDIQ_MOISTURE_DECAY_K",
        "CORS_ORIGINS"
    ]
    for field in essential_fields:
        assert field in settings_fields, f"Missing field in Settings class: {field}"
        assert f"{field}=" in content, f".env.example must document {field}"


def test_setup_demo_env_script_validation(tmp_path):
    """
    Verifies that generating random 32-byte hex secrets satisfies fail-closed
    cryptographic key requirements in Settings.validate_secrets(enforce_all=True).
    """
    hmac_key = generate_secure_hex(32)
    payout_key = generate_secure_hex(32)

    assert len(hmac_key) == 64
    assert len(payout_key) == 64
    assert hmac_key != payout_key

    # Validate that settings with these keys pass fail-closed secret validation
    test_settings = Settings(
        ENVIRONMENT="development",
        MANDIQ_SECRET_HMAC_KEY=hmac_key,
        MANDIQ_PAYOUT_SECRET_KEY=payout_key
    )
    # Should not raise
    test_settings.validate_secrets(enforce_all=True)


def test_presentation_archive_integrity_and_secret_exclusion(tmp_path):
    """
    Verifies that create_presentation_archive creates an archive excluding .env, node_modules,
    .venv, and *.db files, while preserving .env.example, and that verify_archive detects violations.
    """
    from scripts.package_presentation_archive import create_presentation_archive, verify_archive
    import zipfile

    test_archive = tmp_path / "test_presentation.zip"
    success = create_presentation_archive(test_archive)
    assert success is True
    assert test_archive.exists()

    # Integrity verification on clean archive
    violations = verify_archive(test_archive)
    assert violations == [], f"Clean archive has unexpected violations: {violations}"

    # Verify actual zip content
    with zipfile.ZipFile(test_archive, "r") as zf:
        names = zf.namelist()
        assert any(n.endswith(".env.example") for n in names)
        assert not any(n.endswith("/.env") or n == ".env" for n in names)
        assert not any("node_modules" in n for n in names)
        assert not any(".venv" in n or "/venv/" in n for n in names)
        assert not any(n.endswith(".db") for n in names)
        assert not any("dist" in n.split("/") for n in names)

    # Verify that verify_archive catches violations if an archive is tainted
    tainted_archive = tmp_path / "tainted.zip"
    with zipfile.ZipFile(tainted_archive, "w") as zf:
        zf.writestr("SIH_2026/.env", "MANDIQ_SECRET_HMAC_KEY=live_secret")
        zf.writestr("SIH_2026/node_modules/pkg/index.js", "console.log(1)")
        zf.writestr("SIH_2026/.venv/pyvenv.cfg", "home = /usr/bin")
        zf.writestr("SIH_2026/mandiq.db", "sqlite3 data")
        zf.writestr("SIH_2026/frontend/dist/index.html", "<html></html>")

    tainted_violations = verify_archive(tainted_archive)
    assert any("Forbidden secret file" in v for v in tainted_violations)
    assert any("Forbidden node_modules" in v for v in tainted_violations)
    assert any("Forbidden virtual environment" in v for v in tainted_violations)
    assert any("Forbidden file extension" in v for v in tainted_violations)
    assert any("Forbidden build artifact directory" in v for v in tainted_violations)
    assert any("Missing required .env.example" in v for v in tainted_violations)
