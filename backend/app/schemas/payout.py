from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DualSignaturePayoutStageRequest(BaseModel):
    """
    Request schema for staging Direct Benefit Transfer (DBT) payout via dual cryptographic signatures.
    Per AC-009, requires independent HMAC-SHA256 hashes from both Inspector and Operator.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Unique procurement transaction ID")
    invoice_amount_inr: float = Field(..., gt=0.0, description="J-Form invoice amount in INR to be disbursed")
    inspector_id: int = Field(..., description="Identifier of the certifying Procurement Inspector")
    inspector_sig_hash: str = Field(..., description="HMAC-SHA256 signature from Inspector")
    operator_id: int = Field(..., description="Identifier of the certifying Mandi Operator")
    operator_sig_hash: str = Field(..., description="HMAC-SHA256 signature from Operator")


class DemoPayoutSignatureRequest(BaseModel):
    """Controlled local-demo request; signatures are intentionally absent."""
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    invoice_amount_inr: float = Field(..., gt=0.0)
    inspector_id: int
    operator_id: int


class DualSignaturePayoutStageResponse(BaseModel):
    """
    Response schema returning payout staging authorization and block hash.
    """
    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., description="Status of payout staging ('AUTHORIZED' or 'REJECTED')")
    transaction_id: str
    amount_inr: float
    payout_block_hash: str = Field(..., description="Cryptographic payout block hash bound to dual signatures")
    current_state: str
    dbt_reference_id: Optional[str] = None
    message: str


class MockDbtPayoutRequest(BaseModel):
    """
    Request payload simulating government PFMS / NPCI DBT payment instruction.
    """
    model_config = ConfigDict(extra="forbid")

    farmer_id: int = Field(..., description="Unique farmer ID")
    transaction_amount_inr: float = Field(..., gt=0.0, description="Amount in INR to be credited")
    bank_ifsc: str = Field(..., description="Farmer bank account IFSC code")
    account_number_hash: str = Field(..., description="SHA-256 hash of bank account number")


class MockDbtPayoutResponse(BaseModel):
    """
    Response schema simulating PFMS Aadhaar Payment Bridge (APB) confirmation.
    """
    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="INITIATED", description="DBT disbursement status")
    payout_reference_id: str = Field(..., description="Unique PFMS transaction reference ID")
    settlement_rail: str = Field(default="PFMS-Aadhaar-Bridge", description="Government settlement rail name")
    timestamp: str
