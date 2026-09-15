from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class USSDSessionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Unique telecom signaling session identifier")
    phone_number: str = Field(..., description="MSISDN / phone number of the caller")
    service_code: str = Field(default="*247#", description="Dialed shortcode (e.g. *247#)")
    text: str = Field(default="", description="User input text / concatenated input string (e.g. '1' or '4*1*25')")

class USSDSessionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    phone_number: str
    message: str = Field(..., description="USSD screen prompt (prefixed with CON or END)")
    continue_session: bool = Field(..., description="True if waiting for further user input, False if terminal")
    menu_level: str = Field(default="ROOT", description="Identifier of current menu level in state machine")

class USSDMenuOption(BaseModel):
    key: str
    title: str
    action_type: str
