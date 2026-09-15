from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.schemas.billing import (
    JFormGenerationRequest,
    JFormInvoiceResponse
)
from backend.app.services.lifecycle_service import validate_lifecycle_transition

# Authoritative Government of India Minimum Support Price (MSP) Rates (₹ / quintal)
DEFAULT_MSP_RATES = {
    "wheat": 2275.00,
    "wheat (sharbati)": 2275.00,
    "wheat (hd-2967)": 2275.00,
    "soybean": 4892.00,
    "soybean (js-335)": 4892.00,
    "paddy": 2300.00,
    "paddy (basmati)": 2300.00,
    "gram": 5440.00,
    "mustard": 5650.00,
}
FALLBACK_MSP_RATE = 2275.00


def get_crop_msp_rate(crop_name: str) -> float:
    """
    Returns the authoritative MSP rate per quintal for the given crop type,
    defaulting to 2275.00 (Standard Wheat MSP per AC-009).
    """
    if not crop_name:
        return FALLBACK_MSP_RATE
    key = crop_name.strip().lower()
    return DEFAULT_MSP_RATES.get(key, FALLBACK_MSP_RATE)


def generate_jform_invoice(
    db: Session,
    request: JFormGenerationRequest
) -> JFormInvoiceResponse:
    """
    Calculates and persists official digital J-Form joint-sale receipt for a weighed transaction.
    Formula: Gross Amount = Net Weight (qt) * Rate (INR/qt)
             Invoice Amount = Gross Amount - Deductions (INR)
    Enforces prior state transition (must be in WEIGHED_TARE), persists total_payout_inr,
    and advances state to BILL_GENERATED.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # 1. Look up farmer details for crop and rate determination
    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    crop_type = farmer.registered_crop_type if farmer else "Wheat"
    farmer_name = farmer.name if farmer else "Registered Farmer"

    # 2. Determine applicable rate per quintal
    if request.rate_per_qt is not None and request.rate_per_qt > 0:
        rate = float(request.rate_per_qt)
    else:
        rate = get_crop_msp_rate(crop_type)

    # 3. Validate deductions
    deductions = round(float(request.deductions_inr or 0.0), 2)
    if deductions < 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Deductions cannot be negative."
        )

    # 4. Check Net Weight availability
    if log.net_weight_qt is None or float(log.net_weight_qt) <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transaction '{request.transaction_id}' has no valid net weight recorded."
        )
    net_weight = float(log.net_weight_qt)

    # 5. Compute Invoice Amount
    gross_amount = round(net_weight * rate, 2)
    invoice_amount = round(gross_amount - deductions, 2)
    if invoice_amount <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Calculated invoice amount ({invoice_amount:.2f} INR) must be strictly greater than zero."
        )

    # 6. Idempotency handling: if already in BILL_GENERATED
    if log.current_state == "BILL_GENERATED":
        if log.total_payout_inr is not None and abs(float(log.total_payout_inr) - invoice_amount) < 1e-4:
            return JFormInvoiceResponse(
                invoice_id=f"JFORM-{log.transaction_id}",
                transaction_id=log.transaction_id,
                farmer_id=log.farmer_id,
                farmer_name=farmer_name,
                mandi_id=log.mandi_id,
                crop_type=crop_type,
                net_weight_qt=net_weight,
                rate_per_qt=rate,
                gross_amount_inr=gross_amount,
                deductions_inr=deductions,
                invoice_amount_inr=invoice_amount,
                current_state=log.current_state,
                generated_at=log.updated_at.isoformat(),
                message="J-Form already generated (idempotent repeated request)."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicting invoice generation request for transaction '{log.transaction_id}' already in BILL_GENERATED."
            )

    # Cannot re-generate bill if already in advanced payout stages
    if log.current_state in ("DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot generate bill: transaction is already in advanced state '{log.current_state}'."
        )

    # 7. Valid prior state: must be strictly WEIGHED_TARE per lifecycle engine
    is_valid, err_msg, _ = validate_lifecycle_transition(
        log.current_state,
        "BILL_GENERATED",
        payload_fields={"net_weight_qt": net_weight, "total_payout_inr": invoice_amount},
        current_log=log
    )
    if not is_valid or log.current_state != "WEIGHED_TARE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot skip required prior state: transaction is in state '{log.current_state}'. "
                f"Vehicle must be in 'WEIGHED_TARE' before J-Form billing generation."
            )
        )

    # 8. Persist bill generation
    now = datetime.now(timezone.utc)
    log.total_payout_inr = invoice_amount
    log.current_state = "BILL_GENERATED"
    log.updated_at = now
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    return JFormInvoiceResponse(
        invoice_id=f"JFORM-{log.transaction_id}",
        transaction_id=log.transaction_id,
        farmer_id=log.farmer_id,
        farmer_name=farmer_name,
        mandi_id=log.mandi_id,
        crop_type=crop_type,
        net_weight_qt=net_weight,
        rate_per_qt=rate,
        gross_amount_inr=gross_amount,
        deductions_inr=deductions,
        invoice_amount_inr=invoice_amount,
        current_state=log.current_state,
        generated_at=now.isoformat(),
        message=f"J-Form invoice generated successfully: ₹{invoice_amount:.2f} authorized for DBT payout staging."
    )


def get_jform_invoice(
    db: Session,
    transaction_id: str
) -> JFormInvoiceResponse:
    """
    Retrieves the generated J-Form invoice details for a transaction.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    if log.current_state not in ("BILL_GENERATED", "DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"J-Form invoice has not yet been generated for transaction '{transaction_id}' (state: {log.current_state})."
        )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    crop_type = farmer.registered_crop_type if farmer else "Wheat"
    farmer_name = farmer.name if farmer else "Registered Farmer"

    net_weight = float(log.net_weight_qt or 0.0)
    invoice_amount = float(log.total_payout_inr or 0.0)
    rate = get_crop_msp_rate(crop_type)
    gross_amount = round(net_weight * rate, 2)
    deductions = round(max(0.0, gross_amount - invoice_amount), 2)

    return JFormInvoiceResponse(
        invoice_id=f"JFORM-{log.transaction_id}",
        transaction_id=log.transaction_id,
        farmer_id=log.farmer_id,
        farmer_name=farmer_name,
        mandi_id=log.mandi_id,
        crop_type=crop_type,
        net_weight_qt=net_weight,
        rate_per_qt=rate,
        gross_amount_inr=gross_amount,
        deductions_inr=deductions,
        invoice_amount_inr=invoice_amount,
        current_state=log.current_state,
        generated_at=log.updated_at.isoformat(),
        message=f"J-Form invoice for transaction '{transaction_id}'."
    )
