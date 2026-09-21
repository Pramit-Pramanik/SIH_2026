from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index
)
from sqlalchemy.orm import relationship
from backend.app.db.base import Base

VALID_PROCUREMENT_STATES = (
    "SLOT_BOOKED",
    "GATE_ENTRY_VERIFIED",
    "IN_QA_QUEUE",
    "QUALITY_APPROVED",
    "QUALITY_REJECTED",
    "ROUTED_TO_WEIGHBRIDGE",
    "WEIGHED_GROSS",
    "WEIGHED_TARE",
    "BILL_GENERATED",
    "DBT_PAYMENT_INITIATED",
    "PAYMENT_SETTLED",
    "PAYMENT_FAILED",
    "CANCELLED"
)

class ProcurementLog(Base):
    __tablename__ = "procurement_logs"
    __table_args__ = (
        CheckConstraint("crop_moisture_pct >= 0 AND crop_moisture_pct <= 100", name="chk_crop_moisture_range"),
        CheckConstraint("gross_weight_qt >= 0", name="chk_gross_weight_non_negative"),
        CheckConstraint("tare_weight_qt >= 0", name="chk_tare_weight_non_negative"),
        CheckConstraint("net_weight_qt >= 0", name="chk_net_weight_non_negative"),
        CheckConstraint("total_payout_inr >= 0", name="chk_total_payout_non_negative"),
        CheckConstraint(
            f"current_state IN {tuple(VALID_PROCUREMENT_STATES)}",
            name="chk_procurement_state_valid"
        ),
        Index("idx_procurement_mandi_state", "mandi_id", "current_state"),
        Index("idx_procurement_farmer", "farmer_id"),
    )

    transaction_id = Column(String(36), primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.farmer_id", ondelete="RESTRICT"), nullable=False)
    mandi_id = Column(Integer, ForeignKey("mandis.mandi_id", ondelete="RESTRICT"), nullable=False)
    slot_id = Column(Integer, ForeignKey("procurement_slots.slot_id", ondelete="RESTRICT"), nullable=True)
    scheduled_date = Column(Date, nullable=False)
    crop_moisture_pct = Column(Numeric(4, 2), nullable=True)
    gross_weight_qt = Column(Numeric(10, 2), nullable=True)
    tare_weight_qt = Column(Numeric(10, 2), nullable=True)
    net_weight_qt = Column(Numeric(10, 2), nullable=True)
    total_payout_inr = Column(Numeric(12, 2), nullable=True)
    current_state = Column(String(30), nullable=False)
    token_signature = Column(String(64), nullable=False)
    payout_block_hash = Column(String(64), nullable=True)
    client_mutation_id = Column(String(36), nullable=True)
    server_receive_sequence = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    farmer = relationship("Farmer", back_populates="procurement_logs")
    mandi = relationship("Mandi", back_populates="procurement_logs")
    slot = relationship("ProcurementSlot", back_populates="procurement_logs")


class WALMutationJournal(Base):
    """
    Authoritative persistent journal of processed offline WAL mutations.
    Enforces persistent mutation deduplication across backend restarts (P1-02),
    preserving the original monotonic server receive sequence and mutation status.
    """
    __tablename__ = "wal_mutation_journal"

    client_mutation_id = Column(String(64), primary_key=True, index=True)
    transaction_id = Column(String(36), index=True, nullable=False)
    server_receive_sequence = Column(BigInteger, nullable=False)
    current_state = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False)
    signature_type = Column(String(30), nullable=False, default="INTEGRITY_METADATA")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

