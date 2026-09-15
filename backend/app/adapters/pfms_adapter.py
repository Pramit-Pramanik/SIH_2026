from datetime import datetime, timezone
import uuid
from typing import Dict, Any, Optional

class PfmsMockAdapter:
    """
    Mock adapter simulating the Government of India Public Financial Management System (PFMS)
    and NPCI Aadhaar Payment Bridge (APB) direct disbursement rails.
    """
    is_mock: bool = True
    adapter_name: str = "PFMS-NPCI-MOCK-DISBURSEMENT-RAIL"

    @classmethod
    def disburse_payout(
        cls,
        transaction_id: str,
        amount_inr: float,
        payout_block_hash: str
    ) -> Dict[str, Any]:
        """
        Simulates atomic disbursement through PFMS-Aadhaar-Bridge.
        Generates deterministic reference IDs based on transaction ID and date.
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        ref_suffix = uuid.uuid5(uuid.NAMESPACE_DNS, f"{transaction_id}:{amount_inr}").hex[:8].upper()
        payout_ref = f"PFMS-{date_str}-{ref_suffix}"

        return {
            "is_mock": cls.is_mock,
            "adapter": cls.adapter_name,
            "status": "INITIATED",
            "transaction_id": transaction_id,
            "amount_inr": amount_inr,
            "payout_reference_id": payout_ref,
            "settlement_rail": "PFMS-Aadhaar-Bridge",
            "payout_block_hash": payout_block_hash,
            "timestamp": now.isoformat()
        }
