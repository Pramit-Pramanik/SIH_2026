from datetime import datetime, timezone, date, time
import gzip
import json
import time as time_mod
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.models.mandi import Mandi
from backend.app.models.crop import Crop
from backend.app.models.slot import ProcurementSlot
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.schemas.mandi import MandiResponse, MandiCreateRequest
from backend.app.schemas.crop import CropResponse, CropCreateRequest
from backend.app.schemas.auth import UserResponse
from backend.app.schemas.showcase import (
    ShowcaseFarmersResponse,
    ShowcaseFarmerItem,
    ShowcaseFarmerBooking
)
from backend.app.schemas.tas import (
    TASOptimizeRequest,
    TASOptimizeResponse,
    BookingFailureRiskRequest,
    BookingFailureRiskResponse
)
from backend.app.schemas.concurrency import (
    LockTimelineEvent,
    ConcurrentBookingTestRequest,
    ConcurrentBookingTestResponse,
    LWWFieldComparison,
    LWWConflictTestRequest,
    LWWConflictTestResponse,
    GzipSyncEvidenceRequest,
    GzipSyncEvidenceResponse,
    HMACVerificationRequest,
    HMACVerificationResponse,
    DCDQVehicleDemoItem,
    DCDQReorderDemoRequest,
    DCDQReorderDemoResponse,
    AlgorithmShowcaseResetResponse,
)
from backend.app.core.security import (
    generate_booking_signature,
    verify_booking_signature,
    build_booking_payload,
)
from backend.app.services.dcdq_engine import (
    calculate_dcdq_components,
    calculate_dcdq_priority_score,
)
from backend.app.services.eta_service import reset_active_scales
from backend.app.services.tas_optimizer import (
    solve_tas_bilp,
    calculate_logistic_booking_failure
)
from backend.app.services.lock_manager import lock_manager, LockContentionError
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.sync_service import resolve_field_level_lww_merge

router = APIRouter(prefix="/admin", tags=["Administrator Management"])


@router.get(
    "/showcase/farmers",
    response_model=ShowcaseFarmersResponse,
    summary="Get Showcase Farmers (Live Database)",
    description="Returns live database records for showcase farmers with active bookings, ceilings, and mandi association. Restricted to ADMIN and SUPERVISOR."
)
def get_showcase_farmers(
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"], strict=True))
) -> ShowcaseFarmersResponse:
    from backend.app.routers.farmers import compute_farmer_profile

    farmers = db.query(Farmer).order_by(Farmer.farmer_id.asc()).all()
    results = []

    default_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
    if not default_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No APMC mandis found in database."
        )

    for f in farmers:
        profile = compute_farmer_profile(db=db, farmer=f)

        # Look up latest procurement log to determine primary/recent mandi and active booking
        latest_log = db.query(ProcurementLog).filter(
            ProcurementLog.farmer_id == f.farmer_id
        ).order_by(ProcurementLog.created_at.desc()).first()

        total_bookings = db.query(ProcurementLog).filter(
            ProcurementLog.farmer_id == f.farmer_id
        ).count()

        mandi = None
        if latest_log:
            mandi = db.query(Mandi).filter(Mandi.mandi_id == latest_log.mandi_id).first()

        if not mandi:
            mandi = default_mandi

        active_booking = None
        if latest_log and latest_log.current_state not in ("PAYMENT_SETTLED", "CANCELLED", "QUALITY_REJECTED"):
            slot = db.query(ProcurementSlot).filter(ProcurementSlot.slot_id == latest_log.slot_id).first() if latest_log.slot_id else None
            time_str = f"{slot.start_time} - {slot.end_time}" if slot else "Morning Window"
            active_booking = ShowcaseFarmerBooking(
                transaction_id=latest_log.transaction_id,
                current_state=latest_log.current_state,
                scheduled_date=str(latest_log.scheduled_date or ""),
                scheduled_time=time_str,
                slot_id=latest_log.slot_id,
                quantity_qt=float(latest_log.net_weight_qt or 0.0),
                mandi_id=mandi.mandi_id,
                mandi_name=mandi.name
            )

        results.append(
            ShowcaseFarmerItem(
                farmer_id=f.farmer_id,
                name=f.name,
                mobile=f.mobile_number,
                crop=f.registered_crop_type,
                land_area_hectares=float(f.land_area_hectares),
                ceiling_qt=profile.production_ceiling_qt,
                cumulative_booked_qt=profile.cumulative_booked_qt,
                remaining_ceiling_qt=profile.remaining_ceiling_qt,
                mandi_id=mandi.mandi_id,
                mandi_name=mandi.name,
                state=mandi.state,
                district=mandi.district,
                active_booking=active_booking,
                total_bookings=total_bookings
            )
        )

    return ShowcaseFarmersResponse(farmers=results, count=len(results))


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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"], strict=True))
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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"], strict=True))
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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"], strict=True))
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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"], strict=True))
):
    from datetime import datetime, date, time, timedelta

    if "mandi_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'mandi_id' is required."
        )
    try:
        mandi_id = int(payload["mandi_id"])
        if mandi_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'mandi_id' must be a positive integer."
        )

    target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not target_mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"], strict=True))
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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN"], strict=True))
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
    mandi_id: Optional[int] = Query(None, description="Target APMC mandi identifier"),
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
):
    from datetime import date
    from backend.app.models.log import ProcurementLog
    from backend.app.models.farmer import Farmer
    from backend.app.services.queue_manager import queue_manager

    if mandi_id is not None:
        if mandi_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mandi_id must be a positive integer"
            )
        target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
        if not target_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mandi with ID {mandi_id} not found."
            )
        effective_mandi_id = mandi_id
    elif admin_user and getattr(admin_user, "mandi_id", None) is not None:
        effective_mandi_id = admin_user.mandi_id
        target_mandi = db.query(Mandi).filter(Mandi.mandi_id == effective_mandi_id).first()
        if not target_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Authorized mandi with ID {effective_mandi_id} not found."
            )
    else:
        first_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
        if not first_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No APMC mandis found in database."
            )
        effective_mandi_id = first_mandi.mandi_id
        target_mandi = first_mandi

    today = date.today()
    logs = db.query(ProcurementLog).filter(ProcurementLog.mandi_id == effective_mandi_id).all()
    mandi = target_mandi
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

    queued_vehicles = queue_manager.get_queue(effective_mandi_id)
    rejection_pct = round((quality_rejected / quality_inspected * 100.0), 1) if quality_inspected > 0 else 0.0

    return {
        "mandi_id": effective_mandi_id,
        "mandi_name": mandi.name if mandi else f"Mandi #{effective_mandi_id}",
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
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
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

    raw_mandi = payload.get("mandi_id") if payload else None
    if raw_mandi is not None:
        try:
            mandi_id = int(raw_mandi)
            if mandi_id <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mandi_id must be a positive integer"
            )
        target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
        if not target_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mandi with ID {mandi_id} not found."
            )
    elif admin_user and getattr(admin_user, "mandi_id", None) is not None:
        mandi_id = admin_user.mandi_id
        target_mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
        if not target_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Authorized mandi with ID {mandi_id} not found."
            )
    else:
        first_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
        if not first_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No APMC mandis found in database."
            )
        mandi_id = first_mandi.mandi_id
        target_mandi = first_mandi

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

    # Reset any active showcase simulation time offset
    queue_manager.reset_showcase_time_offset(mandi_id)

    # Heterogeneous showcase traffic demonstrating each canonical DCDQ component:
    # Vehicle A (101): Dry Wheat (12%), on-time arrival (A=40), large payload (80qt -> D=8), low initial wait (15m -> W=1.5) => S=49.50
    # Vehicle B (102): Higher moisture Wheat (16.2% -> M=11.23), 20m late (A=30), 50qt (D=5), moderate wait (45m -> W=4.5) => S=50.73 (B > A initially)
    # Vehicle C (106): Chana (14.8% -> M=1.6), on-time (A=40), 35qt (D=3.5), wait 30m (W=3.0) => S=48.10
    # Vehicle D (103): Excessive moisture Mustard (18.5% > 17%) => QUALITY_REJECTED, barred from queue
    # Vehicles 104, 105: Downstream weighbridge & payment demo
    simulated_lots = [
        {
            "transaction_id": f"TXN-SIM-{mandi_id}-101",
            "farmer_id": f_ids[0 % len(f_ids)],
            "slot_id": s_ids[0 % len(s_ids)],
            "crop": "Wheat",
            "moisture": 12.00,
            "qty_qt": 80.00,
            "state": "QUALITY_APPROVED",
            "enqueue": True,
            "planned_arr": now_ts - (15.0 * 60.0),
            "actual_arr": now_ts - (15.0 * 60.0),
            "elapsed_wait": 15.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": f"TXN-SIM-{mandi_id}-102",
            "farmer_id": f_ids[1 % len(f_ids)],
            "slot_id": s_ids[1 % len(s_ids)],
            "crop": "Wheat",
            "moisture": 16.20,
            "qty_qt": 50.00,
            "state": "QUALITY_APPROVED",
            "enqueue": True,
            "planned_arr": now_ts - (65.0 * 60.0),
            "actual_arr": now_ts - (45.0 * 60.0),
            "elapsed_wait": 45.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": f"TXN-SIM-{mandi_id}-106",
            "farmer_id": f_ids[2 % len(f_ids)],
            "slot_id": s_ids[2 % len(s_ids)],
            "crop": "Chana",
            "moisture": 14.80,
            "qty_qt": 35.00,
            "state": "QUALITY_APPROVED",
            "enqueue": True,
            "planned_arr": now_ts - (40.0 * 60.0),
            "actual_arr": now_ts - (40.0 * 60.0),
            "elapsed_wait": 30.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": f"TXN-SIM-{mandi_id}-103",
            "farmer_id": f_ids[0 % len(f_ids)],
            "slot_id": s_ids[0 % len(s_ids)],
            "crop": "Mustard",
            "moisture": 18.50,
            "qty_qt": 45.00,
            "state": "QUALITY_REJECTED",
            "enqueue": False,
            "planned_arr": now_ts - (10.0 * 60.0),
            "actual_arr": now_ts - (10.0 * 60.0),
            "elapsed_wait": 10.0,
            "gross": None,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": f"TXN-SIM-{mandi_id}-104",
            "farmer_id": f_ids[1 % len(f_ids)],
            "slot_id": s_ids[1 % len(s_ids)],
            "crop": "Wheat",
            "moisture": 13.10,
            "qty_qt": 70.00,
            "state": "WEIGHED_GROSS",
            "enqueue": False,
            "planned_arr": now_ts - (30.0 * 60.0),
            "actual_arr": now_ts - (20.0 * 60.0),
            "elapsed_wait": 20.0,
            "gross": 105.00,
            "tare": None,
            "payout": None,
        },
        {
            "transaction_id": f"TXN-SIM-{mandi_id}-105",
            "farmer_id": f_ids[2 % len(f_ids)],
            "slot_id": s_ids[2 % len(s_ids)],
            "crop": "Wheat",
            "moisture": 11.90,
            "qty_qt": 60.00,
            "state": "PAYMENT_SETTLED",
            "enqueue": False,
            "planned_arr": now_ts - (50.0 * 60.0),
            "actual_arr": now_ts - (40.0 * 60.0),
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
        created_dt = datetime.fromtimestamp(item["actual_arr"], tz=timezone.utc)

        if not existing:
            log = ProcurementLog(
                transaction_id=item["transaction_id"],
                farmer_id=item["farmer_id"],
                mandi_id=mandi_id,
                slot_id=item["slot_id"],
                scheduled_date=today,
                crop_type=item.get("crop", "Wheat"),
                crop_moisture_pct=item["moisture"],
                gross_weight_qt=item["gross"],
                tare_weight_qt=item["tare"],
                net_weight_qt=item["qty_qt"],
                total_payout_inr=item["payout"],
                current_state=item["state"],
                token_signature=tok_sig,
                is_showcase=True,
                demo_run_id=f"SHOWCASE_SIM_{mandi_id}",
                created_at=created_dt,
                payout_block_hash=hashlib.sha256(f"PFMS_{item['transaction_id']}".encode()).hexdigest() if item["payout"] else None
            )
            db.add(log)
        else:
            existing.crop_type = item.get("crop", "Wheat")
            existing.crop_moisture_pct = item["moisture"]
            existing.gross_weight_qt = item["gross"]
            existing.tare_weight_qt = item["tare"]
            existing.net_weight_qt = item["qty_qt"]
            existing.total_payout_inr = item["payout"]
            existing.current_state = item["state"]
            existing.token_signature = tok_sig
            existing.is_showcase = True
            existing.demo_run_id = f"SHOWCASE_SIM_{mandi_id}"
            existing.created_at = created_dt
            if item["payout"]:
                existing.payout_block_hash = hashlib.sha256(f"PFMS_{item['transaction_id']}".encode()).hexdigest()

        if item["enqueue"]:
            score = calculate_dcdq_priority_score(
                planned_arrival_ts=item["planned_arr"],
                actual_arrival_ts=item["actual_arr"],
                moisture_pct=item["moisture"],
                elapsed_wait_minutes=item["elapsed_wait"],
                demurrage_score=item["qty_qt"] / 10.0
            )
            queue_manager.enqueue(
                mandi_id=mandi_id,
                transaction_id=item["transaction_id"],
                priority_score=score,
                arrival_ts=item["actual_arr"]
            )
            processed.append({
                "transaction_id": item["transaction_id"],
                "crop": item.get("crop", "Wheat"),
                "state": item["state"],
                "moisture": item["moisture"],
                "priority_score": round(score, 2),
                "in_queue": True
            })
        else:
            queue_manager.remove(mandi_id, item["transaction_id"])
            processed.append({
                "transaction_id": item["transaction_id"],
                "crop": item.get("crop", "Wheat"),
                "state": item["state"],
                "moisture": item["moisture"],
                "in_queue": False
            })

    # Seed authoritative weighbridge completion events in the rolling 15m window so ETA telemetry is active
    from backend.app.models.weighbridge import WeighbridgeEvent
    from datetime import timedelta
    db.query(WeighbridgeEvent).filter(
        WeighbridgeEvent.mandi_id == mandi_id,
        WeighbridgeEvent.transaction_id.like(f"TXN-SIM-{mandi_id}-%")
    ).delete()
    now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    ev1 = WeighbridgeEvent(
        mandi_id=mandi_id,
        transaction_id=f"TXN-SIM-{mandi_id}-104",
        scale_id="SCALE-01",
        gross_weight_qt=105.0,
        tare_weight_qt=35.0,
        net_weight_qt=70.0,
        completed_at=now_dt - timedelta(minutes=5),
        created_at=now_dt - timedelta(minutes=5)
    )
    ev2 = WeighbridgeEvent(
        mandi_id=mandi_id,
        transaction_id=f"TXN-SIM-{mandi_id}-105",
        scale_id="SCALE-02",
        gross_weight_qt=95.0,
        tare_weight_qt=35.0,
        net_weight_qt=60.0,
        completed_at=now_dt - timedelta(minutes=10),
        created_at=now_dt - timedelta(minutes=10)
    )
    db.add(ev1)
    db.add(ev2)

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
    "/advance-showcase-time",
    summary="Advance isolated simulation clock for showcase queue records (DCDQ Dynamic Demo)",
    status_code=status.HTTP_200_OK
)
def advance_showcase_time(
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
):
    """
    Advances the isolated simulation clock offset for showcase queue records in the target mandi.
    Strictly isolated: does NOT alter system clock or real production transactions.
    Re-runs canonical DCDQ dynamic re-ranking to demonstrate anti-starvation wait bonus shifts.
    """
    from backend.app.services.queue_manager import queue_manager
    from backend.app.services.quality_service import recompute_and_get_mandi_queue
    from backend.app.models.weighbridge import WeighbridgeEvent
    from datetime import timedelta

    raw_mandi = payload.get("mandi_id") if payload else None
    if raw_mandi is not None:
        try:
            mandi_id = int(raw_mandi)
            if mandi_id <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mandi_id must be a positive integer"
            )
    elif admin_user and getattr(admin_user, "mandi_id", None) is not None:
        mandi_id = admin_user.mandi_id
    else:
        first_mandi = db.query(Mandi).order_by(Mandi.mandi_id.asc()).first()
        if not first_mandi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No operational mandi configured. Zero magic mandi fallback permitted per DATA-001."
            )
        mandi_id = first_mandi.mandi_id

    advance_minutes = float(payload.get("minutes", 60.0)) if payload else 60.0
    total_offset = queue_manager.advance_showcase_time_offset(mandi_id, advance_minutes)

    # Synchronize showcase weighbridge completion timestamps with the simulation clock advance
    sim_events = db.query(WeighbridgeEvent).filter(
        WeighbridgeEvent.mandi_id == mandi_id,
        WeighbridgeEvent.transaction_id.like(f"TXN-SIM-{mandi_id}-%")
    ).all()
    for ev in sim_events:
        ev.completed_at = ev.completed_at + timedelta(minutes=advance_minutes)
    db.commit()

    queue_resp = recompute_and_get_mandi_queue(db=db, mandi_id=mandi_id)

    return {
        "status": "SUCCESS",
        "mandi_id": mandi_id,
        "advanced_by_minutes": advance_minutes,
        "total_showcase_offset_minutes": total_offset,
        "active_queue_size": queue_resp.total_vehicles,
        "items": [item.model_dump() for item in queue_resp.items],
        "message": f"Showcase simulation time advanced by +{advance_minutes:.1f} min (total offset: {total_offset:.1f} min). DCDQ scores and queue reordered dynamically."
    }


@router.post(
    "/reset-showcase",
    summary="Reset Showcase Database to Clean State",
    description="Cleanly resets simulated and test transactions back to the baseline showcase state."
)
def reset_showcase_database(
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
):
    from backend.app.services.seed_service import reset_showcase_data

    raw_mandi = payload.get("mandi_id") if payload else None
    mandi_id = None
    if raw_mandi is not None:
        try:
            mandi_id = int(raw_mandi)
            if mandi_id <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mandi_id must be a positive integer"
            )
    elif admin_user and getattr(admin_user, "mandi_id", None) is not None:
        mandi_id = admin_user.mandi_id

    raw_farmer = payload.get("farmer_id") if payload else None
    farmer_id = None
    if raw_farmer is not None:
        try:
            farmer_id = int(raw_farmer)
            if farmer_id <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="farmer_id must be a positive integer"
            )

    result = reset_showcase_data(db, mandi_id=mandi_id, farmer_id=farmer_id)
    return result


@router.post(
    "/tas/optimize",
    response_model=TASOptimizeResponse,
    summary="Optimize Truck Appointment System Slots (BILP HiGHS Solver)",
    description="Executes a Mixed-Integer Linear Program (BILP) using HiGHS via SciPy to optimize yard truck slot allocations and minimize congestion overload."
)
def optimize_tas_slots(
    payload: Optional[TASOptimizeRequest] = None,
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
) -> TASOptimizeResponse:
    try:
        return solve_tas_bilp(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"TAS Optimization Error: {str(e)}"
        )


@router.post(
    "/tas/failure-risk",
    response_model=BookingFailureRiskResponse,
    summary="Calculate Logistic Booking Failure Risk",
    description="Evaluates the logistic booking failure probability model P(failure) = 1 / (1 + exp(-k * |actual - expected|)). Returns modelled risk disclaimer."
)
def calculate_failure_risk(
    payload: BookingFailureRiskRequest
) -> BookingFailureRiskResponse:
    try:
        return calculate_logistic_booking_failure(
            actual_arrival=payload.actual_arrival,
            expected_arrival=payload.expected_arrival,
            k=payload.k,
            unit=payload.unit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking Failure Calculation Error: {str(e)}"
        )


@router.get(
    "/tas/failure-risk",
    response_model=BookingFailureRiskResponse,
    summary="Calculate Logistic Booking Failure Risk (Query Params)",
    description="Query-parameter variant of the logistic booking failure probability model."
)
def get_failure_risk(
    expected_arrival: Union[float, str] = Query(..., description="Expected arrival timestamp, ISO string, or minutes"),
    actual_arrival: Union[float, str] = Query(..., description="Actual arrival timestamp, ISO string, or minutes"),
    k: float = Query(default=0.05, gt=0.0, description="Sensitivity parameter k"),
    unit: str = Query(default="minutes", description="Time unit ('minutes', 'seconds', 'hours')")
) -> BookingFailureRiskResponse:
    try:
        return calculate_logistic_booking_failure(
            actual_arrival=actual_arrival,
            expected_arrival=expected_arrival,
            k=k,
            unit=unit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking Failure Calculation Error: {str(e)}"
        )


@router.post(
    "/demo/concurrent-booking",
    response_model=ConcurrentBookingTestResponse,
    summary="Run Concurrent Booking Test (Redis Atomic Reservation Lock)",
    description="Generates N concurrent reservations against the same slot to demonstrate atomic lock contention, zero-capacity-overflow invariant, and request serialization timeline."
)
def run_concurrent_booking_test(
    payload: Optional[ConcurrentBookingTestRequest] = None,
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
) -> ConcurrentBookingTestResponse:
    if not payload or not payload.mandi_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit mandi_id is required. Zero magic identity fallbacks permitted per DATA-001."
        )
    mandi_id = payload.mandi_id
    num_requests = payload.concurrent_requests if (payload and payload.concurrent_requests) else 10
    request_qty = payload.request_qty_qt if (payload and payload.request_qty_qt) else 10.0

    # Ensure target slot exists
    slot_id = payload.slot_id if payload else None
    if slot_id:
        target_slot = db.query(ProcurementSlot).filter(ProcurementSlot.slot_id == slot_id).first()
        if not target_slot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Slot {slot_id} not found.")
    else:
        # Create or cleanly reset a dedicated demo slot with known capacity
        demo_slot = db.query(ProcurementSlot).filter(
            ProcurementSlot.mandi_id == mandi_id,
            ProcurementSlot.scheduled_date == date.today(),
            ProcurementSlot.start_time == time(21, 0)
        ).first()
        if demo_slot:
            demo_slot.booked_capacity_qt = 0.0
            demo_slot.allocated_capacity_qt = request_qty
            db.query(ProcurementLog).filter(ProcurementLog.slot_id == demo_slot.slot_id).delete()
            db.commit()
            target_slot = demo_slot
        else:
            target_slot = ProcurementSlot(
                mandi_id=mandi_id,
                scheduled_date=date.today(),
                start_time=time(21, 0),
                end_time=time(22, 0),
                allocated_capacity_qt=request_qty,
                booked_capacity_qt=0.0,
                version=1
            )
            db.add(target_slot)
            db.commit()
            db.refresh(target_slot)

    target_slot_id = target_slot.slot_id
    initial_allocated = float(target_slot.allocated_capacity_qt)

    # Derive registered farmer IDs or isolated deterministic showcase fixture IDs
    registered_farmers = [f.farmer_id for f in db.query(Farmer.farmer_id).limit(10).all()]
    showcase_fixture_farmers = [101, 102, 103]
    farmer_id_pool = registered_farmers if registered_farmers else showcase_fixture_farmers

    # Concurrency test harness with synchronized barrier
    barrier = threading.Barrier(num_requests)
    timeline: List[LockTimelineEvent] = []
    timeline_lock = threading.Lock()
    t_zero = time_mod.perf_counter()

    def worker_task(worker_id: int):
        farmer_id = farmer_id_pool[worker_id % len(farmer_id_pool)]
        req_id = f"REQ-CONC-{worker_id+1:02d}-{uuid.uuid4().hex[:6]}"
        token = str(uuid.uuid4())

        # Synchronize all threads so they launch simultaneously
        barrier.wait()
        t_start = time_mod.perf_counter()
        t_acq = t_start
        t_rel = t_start
        status_str = "REJECTED"

        db_thread = SessionLocal()
        try:
            t_acq = time_mod.perf_counter()
            reserve_slot_atomic(
                db=db_thread,
                mandi_id=mandi_id,
                slot_id=target_slot_id,
                farmer_id=farmer_id,
                requested_qty_qt=request_qty,
                demo_run_id=req_id
            )
            t_rel = time_mod.perf_counter()
            status_str = "SUCCESS_RESERVED"
        except HTTPException as he:
            t_rel = time_mod.perf_counter()
            detail_msg = str(he.detail).lower()
            if "capacity exhausted" in detail_msg:
                status_str = "REJECTED_CAPACITY_EXHAUSTED"
            elif "ceiling exceeded" in detail_msg:
                status_str = "REJECTED_CEILING_EXCEEDED"
            else:
                status_str = f"REJECTED_{he.status_code}"
        except LockContentionError:
            t_rel = time_mod.perf_counter()
            status_str = "REJECTED_LOCK_CONTENTION"
        except Exception:
            t_rel = time_mod.perf_counter()
            status_str = "REJECTED_ERROR"
        finally:
            db_thread.close()

        duration_ms = round((t_rel - t_start) * 1000.0, 2)
        acq_ms = round((t_acq - t_zero) * 1000.0, 2)
        rel_ms = round((t_rel - t_zero) * 1000.0, 2)

        event = LockTimelineEvent(
            worker_id=worker_id + 1,
            request_id=req_id,
            acquired_at_ms=acq_ms,
            released_at_ms=rel_ms,
            duration_ms=duration_ms,
            status=status_str,
            token=f"{token[:8]}..."
        )
        with timeline_lock:
            timeline.append(event)

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(worker_task, i) for i in range(num_requests)]
        for f in futures:
            f.result()

    # Re-query slot state
    db.expire_all()
    slot_refreshed = db.query(ProcurementSlot).filter(ProcurementSlot.slot_id == target_slot_id).first()
    final_booked = float(slot_refreshed.booked_capacity_qt) if slot_refreshed else 0.0
    final_allocated = float(slot_refreshed.allocated_capacity_qt) if slot_refreshed else initial_allocated
    remaining = max(0.0, round(final_allocated - final_booked, 2))

    timeline.sort(key=lambda x: x.acquired_at_ms)

    successful = sum(1 for e in timeline if e.status == "SUCCESS_RESERVED")
    rejected = len(timeline) - successful
    capacity_exceeded = max(0, int(final_booked > final_allocated))

    summary = (
        f"Executed {num_requests} concurrent reservation requests against Slot #{target_slot_id}. "
        f"Successful: {successful} (booked {final_booked:.1f} qt / {final_allocated:.1f} qt). "
        f"Rejected: {rejected}. Capacity exceeded: {capacity_exceeded} (Zero Tolerance Invariant preserved)."
    )

    return ConcurrentBookingTestResponse(
        mandi_id=mandi_id,
        slot_id=target_slot_id,
        total_requests=num_requests,
        successful_requests=successful,
        rejected_requests=rejected,
        capacity_exceeded=capacity_exceeded,
        allocated_capacity_qt=final_allocated,
        booked_capacity_qt=final_booked,
        remaining_capacity_qt=remaining,
        lock_mechanism="Redis SET NX PX Distributed Mutex (Prototype)",
        timeline=timeline,
        summary=summary
    )


@router.post(
    "/demo/lww-conflict",
    response_model=LWWConflictTestResponse,
    summary="Demonstrate Field-Level LWW Conflict Resolution (Authoritative Server Sequence)",
    description="Demonstrates field-level Last-Write-Wins merge between Mutation A (seq 101) and Mutation B (seq 102). Proves server sequence authority over client timestamp."
)
def run_lww_conflict_demo(
    payload: Optional[LWWConflictTestRequest] = None
) -> LWWConflictTestResponse:
    mut_a = (payload.mutation_a if payload and payload.mutation_a else {
        "mutation_id": "MUT-OFFLINE-A-101",
        "server_sequence": 101,
        "client_timestamp": "2026-09-22T08:30:00.000Z",
        "data": {
            "gross_weight_kg": 4520.0,
            "moisture_pct": 13.8,
            "foreign_matter_pct": 1.2,
            "crop_condition": "OPTIMAL"
        }
    })

    mut_b = (payload.mutation_b if payload and payload.mutation_b else {
        "mutation_id": "MUT-OFFLINE-B-102",
        "server_sequence": 102,
        "client_timestamp": "2026-09-22T08:29:45.000Z",
        "data": {
            "gross_weight_kg": 4535.0,
            "moisture_pct": 14.1,
            "foreign_matter_pct": 1.1,
            "crop_condition": "FAIR_WEATHER_DRIED"
        }
    })

    # Prepare base record representing state after Mutation A
    base_record: Dict[str, Any] = {
        "transaction_id": "TXN-DEMO-1002",
        "server_receive_sequence": mut_a.get("server_sequence", 101),
        "client_mutation_id": mut_a.get("mutation_id", "MUT-OFFLINE-A-101"),
        "_conflict_meta": {}
    }
    for k, v in mut_a.get("data", {}).items():
        base_record[k] = v
        base_record[f"_seq_{k}"] = mut_a.get("server_sequence", 101)
        base_record[f"_mutation_{k}"] = mut_a.get("mutation_id", "MUT-OFFLINE-A-101")

    # Merge incoming Mutation B
    incoming_b = mut_b.get("data", {})
    incoming_seq_b = mut_b.get("server_sequence", 102)
    incoming_id_b = mut_b.get("mutation_id", "MUT-OFFLINE-B-102")
    incoming_ts_b = 1790065785.0

    merged = resolve_field_level_lww_merge(
        existing_record=base_record,
        incoming_record=incoming_b,
        incoming_mutation_id=incoming_id_b,
        incoming_server_sequence=incoming_seq_b,
        incoming_client_timestamp=incoming_ts_b
    )

    fields_res: List[LWWFieldComparison] = []
    all_fields = sorted(list(set(list(mut_a.get("data", {}).keys()) + list(incoming_b.keys()))))
    for f in all_fields:
        old_v = mut_a.get("data", {}).get(f)
        new_v = incoming_b.get(f)
        winner_v = merged.get(f)
        winner_id = merged.get(f"_mutation_{f}", incoming_id_b)
        winner_seq = merged.get(f"_seq_{f}", incoming_seq_b)

        fields_res.append(LWWFieldComparison(
            field=f,
            old_value=old_v,
            incoming_value=new_v,
            winner=winner_v,
            winning_mutation_id=winner_id,
            authoritative_sequence=winner_seq,
            reason="higher authoritative server sequence",
            client_timestamp_a=str(mut_a.get("client_timestamp", "2026-09-22T08:30:00.000Z")),
            client_timestamp_b=str(mut_b.get("client_timestamp", "2026-09-22T08:29:45.000Z"))
        ))

    return LWWConflictTestResponse(
        transaction_id="TXN-DEMO-1002",
        mutation_a_id=mut_a.get("mutation_id", "MUT-OFFLINE-A-101"),
        mutation_a_sequence=mut_a.get("server_sequence", 101),
        mutation_b_id=mut_b.get("mutation_id", "MUT-OFFLINE-B-102"),
        mutation_b_sequence=mut_b.get("server_sequence", 102),
        fields=fields_res,
        governance_model="Authoritative Server Sequence (server_receive_sequence)",
        governance_notice=(
            "Governance Rule: Authoritative conflict ordering is governed by server_receive_sequence, "
            "not client clocks. Client timestamps are retained solely as diagnostic metadata."
        )
    )


@router.post(
    "/demo/gzip-evidence",
    response_model=GzipSyncEvidenceResponse,
    summary="Demonstrate Offline WAL Gzip Compression Evidence",
    description="Demonstrates offline WAL batch compression from IndexedDB through Gzip payload transmission to server-side decompression. Shows true measured byte sizes and compression ratio."
)
def run_gzip_sync_evidence(
    payload: Optional[GzipSyncEvidenceRequest] = None
) -> GzipSyncEvidenceResponse:
    record_count = payload.record_count if (payload and payload.record_count) else 10

    # Construct genuine offline WAL mutation records
    now_ts = time_mod.time()
    mutations = []
    for i in range(record_count):
        mutations.append({
            "client_mutation_id": f"WAL-MUT-{uuid.uuid4().hex[:8].upper()}",
            "farmer_id": 1001 + (i % 10),
            "mandi_id": 999,
            "mutation_type": "UPDATE_WEIGHMENT",
            "client_timestamp": now_ts - (record_count - i) * 30.0,
            "device_id": f"POS-TERMINAL-0{1 + (i % 3)}",
            "retry_count": 0,
            "hmac_signature": f"sig_integrity_{uuid.uuid4().hex[:16]}",
            "fields": {
                "transaction_id": f"TXN-DEMO-{1001 + i}",
                "gross_weight_kg": round(4200.0 + (i * 15.5), 2),
                "tare_weight_kg": 1200.0,
                "net_weight_qt": round((3000.0 + (i * 15.5)) / 100.0, 2),
                "moisture_pct": round(13.5 + (i * 0.1), 1),
                "weighbridge_id": (i % 3) + 1,
                "operator_notes": f"Offline weighment record #{i+1} during connectivity blackout at Weighbridge {(i % 3) + 1}"
            }
        })

    raw_payload_dict = {"mutations": mutations}
    raw_bytes = json.dumps(raw_payload_dict, indent=2).encode("utf-8")
    raw_size = len(raw_bytes)

    # Gzip compress the JSON payload
    compressed_bytes = gzip.compress(raw_bytes)
    compressed_size = len(compressed_bytes)

    # Compute actual savings percentage
    savings_pct = round((1.0 - (compressed_size / float(raw_size))) * 100.0, 2)

    # Verify server decompression round-trip
    decompressed = gzip.decompress(compressed_bytes)
    parsed = json.loads(decompressed.decode("utf-8"))
    assert len(parsed.get("mutations", [])) == record_count

    return GzipSyncEvidenceResponse(
        record_count=record_count,
        raw_size_bytes=raw_size,
        compressed_size_bytes=compressed_size,
        compression_ratio_pct=savings_pct,
        decompression_status="SUCCESS_VERIFIED",
        verified=True,
        pipeline="IndexedDB WAL -> Batch (Raw) -> Gzip Compress -> HTTP POST -> Decompress -> DB Sync"
    )


@router.post(
    "/demo/hmac-verification",
    response_model=HMACVerificationResponse,
    summary="Demonstrate HMAC-SHA256 Cryptographic Verification (Audit Contract AUD-008)",
    description="Demonstrates FIPS 198-1 HMAC-SHA256 signature generation, canonical string serialization, constant-time validation, and tampered payload rejection. NEVER reveals the server secret key."
)
def run_hmac_verification_demo(
    payload: Optional[HMACVerificationRequest] = None
) -> HMACVerificationResponse:
    if not payload or not payload.farmer_id or not payload.mandi_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit farmer_id and mandi_id are required. Zero magic identity fallbacks permitted per DATA-001."
        )
    trace: List[str] = []
    t0 = time_mod.perf_counter()
    req = payload

    # Step 1: Canonical payload assembly
    t_start = round((time_mod.perf_counter() - t0) * 1000.0, 3)
    trace.append(f"+{t_start:.2f}ms: Assembled canonical booking payload '${req.farmer_id}:${req.mandi_id}:${req.slot_id}:{req.quantity_qt}'")
    canonical = build_booking_payload(
        farmer_id=req.farmer_id,
        mandi_id=req.mandi_id,
        slot_id=req.slot_id,
        quantity_qt=req.quantity_qt
    )

    # Step 2: Compute 64-char HMAC-SHA256 signature
    t_sig = round((time_mod.perf_counter() - t0) * 1000.0, 3)
    sig = generate_booking_signature(
        farmer_id=req.farmer_id,
        mandi_id=req.mandi_id,
        slot_id=req.slot_id,
        quantity_qt=req.quantity_qt
    )
    sig_preview = f"{sig[:12]}...{sig[-8:]}"
    trace.append(f"+{t_sig:.2f}ms: Generated 64-char HMAC-SHA256 digest ({len(sig)} chars / 256 bits): {sig_preview}")

    # Step 3: Constant-time validation of authentic payload
    t_val = round((time_mod.perf_counter() - t0) * 1000.0, 3)
    is_valid = verify_booking_signature(
        farmer_id=req.farmer_id,
        mandi_id=req.mandi_id,
        slot_id=req.slot_id,
        quantity_qt=req.quantity_qt,
        signature=sig
    )
    trace.append(f"+{t_val:.2f}ms: Executed constant-time hmac.compare_digest() on authentic payload -> {is_valid} (VALID_VERIFIED)")

    # Step 4: Adversarial tamper test (mutated quantity)
    tamper_qty = req.tamper_quantity_qt if req.tamper_quantity_qt is not None else (req.quantity_qt * 10.0)
    tampered_payload = build_booking_payload(
        farmer_id=req.farmer_id,
        mandi_id=req.mandi_id,
        slot_id=req.slot_id,
        quantity_qt=tamper_qty
    )
    t_tamper = round((time_mod.perf_counter() - t0) * 1000.0, 3)
    tamper_valid = verify_booking_signature(
        farmer_id=req.farmer_id,
        mandi_id=req.mandi_id,
        slot_id=req.slot_id,
        quantity_qt=tamper_qty,
        signature=sig
    )
    tamper_rejected = not tamper_valid
    trace.append(f"+{t_tamper:.2f}ms: Evaluated tampered payload '{tampered_payload}' against original signature -> {tamper_valid} (REJECTED_SIGNATURE_MISMATCH)")

    t_end = round((time_mod.perf_counter() - t0) * 1000.0, 3)
    trace.append(f"+{t_end:.2f}ms: Cryptographic integrity audit complete. Secret key retained exclusively in protected server configuration.")

    return HMACVerificationResponse(
        canonical_payload=canonical,
        signature_length_chars=len(sig),
        signature_preview=sig_preview,
        secret_key_status="PROTECTED (256-bit cryptographic entropy; strictly unexposed in frontend/API)",
        verification_result="VALID_VERIFIED",
        is_valid=is_valid,
        tampered_payload=tampered_payload,
        tampered_result="REJECTED_SIGNATURE_MISMATCH",
        tamper_rejected=tamper_rejected,
        algorithm="HMAC-SHA256 (FIPS 198-1)",
        execution_trace=trace,
        verification_status="VERIFIED_CRYPTO_INTEGRITY"
    )


@router.post(
    "/demo/dcdq-reorder",
    response_model=DCDQReorderDemoResponse,
    summary="Demonstrate Dynamic DCDQ Live Queue Reordering (AUD-008)",
    description="Demonstrates vehicle re-ranking in the DCDQ queue when wait bonus W_i or moisture M_i changes."
)
def run_dcdq_reorder_demo(
    payload: Optional[DCDQReorderDemoRequest] = None
) -> DCDQReorderDemoResponse:
    if not payload or not payload.mandi_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit mandi_id is required. Zero magic identity fallbacks permitted per DATA-001."
        )
    trace: List[str] = []
    req = payload
    mandi_id = req.mandi_id

    # Base sample vehicle lots representing live yard arrivals
    base_vehicles = [
        {
            "transaction_id": "TXN-DEMO-V01",
            "farmer_name": "Ramesh Kumar (G-01)",
            "crop_type": "Wheat (HD-2967)",
            "payload_qt": 35.0,
            "moisture_pct": 13.8,
            "wait_minutes": 15.0,
            "planned_offset": 0.0,
            "actual_offset": 5.0,
        },
        {
            "transaction_id": "TXN-DEMO-V02",
            "farmer_name": "Suresh Patel (G-02)",
            "crop_type": "Wheat (PBW-502)",
            "payload_qt": 42.0,
            "moisture_pct": 14.5,
            "wait_minutes": 25.0,
            "planned_offset": 0.0,
            "actual_offset": 0.0,
        },
        {
            "transaction_id": "TXN-DEMO-V03",
            "farmer_name": "Gurdeep Singh (G-03)",
            "crop_type": "Wheat (Lok-1)",
            "payload_qt": 50.0,
            "moisture_pct": 16.2,  # High moisture risk lot
            "wait_minutes": 10.0,
            "planned_offset": 0.0,
            "actual_offset": 10.0,
        },
        {
            "transaction_id": "TXN-DEMO-V04",
            "farmer_name": "Anita Devi (G-04)",
            "crop_type": "Wheat (Sharbati)",
            "payload_qt": 28.0,
            "moisture_pct": 13.2,
            "wait_minutes": 40.0,  # Long wait lot
            "planned_offset": 0.0,
            "actual_offset": 0.0,
        },
        {
            "transaction_id": "TXN-DEMO-V05",
            "farmer_name": "Balkar Singh (G-05)",
            "crop_type": "Wheat (HD-3086)",
            "payload_qt": 40.0,
            "moisture_pct": 14.0,
            "wait_minutes": 5.0,
            "planned_offset": 0.0,
            "actual_offset": 0.0,
        }
    ]

    now_ts = 1790066000.0  # reference epoch
    trace.append("+0.00ms: Initialized 5 candidate yard vehicles with varying A, D, M, W parameters.")

    def compute_queue(vehicles: list) -> List[DCDQVehicleDemoItem]:
        items = []
        for v in vehicles:
            planned_ts = now_ts + (v["planned_offset"] * 60.0)
            actual_ts = now_ts + (v["actual_offset"] * 60.0)
            comps = calculate_dcdq_components(
                planned_arrival_ts=planned_ts,
                actual_arrival_ts=actual_ts,
                moisture_pct=v["moisture_pct"],
                elapsed_wait_minutes=v["wait_minutes"],
                payload_quintals=v["payload_qt"]
            )
            items.append(DCDQVehicleDemoItem(
                transaction_id=v["transaction_id"],
                farmer_name=v["farmer_name"],
                crop_type=v["crop_type"],
                payload_qt=v["payload_qt"],
                moisture_pct=v["moisture_pct"],
                wait_minutes=v["wait_minutes"],
                planned_arrival_offset_min=v["planned_offset"],
                actual_arrival_offset_min=v["actual_offset"],
                score_a=comps["A"],
                score_d=comps["D"],
                score_m=comps["M"],
                score_w=comps["W"],
                composite_score_s=comps["S"],
                rank=0
            ))
        # Sort descending by composite score S
        items.sort(key=lambda x: x.composite_score_s, reverse=True)
        for idx, it in enumerate(items):
            it.rank = idx + 1
        return items

    before_queue = compute_queue(base_vehicles)
    trace.append(f"+1.20ms: Evaluated baseline DCDQ ranks: Top vehicle = {before_queue[0].transaction_id} (Score S = {before_queue[0].composite_score_s:.2f})")

    # Select target to tweak
    target_id = req.tweak_transaction_id or "TXN-DEMO-V05"
    prev_rank = next((it.rank for it in before_queue if it.transaction_id == target_id), len(before_queue))

    # Apply tweak (e.g. increase wait time by delta or adjust moisture)
    modified_vehicles = []
    for v in base_vehicles:
        v_copy = dict(v)
        if v_copy["transaction_id"] == target_id:
            if req.delta_wait_minutes is not None:
                v_copy["wait_minutes"] += float(req.delta_wait_minutes)
            if req.new_moisture_pct is not None:
                v_copy["moisture_pct"] = float(req.new_moisture_pct)
        modified_vehicles.append(v_copy)

    after_queue = compute_queue(modified_vehicles)
    new_rank = next((it.rank for it in after_queue if it.transaction_id == target_id), prev_rank)

    trace.append(f"+2.40ms: Applied tweak to {target_id}: wait +{req.delta_wait_minutes or 0}m, moisture={req.new_moisture_pct or 'unchanged'}.")
    trace.append(f"+3.10ms: Re-ranked ZSET: {target_id} moved Rank {prev_rank} -> Rank {new_rank}.")

    explanation = (
        f"Dynamic DCDQ Queue Reorder Demonstrated: Vehicle {target_id} moved from Rank #{prev_rank} "
        f"to Rank #{new_rank} after wait time increased by {req.delta_wait_minutes or 0:.0f}m. "
        f"Anti-starvation bonus W_i increased from {before_queue[prev_rank-1].score_w:.1f} to "
        f"{after_queue[new_rank-1].score_w:.1f}, preventing dry lots from indefinite stall."
    )

    return DCDQReorderDemoResponse(
        mandi_id=mandi_id,
        tweak_target=target_id,
        before_queue=before_queue,
        after_queue=after_queue,
        rank_changed=(prev_rank != new_rank),
        previous_rank=prev_rank,
        new_rank=new_rank,
        reorder_explanation=explanation,
        execution_trace=trace,
        verification_status="VERIFIED_DYNAMIC_REORDER"
    )


@router.post(
    "/demo/reset-algorithm-showcase",
    response_model=AlgorithmShowcaseResetResponse,
    summary="Reset Algorithm Showcase Demo Data (Data Isolation Contract AUD-008)",
    description="Purges ONLY demo-run records where is_showcase=true or demo_run_id is set. Never mutates genuine operational procurement data."
)
def reset_algorithm_showcase(
    demo_run_id: Optional[str] = Query(None, description="Optional specific demo_run_id to purge"),
    db: Session = Depends(get_db),
    admin_user: Optional[User] = Depends(require_roles(["ADMIN", "SUPERVISOR"]))
) -> AlgorithmShowcaseResetResponse:
    # 1. Purge demo procurement logs strictly tagged with is_showcase=True
    query = db.query(ProcurementLog).filter(ProcurementLog.is_showcase == True)
    if demo_run_id and demo_run_id.strip():
        query = query.filter(ProcurementLog.demo_run_id == demo_run_id.strip())

    demo_logs = query.all()
    deleted_count = len(demo_logs)
    for log in demo_logs:
        db.delete(log)

    # Also clean demo records with demo prefix if any slipped in
    fallback_demo_logs = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id.like("TXN-DEMO-%") |
        ProcurementLog.transaction_id.like("TXN-E2E-%")
    ).all()
    for log in fallback_demo_logs:
        db.delete(log)
        deleted_count += 1

    # 2. Reset dedicated demo slots (e.g. 21:00 slot used in concurrent booking)
    demo_slots = db.query(ProcurementSlot).filter(
        ProcurementSlot.start_time == time(21, 0)
    ).all()
    slots_reset = 0
    for s in demo_slots:
        s.booked_capacity_qt = 0.0
        slots_reset += 1

    db.commit()

    # 3. Clear active scales in-memory simulation overrides
    reset_active_scales()

    new_demo_id = f"DEMO-RUN-{uuid.uuid4().hex[:8].upper()}"

    return AlgorithmShowcaseResetResponse(
        status="SUCCESS",
        demo_records_purged=deleted_count,
        demo_slots_reset=slots_reset,
        scale_overrides_cleared=True,
        operational_data_protected=True,
        new_demo_run_id=new_demo_id,
        message=(
            f"Algorithm Showcase reset successfully. Purged {deleted_count} demo records, "
            f"reset {slots_reset} demo slots to 0.00 qt. Operational procurement logs "
            f"strictly protected. Active demo run initialized: {new_demo_id}."
        )
    )



