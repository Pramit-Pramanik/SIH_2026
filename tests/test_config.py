import pytest
from backend.app.core.config import REPOSITORY_ROOT, Settings

def test_settings_load_defaults(monkeypatch):
    """Verify default configuration values."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        MANDIQ_SECRET_HMAC_KEY="valid-key",
        MANDIQ_PAYOUT_SECRET_KEY="valid-key"
    )
    assert settings.PROJECT_ROOT == str(REPOSITORY_ROOT)
    assert settings.DATABASE_URL == f"sqlite:///{(REPOSITORY_ROOT / 'mandiq.db').as_posix()}"
    assert settings.MANDIQ_MOISTURE_DECAY_K == 0.8
    assert "http://localhost:5173" in settings.CORS_ORIGINS

def test_relative_sqlite_url_resolves_from_repository_root():
    settings = Settings(DATABASE_URL="sqlite:///data/test.db")
    assert settings.DATABASE_URL == f"sqlite:///{(REPOSITORY_ROOT / 'data/test.db').as_posix()}"

def test_fail_closed_on_missing_hmac_secret():
    """Verify system fails closed when MANDIQ_SECRET_HMAC_KEY is missing (AC-004)."""
    settings = Settings(
        ENVIRONMENT="production",
        MANDIQ_SECRET_HMAC_KEY="",
        MANDIQ_PAYOUT_SECRET_KEY="valid-key"
    )
    with pytest.raises(RuntimeError, match="MANDIQ_SECRET_HMAC_KEY is missing or empty"):
        settings.validate_secrets(enforce_all=True)

def test_fail_closed_on_missing_payout_secret():
    """Verify system fails closed when MANDIQ_PAYOUT_SECRET_KEY is missing (AC-004)."""
    settings = Settings(
        ENVIRONMENT="production",
        MANDIQ_SECRET_HMAC_KEY="valid-key",
        MANDIQ_PAYOUT_SECRET_KEY=""
    )
    with pytest.raises(RuntimeError, match="MANDIQ_PAYOUT_SECRET_KEY is missing or empty"):
        settings.validate_secrets(enforce_all=True)

def test_valid_secrets_pass():
    """Verify valid secrets pass validation."""
    settings = Settings(
        ENVIRONMENT="production",
        MANDIQ_SECRET_HMAC_KEY="valid-hmac-key",
        MANDIQ_PAYOUT_SECRET_KEY="valid-payout-key"
    )
    # Should not raise
    settings.validate_secrets(enforce_all=True)
