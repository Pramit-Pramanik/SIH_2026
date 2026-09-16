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
