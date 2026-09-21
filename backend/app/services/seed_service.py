"""
MandiQ Single Source of Truth — Authoritative Data-Construction & Reset Service.

Centralized, authoritative data-construction layer for:
- scripts/bootstrap_demo.py
- scripts/seed_dev_data.py
- /api/v1/admin/reset-showcase

Maintains canonical definitions and deterministic idempotent construction for:
1. Operational APMC Mandis
2. Official Crops & MSP Price/Moisture Baselines
3. Registered Demo Farmers & Production Ceilings
4. Frontline Operational User Accounts (RBAC)
5. Current and Future Hourly Procurement Slots
6. Canonical Showcase Transactions (TXN-DEMO-1001 through TXN-DEMO-1006)
7. Dynamic Queue Initial State (DCDQ Priority Queue)
"""

import sys
import hashlib
from datetime import date, time, timedelta, datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.crop import Crop
from backend.app.models.user import User
from backend.app.models.log import ProcurementLog
from backend.app.core.security import hash_password, generate_booking_signature
from backend.app.services.queue_manager import queue_manager


def sha256_hex(val: str) -> str:
    """Helper to generate deterministic SHA-256 hex string."""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


# ==============================================================================
# CANONICAL PRESENTATION & DEMO DATA DEFINITIONS
# ==============================================================================

CANONICAL_MANDIS = [
    {
        "mandi_id": 1,
        "name": "Sehore APMC Mandi",
        "district": "Sehore",
        "state": "Madhya Pradesh",
        "daily_capacity_qt": 10000.00,
        "active_weighbridges": 3,
        "is_operational": True
    },
    {
        "mandi_id": 2,
        "name": "Karnal Grain Mandi",
        "district": "Karnal",
        "state": "Haryana",
        "daily_capacity_qt": 15000.00,
        "active_weighbridges": 4,
        "is_operational": True
    }
]

CANONICAL_CROPS = [
    {
        "crop_id": 1,
        "crop_name": "Wheat (HD-2967)",
        "crop_code": "WHEAT_HD2967",
        "category": "CEREAL",
        "msp_price_inr": 2275.00,
        "optimal_moisture_pct": 14.0,
        "max_moisture_pct": 17.0,
        "is_active": True
    },
    {
        "crop_id": 2,
        "crop_name": "Paddy (Basmati)",
        "crop_code": "PADDY_BASMATI",
        "category": "CEREAL",
        "msp_price_inr": 2320.00,
        "optimal_moisture_pct": 15.0,
        "max_moisture_pct": 17.0,
        "is_active": True
    },
    {
        "crop_id": 3,
        "crop_name": "Mustard (Pusa Bold)",
        "crop_code": "MUSTARD_PUSA",
        "category": "OILSEED",
        "msp_price_inr": 5650.00,
        "optimal_moisture_pct": 10.0,
        "max_moisture_pct": 12.0,
        "is_active": True
    },
    {
        "crop_id": 4,
        "crop_name": "Chana (Gram)",
        "crop_code": "CHANA_DESI",
        "category": "PULSE",
        "msp_price_inr": 5440.00,
        "optimal_moisture_pct": 12.0,
        "max_moisture_pct": 14.0,
        "is_active": True
    },
    {
        "crop_id": 5,
        "crop_name": "Soybean (Yellow)",
        "crop_code": "SOYBEAN_YELLOW",
        "category": "OILSEED",
        "msp_price_inr": 4892.00,
        "optimal_moisture_pct": 12.0,
        "max_moisture_pct": 14.0,
        "is_active": True
    }
]

CANONICAL_FARMERS = [
    {
        "farmer_id": 1,
        "aadhaar_hash": sha256_hex("AADHAAR_RAMESH_KUMAR_2026"),
        "name": "Ramesh Kumar",
        "mobile_number": "9876543210",
        "bank_account_hash": sha256_hex("BANK_ACC_RAMESH_2026"),
        "ifsc_code": "SBIN0001040",
        "land_area_hectares": 12.50,
        "registered_crop_type": "Wheat (HD-2967)",
        "production_ceiling_qt": 600.00
    },
    {
        "farmer_id": 2,
        "aadhaar_hash": sha256_hex("AADHAAR_BALVINDER_SINGH_2026"),
        "name": "Balwinder Singh",
        "mobile_number": "9876543211",
        "bank_account_hash": sha256_hex("BANK_ACC_BALVINDER_2026"),
        "ifsc_code": "SBIN0001042",
        "land_area_hectares": 8.00,
        "registered_crop_type": "Wheat (HD-2967)",
        "production_ceiling_qt": 350.00
    },
    {
        "farmer_id": 3,
        "aadhaar_hash": sha256_hex("AADHAAR_SURESH_PATEL_2026"),
        "name": "Suresh Patel",
        "mobile_number": "9876543212",
        "bank_account_hash": sha256_hex("BANK_ACC_SURESH_2026"),
        "ifsc_code": "PUNB0002050",
        "land_area_hectares": 6.00,
        "registered_crop_type": "Mustard (Pusa Bold)",
        "production_ceiling_qt": 250.00
    },
    {
        "farmer_id": 4,
        "aadhaar_hash": "aadhaar_e2e_acceptance_hash_001",
        "name": "Rameshwar Singh",
        "mobile_number": "9876543210",
        "bank_account_hash": sha256_hex("BANK_ACC_RAMESHWAR_2026"),
        "ifsc_code": "SBIN0001042",
        "land_area_hectares": 4.00,
        "registered_crop_type": "Wheat (HD-2967)",
        "production_ceiling_qt": 200.00
    }
]

CANONICAL_USERS = [
    {
        "username": "admin",
        "password": "Admin@MandiQ2026",
        "full_name": "Mandi Board Administrator",
        "role": "ADMIN",
        "mandi_id": None,
        "farmer_id": None
    },
    {
        "username": "supervisor",
        "password": "Supervisor@MandiQ2026",
        "full_name": "APMC Yard Supervisor",
        "role": "SUPERVISOR",
        "mandi_id": 1,
        "farmer_id": None
    },
    {
        "username": "inspector",
        "password": "Inspector@MandiQ2026",
        "full_name": "Quality Assaying Inspector",
        "role": "INSPECTOR",
        "mandi_id": 1,
        "farmer_id": None
    },
    {
        "username": "operator",
        "password": "Operator@MandiQ2026",
        "full_name": "Mandi Yard Operator",
        "role": "OPERATOR",
        "mandi_id": 1,
        "farmer_id": None
    },
    {
        "username": "farmer",
        "password": "Farmer@MandiQ2026",
        "full_name": "Ramesh Kumar (Registered Farmer)",
        "role": "FARMER",
        "mandi_id": None,
        "farmer_id": 1
    }
]

HOURLY_SLOT_WINDOWS = [
    (time(9, 0), time(10, 0)),
    (time(10, 0), time(11, 0)),
    (time(11, 0), time(12, 0)),
    (time(12, 0), time(13, 0)),
    (time(14, 0), time(15, 0)),
    (time(15, 0), time(16, 0)),
    (time(16, 0), time(17, 0))
]


# ==============================================================================
# AUTHORITATIVE CONSTRUCTION METHODS
# ==============================================================================

def ensure_canonical_mandis(db: Session) -> List[Mandi]:
    """Idempotently inserts or updates canonical APMC mandis."""
    mandis = []
    for m_info in CANONICAL_MANDIS:
        existing = db.query(Mandi).filter(
            (Mandi.mandi_id == m_info["mandi_id"]) | (Mandi.name == m_info["name"])
        ).first()
        if not existing:
            mandi = Mandi(**m_info)
            db.add(mandi)
            mandis.append(mandi)
        else:
            for k, v in m_info.items():
                setattr(existing, k, v)
            mandis.append(existing)
    db.commit()
    for m in mandis:
        db.refresh(m)
    return mandis


def ensure_canonical_crops(db: Session) -> List[Crop]:
    """Idempotently inserts or updates canonical agricultural commodities and official MSP."""
    crops = []
    for c_info in CANONICAL_CROPS:
        existing = db.query(Crop).filter(
            (Crop.crop_id == c_info["crop_id"]) | (Crop.crop_code == c_info["crop_code"]) | (Crop.crop_name == c_info["crop_name"])
        ).first()
        if not existing:
            crop = Crop(**c_info)
            db.add(crop)
            crops.append(crop)
        else:
            for k, v in c_info.items():
                setattr(existing, k, v)
            crops.append(existing)
    db.commit()
    for c in crops:
        db.refresh(c)
    return crops


def ensure_canonical_farmers(db: Session, reset: bool = False) -> List[Farmer]:
    """Idempotently inserts or updates registered demo farmers and restores yield ceilings."""
    farmers = []
    for f_info in CANONICAL_FARMERS:
        existing = db.query(Farmer).filter(
            (Farmer.farmer_id == f_info["farmer_id"]) | (Farmer.aadhaar_hash == f_info["aadhaar_hash"])
        ).first()
        if not existing:
            farmer = Farmer(**f_info)
            db.add(farmer)
            farmers.append(farmer)
        else:
            if reset or float(existing.production_ceiling_qt) != float(f_info["production_ceiling_qt"]):
                existing.production_ceiling_qt = f_info["production_ceiling_qt"]
            existing.aadhaar_hash = f_info["aadhaar_hash"]
            existing.name = f_info["name"]
            existing.mobile_number = f_info["mobile_number"]
            existing.bank_account_hash = f_info["bank_account_hash"]
            existing.ifsc_code = f_info["ifsc_code"]
            existing.land_area_hectares = f_info["land_area_hectares"]
            existing.registered_crop_type = f_info["registered_crop_type"]
            farmers.append(existing)
    db.commit()
    for f in farmers:
        db.refresh(f)
    return farmers


def ensure_canonical_users(db: Session) -> List[User]:
    """Idempotently inserts or updates operational user accounts."""
    users = []
    # Purge legacy duplicate farmer login accounts so single farmer auth invariant holds
    db.query(User).filter(User.username.in_(["farmer_balvinder", "farmer_suresh"])).delete(synchronize_session=False)

    for u_info in CANONICAL_USERS:
        uname = u_info["username"]
        existing = db.query(User).filter(User.username == uname).first()
        if not existing:
            u = User(
                username=uname,
                hashed_password=hash_password(u_info["password"]),
                full_name=u_info["full_name"],
                role=u_info["role"],
                mandi_id=u_info["mandi_id"],
                farmer_id=u_info["farmer_id"],
                is_active=True
            )
            db.add(u)
            users.append(u)
        else:
            existing.full_name = u_info["full_name"]
            existing.role = u_info["role"]
            existing.mandi_id = u_info["mandi_id"]
            existing.farmer_id = u_info["farmer_id"]
            existing.is_active = True
            users.append(existing)
    db.commit()
    for u in users:
        db.refresh(u)
    return users


def ensure_canonical_slots(db: Session, num_days: int = 8, reset: bool = False) -> int:
    """
    Idempotently creates hourly procurement slots for Mandis 1 and 2 starting from today
    through the next num_days (default today + 7 days).
    """
    today = date.today()
    slots_created = 0

    for mandi_id in [1, 2]:
        for day_offset in range(num_days):
            sched_date = today + timedelta(days=day_offset)
            for st, et in HOURLY_SLOT_WINDOWS:
                existing = db.query(ProcurementSlot).filter(
                    ProcurementSlot.mandi_id == mandi_id,
                    ProcurementSlot.scheduled_date == sched_date,
                    ProcurementSlot.start_time == st
                ).first()

                if not existing:
                    slot = ProcurementSlot(
                        mandi_id=mandi_id,
                        scheduled_date=sched_date,
                        start_time=st,
                        end_time=et,
                        allocated_capacity_qt=500.00,
                        booked_capacity_qt=0.00,
                        version=1
                    )
                    db.add(slot)
                    slots_created += 1
                elif reset:
                    existing.booked_capacity_qt = 0.00
    db.commit()
    return slots_created


def build_canonical_showcase_transactions(db: Session) -> List[Dict[str, Any]]:
    """Builds the canonical dictionary list of 6 prototype showcase transactions bound to today's slots."""
    today = date.today()
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

    return [
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
        }
    ]


def ensure_showcase_transactions(db: Session, reset: bool = False) -> List[ProcurementLog]:
    """Idempotently seeds or deterministically resets the 6 showcase transactions."""
    showcase_defs = build_canonical_showcase_transactions(db)
    seeded_txns = []

    for t_info in showcase_defs:
        existing = db.query(ProcurementLog).filter(
            ProcurementLog.transaction_id == t_info["transaction_id"]
        ).first()

        if not existing:
            txn = ProcurementLog(**t_info)
            db.add(txn)
            seeded_txns.append(txn)
        elif reset:
            for k, v in t_info.items():
                setattr(existing, k, v)
            existing.created_at = datetime.now(timezone.utc)
            seeded_txns.append(existing)
        else:
            seeded_txns.append(existing)

    db.commit()
    for t in seeded_txns:
        db.refresh(t)
    return seeded_txns


def ensure_showcase_queue_state(mandi_id: int = 1) -> None:
    """Enqueues TXN-DEMO-1002 in active DCDQ queue so live QueueMonitor renders immediately."""
    try:
        queue_manager.clear(mandi_id)
        queue_manager.push(mandi_id, "TXN-DEMO-1002", 49.00)
    except Exception:
        pass


def bootstrap_database(db: Session, reset: bool = False) -> Dict[str, Any]:
    """
    Master authoritative data-construction coordinator.
    Deterministically and idempotently builds:
    mandis -> crops -> farmers -> users -> slots -> showcase transactions -> queue state.
    """
    if reset:
        # Purge temporary simulated and dynamic test transactions
        db.query(ProcurementLog).filter(
            ~ProcurementLog.transaction_id.startswith("TXN-DEMO-")
        ).delete(synchronize_session=False)
        db.commit()

    mandis = ensure_canonical_mandis(db)
    crops = ensure_canonical_crops(db)
    farmers = ensure_canonical_farmers(db, reset=reset)
    users = ensure_canonical_users(db)
    slots_created = ensure_canonical_slots(db, num_days=8, reset=reset)
    txns = ensure_showcase_transactions(db, reset=reset)
    ensure_showcase_queue_state(mandi_id=1)

    total_slots = db.query(ProcurementSlot).count()
    total_txns = db.query(ProcurementLog).count()

    return {
        "status": "SUCCESS",
        "reset": reset,
        "mandis_count": len(mandis),
        "crops_count": len(crops),
        "farmers_count": len(farmers),
        "users_count": len(users),
        "slots_count": total_slots,
        "slots_newly_created": slots_created,
        "transactions_count": total_txns,
        "canonical_transactions": [t.transaction_id for t in txns]
    }


def reset_showcase_data(
    db: Session,
    mandi_id: Optional[int] = None,
    farmer_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Deterministically resets all showcase prototype transactions to their initial pipeline states,
    restores farmer ceilings, hourly slots, and enqueues TXN-DEMO-1002.
    Returns complete backward-compatible dictionary for frontend modals and admin routers.
    """
    if mandi_id is not None:
        target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
        effective_mandi = target_mandi.mandi_id if target_mandi else mandi_id
    else:
        first_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
        effective_mandi = first_mandi.mandi_id if first_mandi else 1

    bootstrap_result = bootstrap_database(db, reset=True)

    today = date.today()
    target_slot = db.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == effective_mandi,
        ProcurementSlot.scheduled_date == today
    ).order_by(ProcurementSlot.start_time.asc()).first()

    if farmer_id is not None:
        farmer = db.query(Farmer).filter(Farmer.farmer_id == farmer_id).first()
    else:
        farmer = db.query(Farmer).order_by(Farmer.farmer_id.asc()).first()

    return {
        "status": "SUCCESS",
        "mandi_id": effective_mandi,
        "farmer_id": farmer.farmer_id if farmer else 1,
        "slot_id": target_slot.slot_id if target_slot else 1,
        "aadhaar_hash": farmer.aadhaar_hash if farmer else "",
        "farmer_name": farmer.name if farmer else "Ramesh Kumar",
        "production_ceiling_qt": float(farmer.production_ceiling_qt) if farmer else 600.0,
        "message": "Showcase prototype database reset successfully to pristine starting states.",
        "transactions_reset": bootstrap_result["canonical_transactions"],
        "scheduled_date": str(today)
    }
