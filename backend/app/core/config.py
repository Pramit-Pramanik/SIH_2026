from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _resolve_sqlite_url(database_url: str) -> str:
    """Resolve relative SQLite database paths against the repository root."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url

    database_path, separator, query = database_url[len(prefix):].partition("?")
    if database_path == ":memory:" or Path(database_path).is_absolute():
        return database_url

    resolved_url = f"{prefix}{(REPOSITORY_ROOT / database_path).resolve().as_posix()}"
    return f"{resolved_url}{separator}{query}" if separator else resolved_url

class Settings(BaseSettings):
    """
    MandiQ Core Configuration.
    Enforces fail-closed cryptographic key safety per AC-004 and ADR-003.
    """
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_ROOT: str = Field(default_factory=lambda: str(REPOSITORY_ROOT))
    ENVIRONMENT: str = Field(default="development")
    DATABASE_URL: str = Field(default="sqlite:///mandiq.db")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Cryptographic secrets - fail closed if missing or empty in production/active runtime
    MANDIQ_SECRET_HMAC_KEY: str = Field(default="")
    MANDIQ_PAYOUT_SECRET_KEY: str = Field(default="")
    MANDIQ_AUTH_ENFORCED: bool = Field(default=False)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480)

    # DCDQ Perishability parameter
    MANDIQ_MOISTURE_DECAY_K: float = Field(default=0.8)

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_sqlite_database_path(cls, database_url: str) -> str:
        return _resolve_sqlite_url(database_url)

    def validate_secrets(self, enforce_all: bool = False) -> None:
        """
        Validates cryptographic secret presence.
        Fails closed immediately with RuntimeError if missing in non-test mode or if enforce_all is True.
        """
        if self.ENVIRONMENT == "test" and not enforce_all:
            return

        if not self.MANDIQ_SECRET_HMAC_KEY or not self.MANDIQ_SECRET_HMAC_KEY.strip():
            raise RuntimeError(
                "FAIL-CLOSED SECURITY INVARIANT (AC-004): MANDIQ_SECRET_HMAC_KEY is missing or empty. "
                "The system refuses to start without a valid HMAC secret."
            )

        if not self.MANDIQ_PAYOUT_SECRET_KEY or not self.MANDIQ_PAYOUT_SECRET_KEY.strip():
            raise RuntimeError(
                "FAIL-CLOSED SECURITY INVARIANT (AC-004): MANDIQ_PAYOUT_SECRET_KEY is missing or empty. "
                "The system refuses to start without a valid DBT payout secret."
            )

@lru_cache()
def get_settings() -> Settings:
    return Settings()
