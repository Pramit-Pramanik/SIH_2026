"""
AUD-008 Runtime Single-Language Verification Suite
Validates:
1. Zero raw unlocalized operational strings in all 7 frontend stations
2. 100% English / Hindi key symmetry across all namespaces
3. Runtime check: Quality failure (EN & HI)
4. Runtime check: Queue failure (EN & HI)
5. Runtime check: Billing failure (EN & HI)
6. Runtime check: HMAC failure (EN & HI)
7. Runtime check: Transaction-not-found dynamic interpolation without translating IDs
8. Single-language purity: EN contains 0 Devanagari, HI contains Devanagari script
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = ROOT / "frontend" / "src"
TRANSLATIONS_FILE = FRONTEND_SRC / "i18n" / "translations.ts"

COMPONENTS = [
    FRONTEND_SRC / "components" / "FarmerPortal.tsx",
    FRONTEND_SRC / "components" / "QualityStation.tsx",
    FRONTEND_SRC / "components" / "QueueMonitor.tsx",
    FRONTEND_SRC / "components" / "WeighbridgeStation.tsx",
    FRONTEND_SRC / "components" / "BillingPayoutStation.tsx",
    FRONTEND_SRC / "components" / "GateTerminal.tsx",
    FRONTEND_SRC / "components" / "AdminDashboard.tsx",
]


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_phase8_runtime_language import parse_translations_with_values


def interpolate(template: str, params: dict) -> str:
    res = template
    for k, v in params.items():
        res = res.replace(f"{{{k}}}", str(v))
    return res


def run_verification():
    print("=" * 70)
    print("  MANDIQ AUD-008 SINGLE-LANGUAGE ENFORCEMENT VERIFIER")
    print("=" * 70)

    # 1. Check file existence
    en_dict = parse_translations_with_values("en")
    hi_dict = parse_translations_with_values("hi")

    print(f"[*] Loaded English keys: {len(en_dict)}")
    print(f"[*] Loaded Hindi keys:   {len(hi_dict)}")

    # 2. Key Symmetry
    missing_in_hi = set(en_dict.keys()) - set(hi_dict.keys())
    missing_in_en = set(hi_dict.keys()) - set(en_dict.keys())

    assert not missing_in_hi, f"Keys missing in Hindi: {missing_in_hi}"
    assert not missing_in_en, f"Keys missing in English: {missing_in_en}"
    print(f"[OK] 100% Key Symmetry verified ({len(en_dict)} keys in both dictionaries).")

    # 3. Language Purity Invariant
    devanagari_regex = re.compile(r"[\u0900-\u097F]")
    for k, v in en_dict.items():
        dev_chars = devanagari_regex.findall(v)
        assert not dev_chars, f"English key '{k}' contains Devanagari characters: {v}"
    print("[OK] English dictionary has 0 Devanagari characters.")

    exempt_acronyms = {"APMC", "DBT", "PFMS", "WAL", "J-Form", "MSP", "HMAC", "OTP", "FAQ", "UPI", "PWA", "JSON", "UUID", "ID"}
    for k, v in hi_dict.items():
        has_dev = bool(devanagari_regex.search(v))
        is_pure_tech = any(a in v for a in exempt_acronyms)
        is_symbol = v.strip() in {"\u20b9", "%", "/", ":", "-"}
        is_formula = "Formula" in k or "=" in v or "+" in v
        assert has_dev or is_pure_tech or is_symbol or is_formula, f"Hindi key '{k}' lacks Devanagari characters: {v}"
    print("[OK] Hindi dictionary contains authentic Devanagari script for all user-facing keys.")

    # 4. Scenario-Specific Runtime Checks (EN and HI)
    print("\n--- Testing Specific Runtime Failure Scenarios ---")

    # A. Quality Failure
    print("[*] 1. Quality Failure:")
    en_q = en_dict.get("quality.resultRejected")
    hi_q = hi_dict.get("quality.resultRejected")
    assert en_q and "rejected" in en_q.lower(), f"Missing en quality failure: {en_q}"
    assert hi_q and devanagari_regex.search(hi_q), f"Missing hi quality failure: {hi_q}"
    print(f"    EN (Threshold): {en_q}")
    print(f"    HI (Threshold): {hi_q}")

    en_q_off = en_dict.get("quality.offlineRejected")
    hi_q_off = hi_dict.get("quality.offlineRejected")
    assert en_q_off and "rejected" in en_q_off.lower()
    assert hi_q_off and devanagari_regex.search(hi_q_off)
    print(f"    EN (Offline WAL): {en_q_off}")
    print(f"    HI (Offline WAL): {hi_q_off}")

    en_q_srv = en_dict.get("quality.assessmentRejected")
    hi_q_srv = hi_dict.get("quality.assessmentRejected")
    assert en_q_srv and hi_q_srv, "Missing quality.assessmentRejected"
    print(f"    EN (Server Reject): {en_q_srv}")
    print(f"    HI (Server Reject): {hi_q_srv}")

    # B. Queue Failure
    print("[*] 2. Queue Failure & Routing:")
    en_queue_err = en_dict["queue.fetchError"]
    hi_queue_err = hi_dict["queue.fetchError"]
    assert en_queue_err and "network" in en_queue_err.lower()
    assert hi_queue_err and devanagari_regex.search(hi_queue_err)
    print(f"    EN (Fetch Error): {en_queue_err}")
    print(f"    HI (Fetch Error): {hi_queue_err}")

    en_dispatch_err = en_dict["queue.dispatchError"]
    hi_dispatch_err = hi_dict["queue.dispatchError"]
    assert en_dispatch_err and hi_dispatch_err and devanagari_regex.search(hi_dispatch_err)
    print(f"    EN (Dispatch Error): {en_dispatch_err}")
    print(f"    HI (Dispatch Error): {hi_dispatch_err}")

    en_q_off = interpolate(en_dict["queue.offlineDispatched"], {"txnId": "TXN-2026-DISP"})
    hi_q_off = interpolate(hi_dict["queue.offlineDispatched"], {"txnId": "TXN-2026-DISP"})
    assert "TXN-2026-DISP" in en_q_off and "TXN-2026-DISP" in hi_q_off
    assert devanagari_regex.search(hi_q_off)
    print(f"    EN (Offline Dispatch): {en_q_off}")
    print(f"    HI (Offline Dispatch): {hi_q_off}")

    # C. Billing Failure
    print("[*] 3. Billing Failure (MSP Resolution & Generation):")
    en_msp_missing = interpolate(en_dict["billing.mspNotFoundInMaster"], {"crop": "WHEAT"})
    hi_msp_missing = interpolate(hi_dict["billing.mspNotFoundInMaster"], {"crop": "गेहूं"})
    assert "WHEAT" in en_msp_missing
    assert "गेहूं" in hi_msp_missing and devanagari_regex.search(hi_msp_missing)
    print(f"    EN (MSP Missing): {en_msp_missing}")
    print(f"    HI (MSP Missing): {hi_msp_missing}")

    en_bill_gen_err = en_dict["billing.failedFetchCropMaster"]
    hi_bill_gen_err = hi_dict["billing.failedFetchCropMaster"]
    assert en_bill_gen_err and "crop master" in en_bill_gen_err.lower()
    assert hi_bill_gen_err and devanagari_regex.search(hi_bill_gen_err)
    print(f"    EN (Fetch Master Error): {en_bill_gen_err}")
    print(f"    HI (Fetch Master Error): {hi_bill_gen_err}")

    en_inv_gen = interpolate(en_dict["billing.invoiceGeneratedDualSig"], {"amount": "227500.00", "state": "SETTLED"})
    hi_inv_gen = interpolate(hi_dict["billing.invoiceGeneratedDualSig"], {"amount": "227500.00", "state": "SETTLED"})
    assert "227500.00" in en_inv_gen and "SETTLED" in en_inv_gen
    assert "227500.00" in hi_inv_gen and "SETTLED" in hi_inv_gen
    assert devanagari_regex.search(hi_inv_gen)
    print(f"    EN (Invoice Gen): {en_inv_gen}")
    print(f"    HI (Invoice Gen): {hi_inv_gen}")

    # D. HMAC Failure
    print("[*] 4. HMAC Failure (Token Verification):")
    en_hmac_missing = en_dict["gate.hmacMissing"]
    hi_hmac_missing = hi_dict["gate.hmacMissing"]
    assert "signature" in en_hmac_missing.lower()
    assert devanagari_regex.search(hi_hmac_missing)
    print(f"    EN (Signature Missing): {en_hmac_missing}")
    print(f"    HI (Signature Missing): {hi_hmac_missing}")

    en_hmac_invalid = en_dict["gate.hmacFormatInvalid"]
    hi_hmac_invalid = hi_dict["gate.hmacFormatInvalid"]
    assert "HMAC" in en_hmac_invalid
    assert "HMAC" in hi_hmac_invalid and devanagari_regex.search(hi_hmac_invalid)
    print(f"    EN (HMAC Format): {en_hmac_invalid}")
    print(f"    HI (HMAC Format): {hi_hmac_invalid}")

    # E. Transaction Not Found (Dynamic Interpolation)
    print("[*] 5. Transaction Not Found (Dynamic Interpolation):")
    test_txn_id = "TXN-2026-9F8A-B2C1"
    en_not_found = interpolate(en_dict["common.txnNotFound"], {"txnId": test_txn_id})
    hi_not_found = interpolate(hi_dict["common.txnNotFound"], {"txnId": test_txn_id})
    
    # Must preserve exact technical ID without translating it
    assert test_txn_id in en_not_found, f"Txn ID missing in EN: {en_not_found}"
    assert test_txn_id in hi_not_found, f"Txn ID missing in HI: {hi_not_found}"
    # Hindi must be in Devanagari
    assert devanagari_regex.search(hi_not_found), f"HI txnNotFound lacks Devanagari: {hi_not_found}"
    print(f"    EN: {en_not_found}")
    print(f"    HI: {hi_not_found}")

    # 5. Component Scan for Raw Strings & Placeholders
    print("\n--- Scanning Components for Unlocalized Elements ---")
    placeholder_pattern = re.compile(r'placeholder=(["\'])(.*?)\1')
    alert_pattern = re.compile(r'\balert\((["\'])(.*?)\1\)')
    confirm_pattern = re.compile(r'\bconfirm\((["\'])(.*?)\1\)')

    for c in COMPONENTS:
        assert c.exists(), f"Component missing: {c}"
        c_text = c.read_text(encoding="utf-8")
        
        # Check raw string alert
        alerts = alert_pattern.findall(c_text)
        assert not alerts, f"Found raw alert() in {c.name}: {alerts}"
        
        # Check raw string confirm
        confirms = confirm_pattern.findall(c_text)
        assert not confirms, f"Found raw confirm() in {c.name}: {confirms}"
        
        # Check raw string placeholder
        placeholders = placeholder_pattern.findall(c_text)
        # Any raw placeholder must not be a plain sentence/phrase
        for q, p in placeholders:
            # If it has alphabetic characters and spaces, it should be t(...)
            if len(p.split()) > 1 and not p.startswith("e.g.") and not p.startswith("http"):
                raise AssertionError(f"Unlocalized placeholder in {c.name}: '{p}'")
        
        print(f"[OK] {c.name}: 0 raw alerts, confirms, or English placeholders.")

    print("\n" + "=" * 70)
    print("  ALL AUD-008 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_verification()
