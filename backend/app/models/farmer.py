from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    CheckConstraint,
    Index
)
from sqlalchemy.orm import relationship
from backend.app.db.base import Base

class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = (
        CheckConstraint("land_area_hectares > 0", name="chk_farmer_land_area"),
        CheckConstraint("production_ceiling_qt > 0", name="chk_farmer_production_ceiling"),
        Index("idx_farmers_aadhaar", "aadhaar_hash"),
    )

    farmer_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aadhaar_hash = Column(String(64), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    mobile_number = Column(String(15), nullable=False)
    bank_account_hash = Column(String(64), nullable=False)
    ifsc_code = Column(String(11), nullable=False)
    land_area_hectares = Column(Numeric(10, 2), nullable=False)
    registered_crop_type = Column(String(50), nullable=False)
    production_ceiling_qt = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    procurement_logs = relationship("ProcurementLog", back_populates="farmer")
