import os
import sys
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlite3 import Connection as SQLite3Connection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 1. Enforce test environment variables before module imports
os.environ["ENVIRONMENT"] = "test"
os.environ["MANDIQ_SECRET_HMAC_KEY"] = "test-hmac-secret-key-for-unit-tests-32char"
os.environ["MANDIQ_PAYOUT_SECRET_KEY"] = "test-payout-secret-key-for-unit-tests-32char"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MANDIQ_AUTH_ENFORCED"] = "false"

from backend.app.core.config import get_settings, Settings
from backend.app.db.base import Base
from backend.app.dependencies.get_db import get_db
from backend.app.main import app
import backend.app.models  # Register all models on Base.metadata

from sqlalchemy.pool import StaticPool

# Create in-memory test engine
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    future=True
)

@pytest.fixture(scope="function", autouse=True)
def setup_tables():
    """Create all tables in memory cleanly before each test and drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def session_factory():
    """Yield session factory bound to the active test engine."""
    return TestingSessionLocal

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Yield a fresh database session for each test."""
    session = TestingSessionLocal()
    yield session
    session.close()

@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
