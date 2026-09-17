from datetime import datetime, timezone, date, time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.models.mandi import Mandi
from backend.app.models.crop import Crop
from backend.app.models.slot import ProcurementSlot
from backend.app.schemas.mandi import MandiResponse, MandiCreateRequest
from backend.app.schemas.crop import CropResponse, CropCreateRequest
from backend.app.schemas.auth import UserResponse

router = APIRouter(prefix="/admin", tags=["Administrator Management"])


@router.post(
    "/mandis",
    response_model=MandiResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Mandi (Admin)",
    description="Registers a new APMC mandi with defined daily capacity and weighbridge resources."
)
def create_mandi(
    payload: MandiCreateRequest,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"]))
) -> MandiResponse:
    existing = db.query(Mandi).filter(Mandi.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mandi with name '{payload.name}' already exists."
        )

    mandi = Mandi(
        name=payload.name,
        district=payload.district,
        state=payload.state,
        daily_capacity_qt=payload.daily_capacity_qt,
        active_weighbridges=payload.active_weighbridges,
        is_operational=payload.is_operational
    )
    db.add(mandi)
    db.commit()
    db.refresh(mandi)
    return MandiResponse.model_validate(mandi)


@router.post(
    "/crops",
    response_model=CropResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Update Crop with MSP (Admin)",
    description="Registers an agricultural commodity with authoritative Minimum Support Price (MSP)."
)
def create_crop(
    payload: CropCreateRequest,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"]))
) -> CropResponse:
    existing = db.query(Crop).filter(Crop.crop_code == payload.crop_code).first()
    if existing:
        # Update existing
        existing.crop_name = payload.crop_name
        existing.category = payload.category
        existing.msp_price_inr = payload.msp_price_inr
        existing.optimal_moisture_pct = payload.optimal_moisture_pct
        existing.max_moisture_pct = payload.max_moisture_pct
        existing.is_active = payload.is_active
        db.commit()
        db.refresh(existing)
        return CropResponse.model_validate(existing)

    crop = Crop(
        crop_name=payload.crop_name,
        crop_code=payload.crop_code,
        category=payload.category,
        msp_price_inr=payload.msp_price_inr,
        optimal_moisture_pct=payload.optimal_moisture_pct,
        max_moisture_pct=payload.max_moisture_pct,
        is_active=payload.is_active
    )
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return CropResponse.model_validate(crop)


@router.put(
    "/mandis/{mandi_id}",
    response_model=MandiResponse,
    summary="Update Mandi Details (Admin)",
    description="Updates operational parameters, capacity, and weighbridges for an existing APMC mandi."
)
def update_mandi(
    mandi_id: int,
    payload: MandiCreateRequest,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"]))
) -> MandiResponse:
    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )

    mandi.name = payload.name
    mandi.district = payload.district
    mandi.state = payload.state
    mandi.daily_capacity_qt = payload.daily_capacity_qt
    mandi.active_weighbridges = payload.active_weighbridges
    mandi.is_operational = payload.is_operational

    db.commit()
    db.refresh(mandi)
    return MandiResponse.model_validate(mandi)


class GenerateSlotsRequest(MandiCreateRequest.__base__):
    mandi_id: int
    start_date: str
    num_days: int = 7
    hourly_capacity_qt: float = 500.0


@router.post(
    "/generate-slots",
    summary="Batch Generate Procurement Slots (Admin)",
    description="Generates standard hourly procurement slots for an APMC mandi across a date range."
)
def generate_procurement_slots(
    payload: dict,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"]))
):
    from datetime import datetime, date, time, timedelta

    mandi_id = int(payload.get("mandi_id", 1))
    start_date_str = payload.get("start_date")
    num_days = int(payload.get("num_days", 7))
    hourly_capacity = float(payload.get("hourly_capacity_qt", 500.0))

    if not start_date_str:
        target_start = date.today()
    else:
        target_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()

    standard_hours = [9, 10, 11, 12, 14, 15, 16]  # 9am to 5pm (1pm lunch)
    created_count = 0

    for d_offset in range(num_days):
        curr_date = target_start + timedelta(days=d_offset)
        for hour in standard_hours:
            s_time = time(hour, 0)
            e_time = time(hour + 1, 0)

            existing = db.query(ProcurementSlot).filter(
                ProcurementSlot.mandi_id == mandi_id,
                ProcurementSlot.scheduled_date == curr_date,
                ProcurementSlot.start_time == s_time
            ).first()

            if not existing:
                slot = ProcurementSlot(
                    mandi_id=mandi_id,
                    scheduled_date=curr_date,
                    start_time=s_time,
                    end_time=e_time,
                    allocated_capacity_qt=hourly_capacity,
                    booked_capacity_qt=0.0
                )
                db.add(slot)
                created_count += 1

    db.commit()
    return {
        "status": "SUCCESS",
        "mandi_id": mandi_id,
        "slots_created": created_count,
        "message": f"Successfully generated {created_count} procurement slots for Mandi #{mandi_id}."
    }


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List Operational Users (Admin)",
    description="Retrieves active user accounts, assigned roles, and operational mandis."
)
def list_users(
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"]))
) -> List[UserResponse]:
    users = db.query(User).order_by(User.user_id.asc()).all()
    return [
        UserResponse(
            user_id=u.user_id,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            mandi_id=u.mandi_id,
            is_active=u.is_active
        )
        for u in users
    ]


@router.delete(
    "/crops/{crop_id}",
    summary="Delete / Deactivate Crop (Admin)",
    description="Deactivates or deletes an agricultural commodity from the APMC master catalog."
)
def delete_crop(
    crop_id: int,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"]))
):
    crop = db.query(Crop).filter(Crop.crop_id == crop_id).first()
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop with ID {crop_id} not found."
        )
    crop.is_active = False
    db.commit()
    return {
        "status": "SUCCESS",
        "crop_id": crop_id,
        "message": f"Crop '{crop.crop_name}' has been deactivated from active procurement."
    }


# ==============================================================================
# DYNAMIC SHOWCASE & LIVE DEMO SIMULATION CONTROLS
# ==============================================================================

@router.get(
    "/metrics",
    summary="Get Real-Time Mandi Yard Metrics (Admin)",
    description="Calculates live operational telemetry across the procurement pipeline for showcase evaluation."
)
def get_mandi_metrics(
    mandi_id: int = 1,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR"]))
):
    from datetime import date
    from backend.app.models.log import ProcurementLog
    from backend.app.models.farmer import Farmer
    from backend.app.services.queue_manager import queue_manager

    today = date.today()
    logs = db.query(ProcurementLog).filter(ProcurementLog.mandi_id == mandi_id).all()
    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    total_farmers = db.query(Farmer).count()

    state_counts = {}
    total_volume_qt = 0.0
    total_payout_inr = 0.0
    quality_inspected = 0
    quality_rejected = 0

    for l in logs:
        st = l.current_state
        state_counts[st] = state_counts.get(st, 0) + 1
        if l.net_weight_qt:
            total_volume_qt += float(l.net_weight_qt)
        if l.total_payout_inr and st == "PAYMENT_SETTLED":
            total_payout_inr += float(l.total_payout_inr)
        if l.crop_moisture_pct is not None:
            quality_inspected += 1
            if st == "QUALITY_REJECTED" or float(l.crop_moisture_pct) > 17.0:
                quality_rejected += 1

    queued_vehicles = queue_manager.get_queue(mandi_id)
    rejection_pct = round((quality_rejected / quality_inspected * 100.0), 1) if quality_inspected > 0 else 0.0

    return {
        "mandi_id": mandi_id,
        "mandi_name": mandi.name if mandi else f"Mandi #{mandi_id}",
        "total_registered_farmers": total_farmers,
        "active_transactions_total": len(logs),
        "state_counts": state_counts,
        "queued_vehicles_count": len(queued_vehicles),
        "total_volume_procured_qt": round(total_volume_qt, 2),
        "total_payout_settled_inr": round(total_payout_inr, 2),
        "quality_inspected_count": quality_inspected,
        "quality_rejected_count": quality_rejected,
        "quality_rejection_rate_pct": rejection_pct,
        "active_weighbridges": mandi.active_weighbridges if mandi else 2,
        "daily_capacity_qt": float(mandi.daily_capacity_qt) if mandi else 10000.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post(
    "/simulate-showcase",
    summary="Simulate Dynamic Showcase Traffic",
    description="Dynamically injects realistic vehicle arrivals with varying moisture into the live database and priority queue."
)
def simulate_showcase_traffic(
    payload: dict = None,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR"]))
):
    from datetime import date, time
    import time as time_module
    import hashlib
    from backend.app.models.log import ProcurementLog
    from backend.app.models.slot import ProcurementSlot
    from backend.app.models.farmer import Farmer
    from backend.app.services.queue_manager import queue_manager
    from backend.app.services.dcdq_engine import calculate_dcdq_priority_score
    from backend.app.core.security import generate_booking_signature

    raw_mandi = payload.get("mandi_id") if payload else 1
    try:
        mandi_id = int(raw_mandi) if raw_mandi is not None and str(raw_mandi).strip() != "" else 1
    except (ValueError, TypeError):
        mandi_id = 1

    # Ensure target mandi exists or fallback gracefully
    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        first_mandi = db.query(Mandi).first()
        if first_mandi:
            mandi_id = first_mandi.mandi_id
        else:
            default_m = Mandi(
                name="Central APMC Mandi",
                district="Sehore",
                state="Madhya Pradesh",
                daily_capacity_qt=10000.0,
                active_weighbridges=2
            )
            db.add(default_m)
            db.commit()
            mandi_id = default_m.mandi_id

    today = date.today()

    # Ensure operational slots exist for today
    today_slots = db.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == mandi_id,
        ProcurementSlot.scheduled_date == today
    ).order_by(ProcurementSlot.start_time.asc()).all()

    if not today_slots:
        for hour in [9, 10, 11, 12, 14, 15, 16]:
            db.add(ProcurementSlot(
                mandi_id=mandi_id,
                scheduled_date=today,
                start_time=time(hour, 0),
                end_time=time(hour + 1, 0),
                allocated_capacity_qt=500.0,
                booked_capacity_qt=0.0,
                version=1
            ))
        db.commit()
        today_slots = db.query(ProcurementSlot).filter(
            ProcurementSlot.mandi_id == mandi_id,
            ProcurementSlot.scheduled_date == today
        ).order_by(ProcurementSlot.start_time.asc()).all()

    farmers = db.query(Farmer).all()
    if not farmers:
        demo_farmer = Farmer(
            farmer_uid="FARMER-DEMO-001",
            full_name="Rameshwar Patel",
            mobile_number="9876543210",
            land_size_hectares=4.5,
            allocated_quota_qt=120.0,
            consumed_quota_qt=0.0
        )
        db.add(demo_farmer)
        db.commit()
        farmers = [demo_farmer]

    f_ids = [f.farmer_id for f in farmers]
    s_ids = [s.slot_id for s in today_slots]
    now_ts = time_module.time()

    simulated_lots = [
        {
            "transaction_id": "TXN-SIM-101",
            "farmer_id": f_ids[0 % len(f_ids)],
            "slot_id": s_ids[0 % len(s_ids)],
            "moisture": 12.40,
            "qty_qt": 80.00,
            "state": "QUALITY_APPROVED",
            "enqueue": True,
            "elapsed_wait": 10.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": "TXN-SIM-102",
            "farmer_id": f_ids[1 % len(f_ids)],
            "slot_id": s_ids[1 % len(s_ids)],
            "moisture": 16.20,
            "qty_qt": 55.00,
            "state": "QUALITY_APPROVED",
            "enqueue": True,
            "elapsed_wait": 35.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": "TXN-SIM-103",
            "farmer_id": f_ids[2 % len(f_ids)],
            "slot_id": s_ids[2 % len(s_ids)],
            "moisture": 18.60,
            "qty_qt": 45.00,
            "state": "QUALITY_REJECTED",
            "enqueue": False,
            "elapsed_wait": 5.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": "TXN-SIM-104",
            "farmer_id": f_ids[3 % len(f_ids)],
            "slot_id": s_ids[3 % len(s_ids)],
            "moisture": 13.10,
            "qty_qt": 70.00,
            "state": "WEIGHED_GROSS",
            "enqueue": False,
            "elapsed_wait": 20.0,
            "gross": 105.00,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": "TXN-SIM-105",
            "farmer_id": f_ids[4 % len(f_ids)],
            "slot_id": s_ids[4 % len(s_ids)],
            "moisture": 11.90,
            "qty_qt": 60.00,
            "state": "PAYMENT_SETTLED",
            "enqueue": False,
            "elapsed_wait": 40.0,
            "gross": 95.00,
            "tare": 35.00,
            "payout": 136500.00,
        },
    ]

    processed = []
    for item in simulated_lots:
        existing = db.query(ProcurementLog).filter(
            ProcurementLog.transaction_id == item["transaction_id"]
        ).first()

        tok_sig = generate_booking_signature(item["farmer_id"], mandi_id, item["slot_id"], item["qty_qt"])

        if not existing:
            log = ProcurementLog(
                transaction_id=item["transaction_id"],
                farmer_id=item["farmer_id"],
                mandi_id=mandi_id,
                slot_id=item["slot_id"],
                scheduled_date=today,
                crop_moisture_pct=item["moisture"],
                gross_weight_qt=item["gross"],
                tare_weight_qt=item["tare"],
                net_weight_qt=item["qty_qt"],
                total_payout_inr=item["payout"],
                current_state=item["state"],
                token_signature=tok_sig,
                payout_block_hash=hashlib.sha256(f"PFMS_{item['transaction_id']}".encode()).hexdigest() if item["payout"] else None
            )
            db.add(log)
        else:
            existing.crop_moisture_pct = item["moisture"]
            existing.gross_weight_qt = item["gross"]
            existing.tare_weight_qt = item["tare"]
            existing.net_weight_qt = item["qty_qt"]
            existing.total_payout_inr = item["payout"]
            existing.current_state = item["state"]
            existing.token_signature = tok_sig
            if item["payout"]:
                existing.payout_block_hash = hashlib.sha256(f"PFMS_{item['transaction_id']}".encode()).hexdigest()

        if item["enqueue"]:
            score = calculate_dcdq_priority_score(
                planned_arrival_ts=now_ts,
                actual_arrival_ts=now_ts,
                moisture_pct=item["moisture"],
                elapsed_wait_minutes=item["elapsed_wait"],
                demurrage_score=item["qty_qt"] / 10.0
            )
            queue_manager.enqueue(
                mandi_id=mandi_id,
                transaction_id=item["transaction_id"],
                priority_score=score,
                arrival_ts=now_ts
            )
            processed.append({
                "transaction_id": item["transaction_id"],
                "state": item["state"],
                "moisture": item["moisture"],
                "priority_score": round(score, 2),
                "in_queue": True
            })
        else:
            queue_manager.remove(mandi_id, item["transaction_id"])
            processed.append({
                "transaction_id": item["transaction_id"],
                "state": item["state"],
                "moisture": item["moisture"],
                "in_queue": False
            })

    db.commit()
    active_queue = queue_manager.get_queue(mandi_id)

    return {
        "status": "SUCCESS",
        "mandi_id": mandi_id,
        "simulated_vehicles": processed,
        "active_queue_size": len(active_queue),
        "message": f"Successfully injected {len(processed)} showcase vehicles. Live queue reordered dynamically with DCDQ algorithm."
    }


@router.post(
    "/reset-showcase",
    summary="Reset Showcase Database to Clean State",
    description="Cleanly resets simulated and test transactions back to the baseline showcase state."
)
def reset_showcase_database(
    payload: dict = None,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR", "OPERATOR"]))
):
    from backend.app.models.log import ProcurementLog
    from backend.app.services.queue_manager import queue_manager

    raw_mandi = payload.get("mandi_id") if payload else 1
    try:
        mandi_id = int(raw_mandi) if raw_mandi is not None and str(raw_mandi).strip() != "" else 1
    except (ValueError, TypeError):
        mandi_id = 1

    # Clear queue
    queue_manager.clear(f"mandi:queue:{mandi_id}")

    # Remove temporary simulated transactions
    db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id.like("TXN-SIM-%")
    ).delete(synchronize_session=False)

    db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id.like("TXN-E2E-%")
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "status": "SUCCESS",
        "mandi_id": mandi_id,
        "message": f"Showcase transactions and priority queue for Mandi #{mandi_id} have been cleanly reset."
    }

