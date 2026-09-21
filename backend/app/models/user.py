from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from backend.app.db.base import Base

VALID_USER_ROLES = (
    "ADMIN",
    "SUPERVISOR",
    "INSPECTOR",
    "OPERATOR",
    "FARMER"
)


class User(Base):
    """
    MandiQ User Model for Authentication and Role-Based Access Control (RBAC).
    Represents Mandi Operators, Inspectors, Yard Supervisors, Administrators, and Farmers.
    """
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False, default="OPERATOR")
    mandi_id = Column(Integer, ForeignKey("mandis.mandi_id"), nullable=True)
    farmer_id = Column(Integer, ForeignKey("farmers.farmer_id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    mandi = relationship("Mandi", backref="users", lazy="joined")
    farmer = relationship("Farmer", backref="user", lazy="joined")

    __table_args__ = (
        CheckConstraint(f"role IN {VALID_USER_ROLES}", name="chk_user_valid_role"),
    )

    def __repr__(self) -> str:
        return f"<User user_id={self.user_id} username='{self.username}' role='{self.role}'>"
