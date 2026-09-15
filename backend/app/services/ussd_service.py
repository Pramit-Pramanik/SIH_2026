from typing import Tuple, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session

from backend.app.adapters.agmarknet_adapter import AgmarknetMockAdapter
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.queue_manager import queue_manager
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.schemas.slot import SlotReservationRequest
from backend.app.schemas.ussd import USSDSessionRequest, USSDSessionResponse

def handle_ussd_session(
    db: Session,
    request: USSDSessionRequest
) -> USSDSessionResponse:
    """
    Main state machine router for MandiQ USSD Gateway (*247#).
    Supports GSM MAP layer concatenated inputs (e.g. '1', '2*1', '4*1*25.0')
    and outputs standard 'CON <prompt>' or 'END <final_message>' strings.
    """
    text = request.text.strip()
    session_id = request.session_id
    phone_number = request.phone_number

    # Normalize parts by splitting on '*'
    parts = [p.strip() for p in text.split("*") if p.strip()]

    # 1. Root Menu (initial dial *247# or empty text or '0' from sub-menu)
    if not parts:
        msg = (
            "CON Welcome to MandiQ (*247#)\n"
            "1. Check MSP Rates\n"
            "2. Live Mandi Wait Time\n"
            "3. Check Payment Status\n"
            "4. Book Arrival Slot\n"
            "0. Exit"
        )
        return USSDSessionResponse(
            session_id=session_id,
            phone_number=phone_number,
            message=msg,
            continue_session=True,
            menu_level="ROOT"
        )

    root_choice = parts[0]

    # 0. Exit
    if root_choice == "0":
        return USSDSessionResponse(
            session_id=session_id,
            phone_number=phone_number,
            message="END Thank you for using MandiQ Zero-Data Cellular Portal.",
            continue_session=False,
            menu_level="EXIT"
        )

    # 1. Check MSP Rates
    elif root_choice == "1":
        rates = AgmarknetMockAdapter.get_current_msp_rates()["rates_inr_per_qt"]
        lines = ["CON Current MSP Rates (2025-26):"]
        idx = 1
        for crop, price in rates.items():
            lines.append(f"{idx}. {crop}: Rs.{price:,.2f}/qt")
            idx += 1
        lines.append("0. Back")
        msg = "\n".join(lines)

        # If user pressed 0 inside submenu, return root
        if len(parts) > 1 and parts[1] == "0":
            return handle_ussd_session(db, USSDSessionRequest(
                session_id=session_id,
                phone_number=phone_number,
                service_code=request.service_code,
                text=""
            ))

        return USSDSessionResponse(
            session_id=session_id,
            phone_number=phone_number,
            message=msg,
            continue_session=True,
            menu_level="MSP_RATES"
        )

    # 2. Live Mandi Wait Time
    elif root_choice == "2":
        if len(parts) == 1:
            msg = "CON Enter Mandi ID (e.g. 1 for Ambala Mandi):\n0. Back"
            return USSDSessionResponse(
                session_id=session_id,
                phone_number=phone_number,
                message=msg,
                continue_session=True,
                menu_level="WAIT_TIME_PROMPT"
            )
        else:
            if parts[1] == "0":
                return handle_ussd_session(db, USSDSessionRequest(
                    session_id=session_id,
                    phone_number=phone_number,
                    service_code=request.service_code,
                    text=""
                ))

            try:
                mandi_id = int(parts[1])
            except ValueError:
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message="CON Invalid Mandi ID. Please enter numbers only:\n0. Back",
                    continue_session=True,
                    menu_level="WAIT_TIME_ERROR"
                )

            mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
            if not mandi:
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message=f"CON Mandi ID {mandi_id} not found.\n0. Back",
                    continue_session=True,
                    menu_level="WAIT_TIME_NOT_FOUND"
                )

            # Query live queue count
            active_count = queue_manager.queue_length(mandi_id)
            weighbridges = max(1, mandi.active_weighbridges or 2)
            est_wait_mins = int((active_count * 10) / weighbridges)

            msg = (
                f"CON Mandi: {mandi.name}\n"
                f"Active Queue: {active_count} vehicles\n"
                f"Est. Wait: {est_wait_mins} mins\n"
                f"Weighbridges: {weighbridges} Active\n"
                f"0. Back"
            )
            return USSDSessionResponse(
                session_id=session_id,
                phone_number=phone_number,
                message=msg,
                continue_session=True,
                menu_level="WAIT_TIME_RESULT"
            )

    # 3. Check Payment Status
    elif root_choice == "3":
        if len(parts) == 1:
            msg = "CON Enter 10-digit Mobile or Txn ID (e.g. TXN-001):\n0. Back"
            return USSDSessionResponse(
                session_id=session_id,
                phone_number=phone_number,
                message=msg,
                continue_session=True,
                menu_level="PAYMENT_STATUS_PROMPT"
            )
        else:
            if parts[1] == "0":
                return handle_ussd_session(db, USSDSessionRequest(
                    session_id=session_id,
                    phone_number=phone_number,
                    service_code=request.service_code,
                    text=""
                ))

            search_query = parts[1].strip()
            log: Optional[ProcurementLog] = None

            if search_query.startswith("TXN-"):
                log = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == search_query).first()
            else:
                # Find farmer by mobile number
                farmer = db.query(Farmer).filter(Farmer.mobile_number == search_query).first()
                if farmer:
                    log = (
                        db.query(ProcurementLog)
                        .filter(ProcurementLog.farmer_id == farmer.farmer_id)
                        .order_by(ProcurementLog.created_at.desc())
                        .first()
                    )

            if not log:
                msg = f"CON No procurement record found for '{search_query}'.\n0. Back"
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message=msg,
                    continue_session=True,
                    menu_level="PAYMENT_NOT_FOUND"
                )

            payout_val = f"Rs.{float(log.total_payout_inr):,.2f}" if log.total_payout_inr else "Pending Weighment"
            payout_status = "Settled (PFMS)" if log.current_state == "PAYMENT_SETTLED" else (
                "Initiated (PFMS)" if log.current_state == "DBT_PAYMENT_INITIATED" else "In Yard Processing"
            )

            msg = (
                f"CON Txn: {log.transaction_id}\n"
                f"State: {log.current_state}\n"
                f"Net Wt: {float(log.net_weight_qt or 0):.2f} qt\n"
                f"Payout: {payout_val}\n"
                f"Status: {payout_status}\n"
                f"0. Back"
            )
            return USSDSessionResponse(
                session_id=session_id,
                phone_number=phone_number,
                message=msg,
                continue_session=True,
                menu_level="PAYMENT_RESULT"
            )

    # 4. Book Arrival Slot
    elif root_choice == "4":
        if len(parts) == 1:
            msg = "CON Enter Mandi ID & Qty in qt (e.g. 1*20):\n0. Back"
            return USSDSessionResponse(
                session_id=session_id,
                phone_number=phone_number,
                message=msg,
                continue_session=True,
                menu_level="BOOKING_PROMPT"
            )
        elif len(parts) == 2:
            if parts[1] == "0":
                return handle_ussd_session(db, USSDSessionRequest(
                    session_id=session_id,
                    phone_number=phone_number,
                    service_code=request.service_code,
                    text=""
                ))
            msg = f"CON Selected Mandi {parts[1]}. Enter Quantity in quintals:\n0. Back"
            return USSDSessionResponse(
                session_id=session_id,
                phone_number=phone_number,
                message=msg,
                continue_session=True,
                menu_level="BOOKING_QTY_PROMPT"
            )
        else:
            if parts[1] == "0" or parts[2] == "0":
                return handle_ussd_session(db, USSDSessionRequest(
                    session_id=session_id,
                    phone_number=phone_number,
                    service_code=request.service_code,
                    text=""
                ))

            try:
                mandi_id = int(parts[1])
                qty_qt = float(parts[2])
            except ValueError:
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message="CON Invalid Mandi ID or Quantity format.\n0. Back",
                    continue_session=True,
                    menu_level="BOOKING_ERROR"
                )

            # Find or fallback farmer by caller phone number
            farmer = db.query(Farmer).filter(Farmer.mobile_number == phone_number).first()
            if not farmer:
                # Fallback to the first registered farmer for demo/simulation
                farmer = db.query(Farmer).first()

            if not farmer:
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message="END Registration required: Farmer profile not found.",
                    continue_session=False,
                    menu_level="BOOKING_NO_FARMER"
                )

            # Find available slot for this mandi
            target_date = date.today()
            slot = (
                db.query(ProcurementSlot)
                .filter(
                    ProcurementSlot.mandi_id == mandi_id,
                    ProcurementSlot.scheduled_date >= target_date,
                    (ProcurementSlot.allocated_capacity_qt - ProcurementSlot.booked_capacity_qt) >= qty_qt
                )
                .order_by(ProcurementSlot.scheduled_date.asc(), ProcurementSlot.start_time.asc())
                .first()
            )

            if not slot:
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message=f"END No available slot with {qty_qt} qt capacity at Mandi {mandi_id}.",
                    continue_session=False,
                    menu_level="BOOKING_CAPACITY_FULL"
                )

            # Invoke atomic domain service
            from fastapi import HTTPException
            try:
                res = reserve_slot_atomic(
                    db=db,
                    mandi_id=mandi_id,
                    slot_id=slot.slot_id,
                    farmer_id=farmer.farmer_id,
                    requested_qty_qt=qty_qt
                )
                token_sig = res.token.signature[:12] if res.token and res.token.signature else "SIG-OK"
                msg = (
                    f"END Slot Reserved Successfully!\n"
                    f"Txn: {res.token.token_id}\n"
                    f"Date: {slot.scheduled_date} ({slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')})\n"
                    f"Qty: {qty_qt} qt\n"
                    f"Token: {token_sig}...\n"
                    f"Present token at gate entry."
                )
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message=msg,
                    continue_session=False,
                    menu_level="BOOKING_SUCCESS"
                )
            except HTTPException as exc:
                return USSDSessionResponse(
                    session_id=session_id,
                    phone_number=phone_number,
                    message=f"END Booking rejected: {exc.detail}",
                    continue_session=False,
                    menu_level="BOOKING_REJECTED"
                )

    # Unrecognized command
    return USSDSessionResponse(
        session_id=session_id,
        phone_number=phone_number,
        message=(
            "CON Invalid option selected.\n"
            "1. Check MSP Rates\n"
            "2. Live Mandi Wait Time\n"
            "3. Check Payment Status\n"
            "4. Book Arrival Slot\n"
            "0. Exit"
        ),
        continue_session=True,
        menu_level="INVALID_OPTION"
    )
