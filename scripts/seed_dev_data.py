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
from backend.app.core.security import hash_password


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
                "land_area_hectares": 2.50,
                "registered_crop_type": "Wheat (HD-2967)",
                "production_ceiling_qt": 100.00
            },
            {
                "farmer_id": 2,
                "aadhaar_hash": sha256_hex("AADHAAR_BALVINDER_SINGH_2026"),
                "name": "Balvinder Singh",
                "mobile_number": "9876543211",
                "bank_account_hash": sha256_hex("BANK_ACC_BALVINDER_2026"),
                "ifsc_code": "SBIN0001042",
                "land_area_hectares": 4.00,
                "registered_crop_type": "Wheat (HD-2967)",
                "production_ceiling_qt": 160.00
            },
            {
                "farmer_id": 3,
                "aadhaar_hash": sha256_hex("AADHAAR_SURESH_PATEL_2026"),
                "name": "Suresh Patel",
                "mobile_number": "9876543212",
                "bank_account_hash": sha256_hex("BANK_ACC_SURESH_2026"),
                "ifsc_code": "PUNB0002050",
                "land_area_hectares": 3.00,
                "registered_crop_type": "Mustard (Pusa Bold)",
                "production_ceiling_qt": 120.00
            }
        ]

        for f_info in farmers_data:
            existing = db.query(Farmer).filter(Farmer.farmer_id == f_info["farmer_id"]).first()
            if not existing:
                farmer = Farmer(**f_info)
                db.add(farmer)
                print(f"  + Added Farmer: {f_info['name']} (Ceiling: {f_info['production_ceiling_qt']} qt)")
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

        print("[MandiQ Seed] Database seeding completed successfully.")

    except Exception as exc:
        db.rollback()
        print(f"[MandiQ Seed] ERROR during seeding: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
