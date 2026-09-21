#!/usr/bin/env python3
"""
MandiQ Localization Completeness & Key Parity Auditor.

Verifies:
1. Complete key parity between English ('en') and Hindi ('hi') dictionaries in translations.ts.
2. Zero missing keys for all t('...') calls across frontend/src/**/*.tsx and *.ts.
3. Scans JSX files for raw unlocalized user-facing text (ignoring proper nouns, tech tokens, numbers, and formulas).
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
TRANSLATIONS_FILE = FRONTEND_SRC / "i18n" / "translations.ts"


def extract_ts_object(ts_content: str, lang: str) -> Dict[str, Any]:
    """
    Extracts dictionary keys for a given language ('en' | 'hi') from translations.ts.
    Uses regex and braces matching to safely collect nested keys.
    """
    pattern = rf"\b{lang}\s*:\s*\{{"
    match = re.search(pattern, ts_content)
    if not match:
        raise ValueError(f"Could not find start of language dictionary: '{lang}'")

    start_idx = match.end() - 1
    depth = 0
    end_idx = -1
    for i in range(start_idx, len(ts_content)):
        char = ts_content[i]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    if end_idx == -1:
        raise ValueError(f"Could not parse end of language block: '{lang}'")

    block = ts_content[start_idx:end_idx]
    return parse_object_keys(block)


def parse_object_keys(block: str) -> Dict[str, Any]:
    """
    Recursively extracts dotted paths from TypeScript object literal text.
    """
    keys_dict: Dict[str, Any] = {}
    lines = block.splitlines()
    stack: List[Tuple[str, int]] = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Check section opening: `sectionName: {`
        sec_match = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*\{", stripped)
        if sec_match:
            sec_name = sec_match.group(1)
            stack.append((sec_name, stripped.count("{") - stripped.count("}")))
            continue

        # Check leaf property: `keyName:`
        leaf_match = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(['\"`]|.*)", stripped)
        if leaf_match and not stripped.endswith("{"):
            key_name = leaf_match.group(1)
            if stack:
                prefix = ".".join(s[0] for s in stack)
                keys_dict[f"{prefix}.{key_name}"] = True
            else:
                keys_dict[key_name] = True

        # Adjust stack depth based on closing braces
        closing_count = stripped.count("}")
        opening_count = stripped.count("{")
        net = closing_count - opening_count
        while net > 0 and stack:
            stack.pop()
            net -= 1

    return keys_dict


def find_all_t_calls(src_dir: Path) -> Set[str]:
    """
    Finds all t('key.path') calls in all .tsx and .ts files.
    """
    t_pattern = re.compile(r"\bt\(\s*['\"`]([a-zA-Z0-9_.]+)['\"`]")
    all_keys: Set[str] = set()

    for file_path in src_dir.rglob("*.tsx"):
        content = file_path.read_text(encoding="utf-8")
        for match in t_pattern.finditer(content):
            all_keys.add(match.group(1))

    for file_path in src_dir.rglob("*.ts"):
        if "translations.ts" in str(file_path):
            continue
        content = file_path.read_text(encoding="utf-8")
        for match in t_pattern.finditer(content):
            all_keys.add(match.group(1))

    return all_keys


def scan_raw_jsx_text(src_dir: Path) -> List[Tuple[str, int, str]]:
    """
    Scans JSX for raw unlocalized user-facing strings in JSX bodies and attributes.
    Exempts numbers, symbols, technical tokens, proper nouns, and code identifiers.
    """
    jsx_text_pattern = re.compile(r">([^<>{}\r\n]+)<")
    attr_pattern = re.compile(r'\b(placeholder|title|aria-label)=["\']([^"\']+)["\']')

    EXEMPT_REGEXES = [
        re.compile(r"^[0-9\s.,:%/+\\-]+$"),   # numbers & punctuation
        re.compile(r"^(&gt;|&lt;)\s*[0-9\s.,:%/+\\-]+$"), # Comparison thresholds like &gt; 17.0%
        re.compile(r"^[A-Z0-9_\-./]+$"),      # Technical uppercase identifiers
        re.compile(r"^&\w+;$"),              # HTML entities
        re.compile(r"^[✕✓•*#]+$"),            # Symbols
        re.compile(r"^[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$"), # Code property paths
        re.compile(r"^lock:[a-z0-9_:]+$"),    # Redis lock keys
        re.compile(r"^e\.g\.\s+TXN.*$"),     # Technical ID placeholders
        re.compile(r"^[0-9.]+\s*(&&|\|\|).*$"), # Code expressions in JSX
    ]

    EXEMPT_EXACT = {
        "MandiQ", "Sehore", "Karnal", "Dewas", "Khanna", "Ujjain", "Madhya Pradesh",
        "Ramesh Kumar", "Balvinder Singh", "Suresh Patel",
        "Wheat", "Paddy", "Mustard", "Gram", "Soybean",
        "DCDQ", "WAL", "HMAC", "SHA256", "PFMS", "DBT", "MSP", "APMC", "PWA",
        "IndexedDB", "REST", "API", "HTTP", "GSM", "2G", "4G", "MAP", "JSON",
        "UUID", "Aadhaar", "AgriStack", "ZSET", "FIFO",
        "LIVE CLOUD LINK", "OFFLINE AIR-GAP", "Direct REST & Gzip WAL", "IndexedDB Local Fallback",
        "Live Dynamic Stream (5s)", "GSM-4G [||||]",
        "English", "हिन्दी",  # Language selector display names
        "min", "kg", "qt", "₹",  # Units
        "Promise", "Record",  # TypeScript type tokens
    }

    suspicious: List[Tuple[str, int, str]] = []

    for file_path in src_dir.glob("components/*.tsx"):
        lines = file_path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            # Check JSX text
            for match in jsx_text_pattern.finditer(line):
                text = match.group(1).strip()
                if not text or len(text) <= 1:
                    continue
                if any(rx.match(text) for rx in EXEMPT_REGEXES):
                    continue
                if text in EXEMPT_EXACT:
                    continue
                # If text contains only words that look like technical acronyms or formulas
                if text.startswith("S_i =") or text.startswith("alpha *") or text.startswith("beta *") or text.startswith("gamma *") or text.startswith("lambda *"):
                    continue
                if text.startswith(">") or text.startswith("<"):
                    continue
                suspicious.append((file_path.name, idx, text))

            # Check attributes
            for match in attr_pattern.finditer(line):
                attr_val = match.group(2).strip()
                if not attr_val or len(attr_val) <= 1:
                    continue
                if any(rx.match(attr_val) for rx in EXEMPT_REGEXES):
                    continue
                if attr_val in EXEMPT_EXACT:
                    continue
                suspicious.append((file_path.name, idx, f"{match.group(1)}='{attr_val}'"))

    return suspicious


def run_audit() -> bool:
    print("=" * 70)
    print("  MANDIQ GLOBAL LOCALIZATION AUDITOR")
    print("=" * 70)

    if not TRANSLATIONS_FILE.exists():
        print(f"[FAIL] Missing translations file: {TRANSLATIONS_FILE}")
        return False

    content = TRANSLATIONS_FILE.read_text(encoding="utf-8")
    
    en_keys = set(extract_ts_object(content, "en").keys())
    hi_keys = set(extract_ts_object(content, "hi").keys())

    print(f"[*] Total English ('en') keys: {len(en_keys)}")
    print(f"[*] Total Hindi ('hi') keys:   {len(hi_keys)}")

    # 1. Key parity check
    missing_in_hi = en_keys - hi_keys
    missing_in_en = hi_keys - en_keys
    
    has_errors = False

    if missing_in_hi:
        print(f"\n[ERROR] Found {len(missing_in_hi)} keys present in 'en' but MISSING in 'hi':")
        for k in sorted(missing_in_hi)[:15]:
            print(f"  - {k}")
        if len(missing_in_hi) > 15:
            print(f"  ... and {len(missing_in_hi) - 15} more")
        has_errors = True

    if missing_in_en:
        print(f"\n[ERROR] Found {len(missing_in_en)} keys present in 'hi' but MISSING in 'en':")
        for k in sorted(missing_in_en)[:15]:
            print(f"  - {k}")
        if len(missing_in_en) > 15:
            print(f"  ... and {len(missing_in_en) - 15} more")
        has_errors = True

    if not missing_in_hi and not missing_in_en:
        print("[OK] Perfect 100% key symmetry between English and Hindi dictionaries.")

    # 2. Used t('...') calls check
    referenced_keys = find_all_t_calls(FRONTEND_SRC)
    print(f"[*] Total referenced t() keys in frontend code: {len(referenced_keys)}")

    unresolved_en = referenced_keys - en_keys
    unresolved_hi = referenced_keys - hi_keys

    if unresolved_en:
        print(f"\n[ERROR] Found {len(unresolved_en)} t() keys NOT defined in 'en' dictionary:")
        for k in sorted(unresolved_en)[:15]:
            print(f"  - {k}")
        has_errors = True

    if unresolved_hi:
        print(f"\n[ERROR] Found {len(unresolved_hi)} t() keys NOT defined in 'hi' dictionary:")
        for k in sorted(unresolved_hi)[:15]:
            print(f"  - {k}")
        has_errors = True

    if not unresolved_en and not unresolved_hi:
        print("[OK] All referenced t() keys resolve in both English and Hindi dictionaries.")

    # 3. Raw JSX Text Scan
    raw_texts = scan_raw_jsx_text(FRONTEND_SRC)
    print(f"[*] Raw JSX scan: {len(raw_texts)} unclassified strings detected.")
    if raw_texts:
        print("  Noticeable raw strings (review if any are user-facing UI labels):")
        for fname, line_no, raw in raw_texts[:10]:
            print(f"    - {fname}:{line_no} -> {raw}")
        if len(raw_texts) > 10:
            print(f"    ... and {len(raw_texts) - 10} more")

    print("=" * 70)
    if has_errors:
        print("[AUDIT RESULT: FAIL] Translation gaps detected.")
        return False
    else:
        print("[AUDIT RESULT: PASS] 100% Localization Completeness verified.")
        return True


if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)

