from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    Date,
    Time,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index
)
from sqlalchemy.orm import relationship
from backend.app.db.base import Base

class ProcurementSlot(Base):
    __tablename__ = "procurement_slots"
    __table_args__ = (
        CheckConstraint("allocated_capacity_qt > 0", name="chk_slot_allocated_capacity"),
        CheckConstraint("booked_capacity_qt >= 0", name="chk_slot_booked_non_negative"),
        CheckConstraint("booked_capacity_qt <= allocated_capacity_qt", name="chk_slot_capacity"),
        Index("idx_slots_date_mandi", "mandi_id", "scheduled_date"),
    )

    slot_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mandi_id = Column(Integer, ForeignKey("mandis.mandi_id", ondelete="RESTRICT"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    allocated_capacity_qt = Column(Numeric(10, 2), nullable=False)
    booked_capacity_qt = Column(Numeric(10, 2), nullable=False, default=0.00)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    mandi = relationship("Mandi", back_populates="slots")
    procurement_logs = relationship("ProcurementLog", back_populates="slot")
