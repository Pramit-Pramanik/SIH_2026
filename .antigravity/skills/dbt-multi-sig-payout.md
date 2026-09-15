# Skill: Multi-Signature DBT Payout Authorization (HMAC-SHA256)

## Purpose
Enforces multi-signature cryptographic authorization from both the Procurement Inspector and Mandi Operator before triggering Direct Benefit Transfer (DBT) payment instructions to PFMS/NPCI mock rails.

## Security Directives
1. **HMAC-SHA256 Required**: Signatures must use HMAC-SHA256 calculated over the specific transaction ID, invoice amount, and role identifier. Plain SHA-256 is strictly prohibited.
2. **Fail-Closed Secret Injection**: Secret key must be loaded from `MANDIQ_PAYOUT_SECRET_KEY`. If unset or empty, execution fails closed with a fatal configuration error.
3. **Dual-Signature Obligation**: Payout staging CANNOT proceed with only one signature. Both Inspector and Operator hashes must match.
4. **Transaction & Amount Bound**: Signatures are cryptographically bound to `transaction_id` and `invoice_amount_inr` to prevent signature reuse across different transactions or altered amounts.

## Executable Python Multi-Sig Verification Handler
```python
import os
import hmac
import hashlib
from typing import Dict, Any

def get_payout_secret_key() -> bytes:
    key = os.getenv("MANDIQ_PAYOUT_SECRET_KEY")
    if not key or not key.strip():
        raise RuntimeError(
            "FATAL SECURITY CONFIGURATION ERROR: 'MANDIQ_PAYOUT_SECRET_KEY' is missing or empty. "
            "MandiQ refuses to stage DBT payouts with default or empty cryptographic secrets. "
            "Please configure MANDIQ_PAYOUT_SECRET_KEY in the environment."
        )
    return key.encode("utf-8")

def compute_role_signature(secret_key: bytes, transaction_id: str, amount_inr: float, role_id: int, role_title: str) -> str:
    """
    Computes an HMAC-SHA256 signature for a specific approver role bound to transaction and amount.
    """
    raw_payload = f"{transaction_id}:{amount_inr:.2f}:{role_title}:{role_id}"
    return hmac.new(secret_key, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_and_stage_dbt_payout(
    transaction_id: str,
    invoice_amount_inr: float,
    inspector_id: int,
    inspector_sig_hash: str,
    operator_id: int,
    operator_sig_hash: str
) -> Dict[str, Any]:
    """
    Validates dual HMAC-SHA256 cryptographic signatures before staging DBT payout.
    Fails closed if secrets are missing or either signature is invalid.
    """
    secret_key = get_payout_secret_key()
    
    # 1. Reject if either signature is missing or blank
    if not inspector_sig_hash or not inspector_sig_hash.strip():
        return {"status": "REJECTED", "reason": "Missing Inspector Signature"}
        
    if not operator_sig_hash or not operator_sig_hash.strip():
        return {"status": "REJECTED", "reason": "Missing Operator Signature"}
        
    # 2. Recompute expected Inspector HMAC-SHA256
    expected_inspector_hash = compute_role_signature(
        secret_key, transaction_id, invoice_amount_inr, inspector_id, "INSPECTOR"
    )
    if not hmac.compare_digest(inspector_sig_hash, expected_inspector_hash):
        return {"status": "REJECTED", "reason": "Invalid Inspector Signature"}
        
    # 3. Recompute expected Operator HMAC-SHA256
    expected_operator_hash = compute_role_signature(
        secret_key, transaction_id, invoice_amount_inr, operator_id, "OPERATOR"
    )
    if not hmac.compare_digest(operator_sig_hash, expected_operator_hash):
        return {"status": "REJECTED", "reason": "Invalid Operator Signature"}
        
    # 4. Both signatures valid -> Generate Payout Block Hash
    block_payload = f"{transaction_id}:{invoice_amount_inr:.2f}:{inspector_sig_hash}:{operator_sig_hash}"
    payout_block_hash = hmac.new(secret_key, block_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    
    return {
        "status": "AUTHORIZED",
        "transaction_id": transaction_id,
        "amount_inr": invoice_amount_inr,
        "payout_block_hash": payout_block_hash
    }
```
