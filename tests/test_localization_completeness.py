"""
Test Localization Completeness & Single-Language Invariants.
Verifies Requirement 1, 2, 3, 4, 6, 9, 10, 11 of MANDIQ Phase 3:
1. 100% key parity between English ('en') and Hindi ('hi').
2. Zero unresolved t('...') keys in frontend codebase.
3. Zero unclassified raw user-facing strings in JSX.
4. No silent English fallback for Hindi keys.
"""

import sys
from pathlib import Path
import pytest
from scripts.audit_localization import (
    run_audit,
    extract_ts_object,
    find_all_t_calls,
    scan_raw_jsx_text,
    TRANSLATIONS_FILE,
    FRONTEND_SRC,
)


def test_localization_key_symmetry_and_zero_missing():
    """
    Assert that the English and Hindi dictionaries have 100% key symmetry,
    and every referenced t() call in the UI resolves in both dictionaries.
    """
    assert TRANSLATIONS_FILE.exists(), f"Translations file not found: {TRANSLATIONS_FILE}"
    content = TRANSLATIONS_FILE.read_text(encoding="utf-8")

    en_keys = set(extract_ts_object(content, "en").keys())
    hi_keys = set(extract_ts_object(content, "hi").keys())

    assert len(en_keys) > 500, f"Expected > 500 English keys, found {len(en_keys)}"
    assert len(hi_keys) > 500, f"Expected > 500 Hindi keys, found {len(hi_keys)}"

    missing_in_hi = en_keys - hi_keys
    missing_in_en = hi_keys - en_keys

    assert not missing_in_hi, f"Keys in 'en' missing in 'hi': {missing_in_hi}"
    assert not missing_in_en, f"Keys in 'hi' missing in 'en': {missing_in_en}"


def test_all_referenced_t_keys_resolve():
    """
    Assert that every single t('key.path') in all .tsx and .ts files
    is defined in both 'en' and 'hi' dictionaries.
    """
    content = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    en_keys = set(extract_ts_object(content, "en").keys())
    hi_keys = set(extract_ts_object(content, "hi").keys())

    referenced = find_all_t_calls(FRONTEND_SRC)
    assert len(referenced) > 300, f"Expected > 300 referenced keys, found {len(referenced)}"

    unresolved_en = referenced - en_keys
    unresolved_hi = referenced - hi_keys

    assert not unresolved_en, f"Referenced keys missing in 'en': {unresolved_en}"
    assert not unresolved_hi, f"Referenced keys missing in 'hi': {unresolved_hi}"


def test_zero_unclassified_raw_jsx_strings():
    """
    Assert that no raw unlocalized user-facing strings remain in JSX components.
    """
    suspicious = scan_raw_jsx_text(FRONTEND_SRC)
    assert len(suspicious) == 0, f"Unclassified raw strings found in JSX: {suspicious}"


def test_audit_script_exits_clean():
    """
    Assert that the master localization audit function returns True.
    """
    assert run_audit() is True
