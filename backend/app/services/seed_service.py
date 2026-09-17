"""
MandiQ Dynamic Showcase & Demonstration Reset Service.
Enables real-time resetting and re-seeding of showcase pipeline transactions,
daily slots, and farmer ceilings from the API / UI during live demonstrations.
"""

from datetime import date, datetime, timezone, time, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.crop import Crop
from backend.app.models.log import ProcurementLog
from backend.app.core.security import generate_booking_signature
from backend.app.services.queue_manager import queue_manager
import hashlib


def sha256_hex(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def reset_showcase_data(db: Session) -> Dict[str, Any]:
    """
    Deterministically resets all 6 showcase prototype transactions to their initial pipeline states
    with today's date, restores farmer ceilings, ensures today's hourly slots are populated,
    and enqueues TXN-DEMO-1002 in the active DCDQ queue.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # 1. Ensure slots exist for today and tomorrow for Mandi 1 & 2
    for mandi_id in [1, 2]:
        for d in [today, tomorrow]:
            existing_count = db.query(ProcurementSlot).filter(
                ProcurementSlot.mandi_id == mandi_id,
                ProcurementSlot.scheduled_date == d
            ).count()

            if existing_count == 0:
                slot_times = [
                    (time(9, 0), time(10, 0)),
                    (time(10, 0), time(11, 0)),
                    (time(11, 0), time(12, 0)),
                    (time(12, 0), time(13, 0)),
                    (time(14, 0), time(15, 0)),
                    (time(15, 0), time(16, 0)),
                    (time(16, 0), time(17, 0)),
                ]
                for st, et in slot_times:
                    slot = ProcurementSlot(
                        mandi_id=mandi_id,
                        scheduled_date=d,
                        start_time=st,
                        end_time=et,
                        allocated_capacity_qt=500.00,
                        booked_capacity_qt=0.00
                    )
                    db.add(slot)
    db.commit()

    # 2. Reset Farmer Ceilings
    farmer_1 = db.query(Farmer).filter(Farmer.farmer_id == 1).first()
    if farmer_1:
        farmer_1.cumulative_booked_qt = 40.00  # Leaves 200.00 qt available
    farmer_2 = db.query(Farmer).filter(Farmer.farmer_id == 2).first()
    if farmer_2:
        farmer_2.cumulative_booked_qt = 65.00
    farmer_3 = db.query(Farmer).filter(Farmer.farmer_id == 3).first()
    if farmer_3:
        farmer_3.cumulative_booked_qt = 60.00
    db.commit()

    # 3. Retrieve today's slots for Mandi 1
    mandi_1_today_slots = db.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today
    ).order_by(ProcurementSlot.start_time.asc()).all()

    slot_ids = [s.slot_id for s in mandi_1_today_slots]
    s1 = slot_ids[0] if len(slot_ids) > 0 else 1
    s2 = slot_ids[1] if len(slot_ids) > 1 else 2
    s3 = slot_ids[2] if len(slot_ids) > 2 else 3
    s4 = slot_ids[3] if len(slot_ids) > 3 else 4
    s5 = slot_ids[4] if len(slot_ids) > 4 else 5
    s6 = slot_ids[5] if len(slot_ids) > 5 else 6

    # 4. Canonical Showcase Transactions
    showcase_txns = [
        {
            "transaction_id": "TXN-DEMO-1001",
            "farmer_id": 1,
            "mandi_id": 1,
            "slot_id": s1,
            "scheduled_date": today,
            "crop_moisture_pct": None,
            "gross_weight_qt": None,
            "tare_weight_qt": None,
            "net_weight_qt": 35.00,
            "total_payout_inr": None,
            "current_state": "GATE_ENTRY_VERIFIED",
            "token_signature": generate_booking_signature(1, 1, s1, 35.0),
            "payout_block_hash": None
        },
        {
            "transaction_id": "TXN-DEMO-1002",
            "farmer_id": 2,
            "mandi_id": 1,
            "slot_id": s2,
            "scheduled_date": today,
            "crop_moisture_pct": 13.80,
            "gross_weight_qt": None,
            "tare_weight_qt": None,
            "net_weight_qt": 75.00,
            "total_payout_inr": None,
            "current_state": "QUALITY_APPROVED",
            "token_signature": generate_booking_signature(2, 1, s2, 75.0),
            "payout_block_hash": None
        },
        {
            "transaction_id": "TXN-DEMO-1003",
            "farmer_id": 3,
            "mandi_id": 1,
            "slot_id": s3,
            "scheduled_date": today,
            "crop_moisture_pct": 10.50,
            "gross_weight_qt": 95.00,
            "tare_weight_qt": 35.00,
            "net_weight_qt": 60.00,
            "total_payout_inr": None,
            "current_state": "WEIGHED_TARE",
            "token_signature": generate_booking_signature(3, 1, s3, 60.0),
            "payout_block_hash": None
        },
        {
            "transaction_id": "TXN-DEMO-1004",
            "farmer_id": 1,
            "mandi_id": 1,
            "slot_id": s4,
            "scheduled_date": today,
            "crop_moisture_pct": 12.00,
            "gross_weight_qt": 72.00,
            "tare_weight_qt": 32.00,
            "net_weight_qt": 40.00,
            "total_payout_inr": 91000.00,
            "current_state": "BILL_GENERATED",
            "token_signature": generate_booking_signature(1, 1, s4, 40.0),
            "payout_block_hash": None
        },
        {
            "transaction_id": "TXN-DEMO-1005",
            "farmer_id": 2,
            "mandi_id": 1,
            "slot_id": s5,
            "scheduled_date": today,
            "crop_moisture_pct": 13.00,
            "gross_weight_qt": 100.00,
            "tare_weight_qt": 35.00,
            "net_weight_qt": 65.00,
            "total_payout_inr": 147875.00,
            "current_state": "PAYMENT_SETTLED",
            "token_signature": generate_booking_signature(2, 1, s5, 65.0),
            "payout_block_hash": sha256_hex("PFMS_SETTLED_DEMO_1005")
        },
        {
            "transaction_id": "TXN-DEMO-1006",
            "farmer_id": 1,
            "mandi_id": 1,
            "slot_id": s6,
            "scheduled_date": today,
            "crop_moisture_pct": 18.20,
            "gross_weight_qt": None,
            "tare_weight_qt": None,
            "net_weight_qt": 55.00,
            "total_payout_inr": None,
            "current_state": "QUALITY_REJECTED",
            "token_signature": generate_booking_signature(1, 1, s6, 55.0),
            "payout_block_hash": None
        },
    ]

    for t_info in showcase_txns:
        existing = db.query(ProcurementLog).filter(
            ProcurementLog.transaction_id == t_info["transaction_id"]
        ).first()

        if not existing:
            txn = ProcurementLog(**t_info)
            db.add(txn)
        else:
            for k, v in t_info.items():
                setattr(existing, k, v)
            existing.updated_at = datetime.now(timezone.utc)

    db.commit()

    # 5. Populate DCDQ Queue with TXN-DEMO-1002 (so QueueMonitor displays immediately)
    try:
        queue_manager.push(1, "TXN-DEMO-1002", 49.00)
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "message": "Showcase prototype database reset successfully to pristine starting states.",
        "transactions_reset": [t["transaction_id"] for t in showcase_txns],
        "scheduled_date": str(today)
    }
