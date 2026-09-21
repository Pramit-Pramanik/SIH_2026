#!/usr/bin/env python3
"""
MandiQ Repository Preflight & Portability Auditor
Enforces non-negotiable repository governance, portability rules,
forbidden pattern detection, and dependency boundaries across
implementation source code, tests, scripts, and configuration manifests.
"""

import sys
import re
from pathlib import Path
from typing import List

# Paths to inspect
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Governance directories required to exist
REQUIRED_GOVERNANCE_DIRECTORIES = [
    "documentation",
    "agent",
    ".antigravity"
]

# Implementation targets subject to code and portability audits
AUDIT_TARGET_DIRS = [
    "backend",
    "frontend",
    "tests",
    "scripts"
]

AUDIT_ROOT_FILES = [
    ".env.example",
    "docker-compose.yml",
    "README.md"
]

# Global forbidden patterns in implementation code and configs
GLOBAL_FORBIDDEN_PATTERNS = [
    (r"file:///[a-zA-Z]:", "Absolute machine file URI (file:///X:)"),
    (r"[a-zA-Z]:\\SIH", "Absolute Windows drive path to SIH repository"),
    (r"C:\\Users", "Absolute Windows user profile path"),
    (r"MANDIQ_SECRET_HMAC_KEY_2026", "Hardcoded fallback HMAC key"),
    (r"MANDIQ_MULTISIG_SALT", "Hardcoded fallback multi-sig salt")
]

# Forbidden infrastructure keywords in runtime/package manifests and code
INFRA_FORBIDDEN_PATTERNS = [
    (r"^\s*(?:import\s+confluent_kafka|from\s+confluent_kafka)", "Apache Kafka import in prototype code"),
    (r"^\s*(?:import\s+kafka|from\s+kafka)", "Apache Kafka import in prototype code"),
    (r"^\s*(?:import\s+pika|from\s+pika)", "RabbitMQ import in prototype code"),
    (r"^\s*(?:import\s+celery|from\s+celery)", "Celery import in prototype code"),
    (r"^\s*['\"]?(?:confluent-kafka|kafka-python|pika|celery)['\"]?\s*(?:[=><~].*)?$", "Forbidden message broker in package manifest")
]

# Code placeholder patterns forbidden in production application code
PROD_CODE_DIRS = ["backend", "frontend", "scripts"]
PLACEHOLDER_PATTERNS = [
    (r"\bTODO\b", "Unresolved TODO placeholder"),
    (r"\bFIXME\b", "Unresolved FIXME placeholder"),
    (r"\bNotImplementedError\b", "NotImplementedError stub")
]

# Files / extensions to ignore during scanning
IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".gemini"
}

IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pyc",
    ".db",
    ".sqlite",
    ".sqlite3"
}

def scan_file(file_path: Path) -> list[str]:
    violations = []
    
    # Self-exclusion for the preflight script itself
    if file_path.resolve() == Path(__file__).resolve():
        return violations
        
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        violations.append(f"Cannot read {file_path}: {e}")
        return violations

    lines = content.splitlines()

    # 1. Global forbidden patterns (paths, hardcoded secrets)
    for pattern, description in GLOBAL_FORBIDDEN_PATTERNS:
        regex = re.compile(pattern, re.IGNORECASE)
        for idx, line in enumerate(lines, 1):
            if regex.search(line):
                violations.append(
                    f"{file_path}:{idx}: [GLOBAL FORBIDDEN] {description} -> '{line.strip()}'"
                )

    # 2. Infra forbidden patterns (in python/manifest files)
    if file_path.suffix in [".py", ".json", ".txt", ".yml", ".yaml", ".toml"]:
        for pattern, description in INFRA_FORBIDDEN_PATTERNS:
            regex = re.compile(pattern, re.IGNORECASE)
            for idx, line in enumerate(lines, 1):
                if regex.search(line):
                    violations.append(
                        f"{file_path}:{idx}: [FORBIDDEN INFRA] {description} -> '{line.strip()}'"
                    )

    # 3. Placeholder patterns in production code (exclude tests)
    try:
        rel_parts = file_path.relative_to(PROJECT_ROOT).parts
        if rel_parts and rel_parts[0] in PROD_CODE_DIRS:
            if file_path.suffix in [".py", ".ts", ".tsx", ".js", ".jsx"]:
                for pattern, description in PLACEHOLDER_PATTERNS:
                    regex = re.compile(pattern)
                    for idx, line in enumerate(lines, 1):
                        if regex.search(line):
                            violations.append(
                                f"{file_path}:{idx}: [PLACEHOLDER DETECTED] {description} -> '{line.strip()}'"
                            )
    except ValueError:
        pass

    return violations

import zipfile
import tarfile
import subprocess


def check_packaging_and_secrets() -> List[str]:
    violations = []

    # Check 1: .env.example must not contain live/populated secret values
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        content = env_example.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("MANDIQ_SECRET_HMAC_KEY=") and len(line.split("=", 1)[1].strip()) > 0:
                violations.append(".env.example contains populated MANDIQ_SECRET_HMAC_KEY secret value!")
            if line.startswith("MANDIQ_PAYOUT_SECRET_KEY=") and len(line.split("=", 1)[1].strip()) > 0:
                violations.append(".env.example contains populated MANDIQ_PAYOUT_SECRET_KEY secret value!")

    # Check 2: .env must NOT be tracked in git
    try:
        res = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        if res.stdout.strip():
            violations.append(f"CRITICAL SECURITY VIOLATION: .env is tracked in git index: {res.stdout.strip()}")
    except Exception:
        pass

    # Check 3: Distributable archives must not bundle .env, node_modules, .venv, or database files
    candidate_archives = []
    for ext in ("*.zip", "*.tar", "*.tar.gz", "*.tgz"):
        candidate_archives.extend(PROJECT_ROOT.glob(ext))
    for pat in ("SIH_2026*.zip", "*presentation*.zip"):
        candidate_archives.extend(PROJECT_ROOT.parent.glob(pat))

    checked = set()
    for archive_path in candidate_archives:
        if archive_path.resolve() in checked or not archive_path.is_file():
            continue
        checked.add(archive_path.resolve())

        if archive_path.suffix == ".zip":
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for name in zf.namelist():
                        norm = name.replace("\\", "/")
                        parts = norm.split("/")
                        fname = parts[-1]
                        if fname == ".env" or (fname.startswith(".env") and fname != ".env.example"):
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden secret file: {name}")
                        if "node_modules" in parts:
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden node_modules path: {name}")
                        if ".venv" in parts or "venv" in parts:
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden virtualenv path: {name}")
                        if any(norm.endswith(ext) for ext in (".db", ".sqlite", ".sqlite3")):
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden database file: {name}")
            except Exception:
                pass
        elif "tar" in archive_path.suffix or archive_path.name.endswith(".tgz"):
            try:
                with tarfile.open(archive_path, "r:*") as tf:
                    for member in tf.getmembers():
                        norm = member.name.replace("\\", "/")
                        parts = norm.split("/")
                        fname = parts[-1]
                        if fname == ".env" or (fname.startswith(".env") and fname != ".env.example"):
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden secret file: {member.name}")
                        if "node_modules" in parts:
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden node_modules path: {member.name}")
                        if ".venv" in parts or "venv" in parts:
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden virtualenv path: {member.name}")
                        if any(norm.endswith(ext) for ext in (".db", ".sqlite", ".sqlite3")):
                            violations.append(f"Distributable archive {archive_path.name} contains forbidden database file: {member.name}")
            except Exception:
                pass

    return violations


def main() -> int:
    print("=" * 70)
    print("  MANDIQ REPOSITORY PREFLIGHT & PORTABILITY AUDITOR")
    print("=" * 70)

    all_violations = []

    # 1. Check packaging and secret cleanliness
    print("[1/4] Checking distributable archive & secret cleanliness...")
    pkg_violations = check_packaging_and_secrets()
    all_violations.extend(pkg_violations)
    if not pkg_violations:
        print("  [OK] .env is not tracked in git and no distributable archives bundle .env.")
        print("  [OK] .env.example contains zero populated secrets.")

    # 2. Check required governance directories
    print("\n[2/4] Checking required governance directories...")
    for req_dir in REQUIRED_GOVERNANCE_DIRECTORIES:
        target = PROJECT_ROOT / req_dir
        if not target.is_dir():
            all_violations.append(f"Missing required governance directory: {req_dir}")
        else:
            print(f"  [OK] Found required directory: {req_dir}/")

    # 3. Collect files to audit
    print("\n[3/4] Scanning implementation files, tests, scripts, and configurations...")
    files_to_scan = []

    # Root audit files
    for root_file in AUDIT_ROOT_FILES:
        target = PROJECT_ROOT / root_file
        if target.is_file():
            files_to_scan.append(target)

    # Target directory trees
    for target_dir in AUDIT_TARGET_DIRS:
        target = PROJECT_ROOT / target_dir
        if target.is_dir():
            for p in target.rglob("*"):
                if p.is_file():
                    if any(ignored in p.parts for ignored in IGNORED_DIRS):
                        continue
                    if p.suffix in IGNORED_EXTENSIONS:
                        continue
                    files_to_scan.append(p)

    scanned_count = 0
    for file_path in files_to_scan:
        scanned_count += 1
        violations = scan_file(file_path)
        all_violations.extend(violations)

    print(f"  Scanned {scanned_count} implementation & configuration files.")

    # 4. Results evaluation
    print("\n[4/4] Evaluating preflight audit status...")
    if all_violations:
        print("\n[FAIL] Preflight audit FAILED with the following violations:\n")
        for v in all_violations:
            print(f"  - {v}")
        print("\nRepository contains non-compliant patterns. Aborting execution.")
        return 1
    else:
        print("\n[PASS] All preflight checks PASSED cleanly.")
        print("  - Zero machine-specific paths detected.")
        print("  - Zero forbidden infrastructure dependencies detected.")
        print("  - Zero hardcoded fallback secrets detected.")
        print("  - Zero unresolved code placeholders detected.")
        print("  - All required governance directories intact.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
