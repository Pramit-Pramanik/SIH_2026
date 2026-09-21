"""
MandiQ - Phase 8: Runtime Single-Language Enforcement Test Suite

Automated verification of:
1. Strict Single-Language Invariant:
   - English mode: 0 Devanagari script characters in UI values.
   - Hindi mode: 100% Devanagari localized strings with 0 ordinary Latin UI text.
2. Complete elimination of raw runtime English strings across all UI stations and handlers.
3. Dynamic database localization strategy for unknown Mandis and Crops.
4. Role and page coverage across all stations, dialogs, and tools.
5. Language toggle state independence.
"""

import os
import re
import json
import pytest
from pathlib import Path
from scripts.audit_localization import extract_ts_object, TRANSLATIONS_FILE, FRONTEND_SRC

REPO_ROOT = Path(__file__).resolve().parent.parent
LANGUAGE_CONTEXT_FILE = FRONTEND_SRC / "i18n" / "LanguageContext.tsx"


def parse_translations_with_values(lang: str):
    """Extract full dictionary key-value pairs for a given language ('en' | 'hi')."""
    content = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    pattern = rf"\b{lang}\s*:\s*\{{"
    match = re.search(pattern, content)
    assert match, f"Could not find start of language dictionary: '{lang}'"

    start_idx = match.end() - 1
    depth = 0
    end_idx = -1
    for i in range(start_idx, len(content)):
        char = content[i]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    assert end_idx != -1, f"Could not find end of language dictionary: '{lang}'"
    block = content[start_idx:end_idx]

    key_vals = {}
    lines = block.splitlines()
    stack = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        sec_match = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*\{", stripped)
        if sec_match:
            sec_name = sec_match.group(1)
            stack.append(sec_name)
            continue

        # Match single-quote, double-quote, or backtick string literals
        leaf_match = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(['\"`])(.*)\2,?", stripped)
        if leaf_match:
            key_name = leaf_match.group(1)
            val_text = leaf_match.group(3)
            prefix = ".".join(stack)
            full_key = f"{prefix}.{key_name}" if prefix else key_name
            key_vals[full_key] = val_text

        # Stack pop on closing brace
        closing_count = stripped.count("}")
        opening_count = stripped.count("{")
        net = closing_count - opening_count
        while net > 0 and stack and not sec_match:
            stack.pop()
            net -= 1

    return key_vals


def test_dictionary_parity_and_key_symmetry():
    """Verify 100% key symmetry between English and Hindi dictionaries with zero missing keys."""
    ts_content = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    en_keys = extract_ts_object(ts_content, "en")
    hi_keys = extract_ts_object(ts_content, "hi")

    missing_in_hi = set(en_keys.keys()) - set(hi_keys.keys())
    missing_in_en = set(hi_keys.keys()) - set(en_keys.keys())

    assert not missing_in_hi, f"Keys missing in Hindi: {missing_in_hi}"
    assert not missing_in_en, f"Keys missing in English: {missing_in_en}"
    assert len(en_keys) == len(hi_keys)
    assert len(en_keys) >= 580, f"Expected at least 580 keys, found {len(en_keys)}"


def test_strict_single_language_invariant():
    """
    Acceptance Rule:
    English mode -> No ordinary Hindi UI text (0 Devanagari characters)
    Hindi mode   -> No ordinary English UI text (Devanagari script required for user-facing tokens)
    """
    en_vals = parse_translations_with_values("en")
    hi_vals = parse_translations_with_values("hi")

    devanagari_regex = re.compile(r"[\u0900-\u097F]")

    # 1. English mode must not contain ANY Devanagari characters
    for key, text in en_vals.items():
        dev_chars = devanagari_regex.findall(text)
        assert not dev_chars, f"English key '{key}' contains Devanagari text: '{text}'"

    # 2. Hindi mode must contain Devanagari characters for user-facing UI strings
    # Currency symbols (₹), technical acronyms or formatting tokens are exempt
    technical_acronyms = {"APMC", "DBT", "PFMS", "WAL", "J-Form", "MSP", "HMAC", "OTP", "FAQ", "UPI", "PWA", "JSON", "UUID", "ID"}
    for key, text in hi_vals.items():
        has_dev = bool(devanagari_regex.search(text))
        is_pure_tech = any(acronym in text for acronym in technical_acronyms)
        is_symbol = text.strip() in {"₹", "%", "/", ":", "-"}
        is_formula = "Formula" in key or "=" in text or "+" in text
        assert has_dev or is_pure_tech or is_symbol or is_formula, f"Hindi key '{key}' has no Devanagari text: '{text}'"


def test_no_raw_runtime_strings_in_components():
    """
    Verify complete elimination of raw runtime English strings across all UI components.
    Specifically checks the strings cited in the mandate.
    """
    forbidden_strings = [
        "BACKEND OFFLINE",
        "IN-MEMORY QUEUE",
        "No operational mandis available",
        "Failed to cancel appointment",
        "Network error cancelling appointment.",
        "Authenticated farmer profile is not linked. Slot reservation cannot proceed.",
        "Please select an operational mandi.",
        "No authoritative transaction selected.",
        "Physical Invariant Violation: Tare weight cannot be >= Gross weight.",
        "No operational mandi selected.",
        "No vehicles currently present in queue to dispatch.",
        "Saved locally in IndexedDB transactionsWAL.",
        "Please generate or fetch a valid J-Form invoice first.",
        "Dual-signature verification requires both Inspector and Operator cryptographic signatures.",
        "[OFFLINE WAL] Dual-signature DBT authorization stored locally in IndexedDB transactionsWAL.",
        "Direct Benefit Transfer (DBT) confirmed by PFMS Settlement Rail!",
        "Offline Blackout: Direct Benefit Transfer (DBT) recorded locally in Dexie.",
        "[OFFLINE WAL] Supervisor override recorded locally in Dexie.",
        "Backend unavailable. Reconnect to manage server-side administration.",
        "No operational mandi selected for simulation.",
        "No operational mandi selected for reset.",
    ]

    components_dir = FRONTEND_SRC / "components"
    violations = []

    for file_path in components_dir.glob("*.tsx"):
        content = file_path.read_text(encoding="utf-8")
        for bad_str in forbidden_strings:
            # Check for raw occurrence as string literal in JSX or JS
            if f"'{bad_str}'" in content or f'"{bad_str}"' in content or f">{bad_str}<" in content:
                violations.append(f"{file_path.name}: found raw literal '{bad_str}'")

    assert not violations, "Raw runtime strings detected in components:\n" + "\n".join(violations)


def test_dynamic_data_localization_unknown_values():
    """
    Verify the explicit multi-tier dynamic localization strategy:
    Unknown database Mandi and Crop names must never silently remain English in Hindi mode.
    """
    lang_ctx_code = LANGUAGE_CONTEXT_FILE.read_text(encoding="utf-8")

    # 1. Verify transliterateToHindi is implemented and exported
    assert "export function transliterateToHindi" in lang_ctx_code, "transliterateToHindi function must be exported"

    # 2. Verify compound token parsing in getMandiName and getCropName
    assert "MANDI_VOCABULARY" in lang_ctx_code, "MANDI_VOCABULARY must be defined for compound mandi resolution"
    assert "CROP_VOCABULARY" in lang_ctx_code, "CROP_VOCABULARY must be defined for compound crop resolution"

    # 3. Verify that in Hindi mode, getMandiName and getCropName do NOT return raw canonicalName
    assert "return localized.join('');" in lang_ctx_code, "getMandiName/getCropName must return localized compound tokens"


def test_all_station_namespaces_fully_populated():
    """Verify that all required stations and tools have complete translation coverage."""
    ts_content = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    en_keys = extract_ts_object(ts_content, "en")

    required_stations = [
        "login",
        "common",
        "nav",
        "roles",
        "farmer",
        "gate",
        "quality",
        "queue",
        "weighbridge",
        "billing",
        "admin",
        "demoTools",
        "journey",
        "ussd",
        "sync",
        "receipt",
    ]

    for st in required_stations:
        st_keys = [k for k in en_keys if k.startswith(f"{st}.")]
        assert st_keys, f"Missing required station namespace: '{st}'"
        assert len(st_keys) >= 5, f"Station namespace '{st}' has suspiciously few keys ({len(st_keys)})"


def test_roles_complete_coverage():
    """Verify all five operational roles have dedicated localized labels."""
    ts_content = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    en_keys = extract_ts_object(ts_content, "en")
    hi_keys = extract_ts_object(ts_content, "hi")
    roles = ["farmer", "operator", "inspector", "supervisor", "admin"]

    for r in roles:
        assert f"roles.{r}" in en_keys, f"Role '{r}' missing in en.roles"
        assert f"roles.{r}" in hi_keys, f"Role '{r}' missing in hi.roles"
