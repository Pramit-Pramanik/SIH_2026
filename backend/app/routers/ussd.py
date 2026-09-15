from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.schemas.ussd import USSDSessionRequest, USSDSessionResponse
from backend.app.services.ussd_service import handle_ussd_session
from backend.app.adapters.agmarknet_adapter import AgmarknetMockAdapter

router = APIRouter(prefix="/ussd", tags=["USSD Zero-Data Gateway (*247#)"])

@router.post(
    "/session",
    response_model=USSDSessionResponse,
    summary="Interactive USSD *247# Session Gateway",
    description="Processes zero-data mobile signaling interactions (GSM MAP layer emulation). Supports both structured JSON and plain-text telecom responses."
)
async def ussd_session_endpoint(
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    """
    Handles interactive USSD session turns.
    Supports either JSON payload or standard telecom URL-encoded form data.
    """
    body_bytes = await request.body()
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        import json
        body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        session_req = USSDSessionRequest(**body)
    else:
        # Telecom form-encoded data (e.g. sessionId, phoneNumber, serviceCode, text)
        import urllib.parse
        form_str = body_bytes.decode("utf-8") if body_bytes else ""
        parsed = urllib.parse.parse_qs(form_str)
        session_req = USSDSessionRequest(
            session_id=parsed.get("sessionId", parsed.get("session_id", ["sess-default"]))[0],
            phone_number=parsed.get("phoneNumber", parsed.get("phone_number", ["9999999999"]))[0],
            service_code=parsed.get("serviceCode", parsed.get("service_code", ["*247#"]))[0],
            text=parsed.get("text", [""])[0]
        )

    ussd_res = handle_ussd_session(db=db, request=session_req)

    # Return plain text if caller expects standard telecom CON/END response
    accept_header = request.headers.get("accept", "").lower()
    if "text/plain" in accept_header:
        return PlainTextResponse(content=ussd_res.message, status_code=200)

    return ussd_res


@router.get(
    "/menu",
    summary="Retrieve USSD Menu Specification",
    description="Returns the interactive menu tree for web and mobile feature-phone emulators."
)
def get_ussd_menu_spec() -> Dict[str, Any]:
    """
    Returns USSD menu hierarchy and available commands.
    """
    return {
        "service_code": "*247#",
        "portal_name": "MandiQ Zero-Data Feature Phone Portal",
        "transport": "GSM MAP Signaling Layer",
        "root_menu": [
            {"key": "1", "title": "Check MSP Rates", "adapter": "AGMARKNET"},
            {"key": "2", "title": "Live Mandi Wait Time", "service": "DCDQ Queue Manager"},
            {"key": "3", "title": "Check Payment Status", "service": "Procurement Ledger"},
            {"key": "4", "title": "Book Arrival Slot", "service": "Dynamic Slot Booking"},
            {"key": "0", "title": "Exit", "action": "TERMINATE_SESSION"}
        ]
    }


@router.get(
    "/mock/agmarknet/msp",
    summary="Mock AGMARKNET Minimum Support Prices",
    description="Returns official MSP rates from the mock AGMARKNET price adapter."
)
def get_mock_agmarknet_rates() -> Dict[str, Any]:
    """
    Returns deterministic MSP rates for agricultural crops.
    """
    return AgmarknetMockAdapter.get_current_msp_rates()
