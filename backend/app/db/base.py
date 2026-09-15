from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 Declarative Base for all MandiQ relational ledger models.
    Ensures complete metadata discovery and cross-engine portability (PostgreSQL 16 / SQLite 3).
    """
    pass
