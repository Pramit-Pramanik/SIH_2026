from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Boolean,
    DateTime,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from backend.app.db.base import Base

class Mandi(Base):
    __tablename__ = "mandis"
    __table_args__ = (
        CheckConstraint("daily_capacity_qt > 0", name="chk_mandi_daily_capacity"),
        CheckConstraint("active_weighbridges >= 1", name="chk_mandi_active_weighbridges"),
    )

    mandi_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    district = Column(String(50), nullable=False)
    state = Column(String(50), nullable=False)
    daily_capacity_qt = Column(Numeric(12, 2), nullable=False)
    active_weighbridges = Column(Integer, nullable=False, default=2)
    is_operational = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    slots = relationship("ProcurementSlot", back_populates="mandi", cascade="all, delete-orphan")
    procurement_logs = relationship("ProcurementLog", back_populates="mandi")
