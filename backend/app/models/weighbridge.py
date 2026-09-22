from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class WeighbridgeEvent(Base):
    """
    Authoritative telemetry record of a completed weighbridge weighment.
    Records actual scale load-cell completion events (WEIGHED_TARE) used by the
    M(t)/E_k/c(t) non-stationary queuing model to calculate rolling 15-minute
    weighbridge service rates (mu_active) and vehicle ETAs.
    """
    __tablename__ = "weighbridge_events"
    __table_args__ = (
        Index("idx_weighbridge_events_mandi_completed", "mandi_id", "completed_at"),
    )

    event_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    mandi_id = Column(Integer, ForeignKey("mandis.mandi_id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(String(64), nullable=True, index=True)
    scale_id = Column(String(50), nullable=False, default="SCALE-01")
    gross_weight_qt = Column(Numeric(10, 2), nullable=False)
    tare_weight_qt = Column(Numeric(10, 2), nullable=False)
    net_weight_qt = Column(Numeric(10, 2), nullable=False)
    completed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    mandi = relationship("Mandi")

