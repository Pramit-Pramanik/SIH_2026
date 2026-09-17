#!/usr/bin/env python3
"""
MandiQ Deterministic Development & Demonstration Seed Data Script.
Populates standard operational mandis, crops (with MSP), farmers, procurement slots,
and default user accounts for role-based testing and application usage.
"""

import sys
import hashlib
from datetime import date, time, timedelta, datetime, timezone
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.crop import Crop
from backend.app.models.user import User
from backend.app.models.log import ProcurementLog
from backend.app.core.security import hash_password, generate_booking_signature


def sha256_hex(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def seed_database() -> None:
    db = SessionLocal()
    try:
        print("[MandiQ Seed] Starting deterministic database initialization...")

        # 1. Mandis
        mandis_data = [
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

        for m_info in mandis_data:
            existing = db.query(Mandi).filter(Mandi.mandi_id == m_info["mandi_id"]).first()
            if not existing:
                mandi = Mandi(**m_info)
                db.add(mandi)
                print(f"  + Added Mandi: {m_info['name']} (ID {m_info['mandi_id']})")
        db.commit()

        # 2. Crops & Official MSP
        crops_data = [
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

        for c_info in crops_data:
            existing = db.query(Crop).filter(Crop.crop_id == c_info["crop_id"]).first()
            if not existing:
                crop = Crop(**c_info)
                db.add(crop)
                print(f"  + Added Crop: {c_info['crop_name']} (MSP: INR {c_info['msp_price_inr']}/qt)")
        db.commit()

        # 3. Farmers
        farmers_data = [
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
                "name": "Balvinder Singh",
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
            }
        ]

        for f_info in farmers_data:
            existing = db.query(Farmer).filter(Farmer.farmer_id == f_info["farmer_id"]).first()
            if not existing:
                farmer = Farmer(**f_info)
                db.add(farmer)
                print(f"  + Added Farmer: {f_info['name']} (Ceiling: {f_info['production_ceiling_qt']} qt)")
            else:
                if float(existing.production_ceiling_qt) < f_info["production_ceiling_qt"]:
                    existing.production_ceiling_qt = f_info["production_ceiling_qt"]
                    print(f"  + Updated Farmer Ceiling: {f_info['name']} -> {f_info['production_ceiling_qt']} qt")
        db.commit()

        # 4. Standard Operational Users
        default_users = [
            ("admin", "Admin@MandiQ2026", "Mandi Board Administrator", "ADMIN", None),
            ("supervisor", "Supervisor@MandiQ2026", "APMC Yard Supervisor", "SUPERVISOR", 1),
            ("inspector", "Inspector@MandiQ2026", "Quality Assaying Inspector", "INSPECTOR", 1),
            ("operator", "Operator@MandiQ2026", "Mandi Yard Operator", "OPERATOR", 1),
            ("farmer", "Farmer@MandiQ2026", "Ramesh Kumar (Registered Farmer)", "FARMER", None),
        ]

        for uname, pword, fname, role, m_id in default_users:
            existing = db.query(User).filter(User.username == uname).first()
            if not existing:
                u = User(
                    username=uname,
                    hashed_password=hash_password(pword),
                    full_name=fname,
                    role=role,
                    mandi_id=m_id,
                    is_active=True
                )
                db.add(u)
                print(f"  + Added User: {uname} (Role: {role})")
        db.commit()

        # 5. Procurement Slots (Today + next 7 days for Mandis 1 and 2)
        today = date.today()
        slot_times = [
            (time(9, 0), time(10, 0)),
            (time(10, 0), time(11, 0)),
            (time(11, 0), time(12, 0)),
            (time(12, 0), time(13, 0)),
            (time(14, 0), time(15, 0)),
            (time(15, 0), time(16, 0)),
            (time(16, 0), time(17, 0))
        ]

        slots_created = 0
        for m_id in [1, 2]:
            for day_offset in range(8):
                sched_date = today + timedelta(days=day_offset)
                for start_t, end_t in slot_times:
                    existing = db.query(ProcurementSlot).filter(
                        ProcurementSlot.mandi_id == m_id,
                        ProcurementSlot.scheduled_date == sched_date,
                        ProcurementSlot.start_time == start_t
                    ).first()
                    if not existing:
                        slot = ProcurementSlot(
                            mandi_id=m_id,
                            scheduled_date=sched_date,
                            start_time=start_t,
                            end_time=end_t,
                            allocated_capacity_qt=500.00,
                            booked_capacity_qt=0.00,
                            version=1
                        )
                        db.add(slot)
                        slots_created += 1
        db.commit()
        print(f"  + Created {slots_created} procurement slots across mandis.")

        # 6. Showcase Persistent Procurement Transactions
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

        txns_seeded = 0
        reset_mode = "--reset" in sys.argv
        for t_info in showcase_txns:
            existing = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == t_info["transaction_id"]).first()
            if not existing:
                txn = ProcurementLog(**t_info)
                db.add(txn)
                txns_seeded += 1
                print(f"  + Added Showcase Transaction: {t_info['transaction_id']} (State: {t_info['current_state']})")
            elif reset_mode:
                for k, v in t_info.items():
                    setattr(existing, k, v)
                txns_seeded += 1
                print(f"  + Reset Showcase Transaction: {t_info['transaction_id']} (State: {t_info['current_state']})")
        db.commit()
        print(f"  + Processed {txns_seeded} showcase prototype transactions.")

        print("[MandiQ Seed] Database seeding completed successfully.")

    except Exception as exc:
        db.rollback()
        print(f"[MandiQ Seed] ERROR during seeding: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
