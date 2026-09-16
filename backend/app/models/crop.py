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
from backend.app.db.base import Base

class Crop(Base):
    __tablename__ = "crops"
    __table_args__ = (
        CheckConstraint("msp_price_inr > 0", name="chk_crop_msp_positive"),
        CheckConstraint("optimal_moisture_pct > 0 AND optimal_moisture_pct <= 100", name="chk_crop_optimal_moisture"),
        CheckConstraint("max_moisture_pct > 0 AND max_moisture_pct <= 100", name="chk_crop_max_moisture"),
        CheckConstraint("optimal_moisture_pct <= max_moisture_pct", name="chk_crop_moisture_bounds"),
    )

    crop_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    crop_name = Column(String(100), unique=True, nullable=False)
    crop_code = Column(String(20), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False, default="CEREAL")
    msp_price_inr = Column(Numeric(10, 2), nullable=False)
    optimal_moisture_pct = Column(Numeric(4, 2), nullable=False, default=14.0)
    max_moisture_pct = Column(Numeric(4, 2), nullable=False, default=17.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Crop crop_id={self.crop_id} name='{self.crop_name}' code='{self.crop_code}' msp={self.msp_price_inr}>"
