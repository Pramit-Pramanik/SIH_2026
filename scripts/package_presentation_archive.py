#!/usr/bin/env python3
"""
MandiQ Presentation Archive Packager.

Deterministically packages the repository into a clean, distributable ZIP archive
for evaluation, demonstration, or external submission.

Guarantees:
- Strictly excludes local secrets (.env, .env.local, etc.).
- Strictly excludes virtual environments (.venv/, venv/).
- Strictly excludes dependencies (node_modules/).
- Strictly excludes local databases (*.db, *.sqlite*).
- Strictly preserves .env.example, README.md, documentation, source code, and tests.
- Audits the resulting archive and fails closed if any forbidden file is included.
"""

import os
import sys
import zipfile
from pathlib import Path
from typing import List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories to strictly exclude from distributable archives
EXCLUDED_DIR_NAMES: Set[str] = {
    ".git",
    ".github",
    ".gemini",
    "node_modules",
    ".venv",
    "venv",
    "ENV",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    ".hypothesis",
    "scratch",
    "artifacts",
    "dist",
    "dist-ssr",
    "build"
}

# File extensions to strictly exclude
EXCLUDED_EXTENSIONS: Set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".sqlite",
    ".sqlite3"
}

# Exact file names to strictly exclude
EXCLUDED_FILE_NAMES: Set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    ".DS_Store",
    "Thumbs.db"
}


def is_excluded_path(path: Path) -> bool:
    """Determine if a file or directory path should be excluded from packaging."""
    rel = path.relative_to(PROJECT_ROOT)
    parts = rel.parts

    # 1. Check directory components
    for part in parts[:-1]:
        if part in EXCLUDED_DIR_NAMES:
            return True

    # If it's a directory being inspected
    if path.is_dir():
        return parts[-1] in EXCLUDED_DIR_NAMES

    # 2. Check filename
    file_name = parts[-1]
    if file_name in EXCLUDED_FILE_NAMES:
        return True

    # Any file starting with .env other than .env.example
    if file_name.startswith(".env") and file_name != ".env.example":
        return True

    # 3. Check extension
    if path.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True

    return False


def verify_archive(archive_path: Path) -> List[str]:
    """Inspects a generated archive to verify safety and completeness."""
    violations = []
    has_env_example = False
    has_backend_main = False
    has_frontend_pkg = False
    has_frontend_lock = False
    has_backend_req = False
    has_setup_demo = False

    with zipfile.ZipFile(archive_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            norm_name = name.replace("\\", "/")

            # Check required files
            if norm_name.endswith(".env.example"):
                has_env_example = True
            if norm_name.endswith("backend/app/main.py"):
                has_backend_main = True
            if norm_name.endswith("frontend/package.json"):
                has_frontend_pkg = True
            if norm_name.endswith("frontend/package-lock.json"):
                has_frontend_lock = True
            if norm_name.endswith("backend/requirements.txt"):
                has_backend_req = True
            if norm_name.endswith("scripts/setup_demo_env.py"):
                has_setup_demo = True

            # Check forbidden files
            parts = norm_name.split("/")
            file_name = parts[-1]

            if file_name == ".env" or (file_name.startswith(".env") and file_name != ".env.example"):
                violations.append(f"Forbidden secret file in archive: {name}")

            if "node_modules" in parts:
                violations.append(f"Forbidden node_modules path in archive: {name}")

            if ".venv" in parts or "venv" in parts:
                violations.append(f"Forbidden virtual environment path in archive: {name}")

            if "dist" in parts or "build" in parts:
                violations.append(f"Forbidden build artifact directory in archive: {name}")

            if any(name.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
                violations.append(f"Forbidden file extension in archive: {name}")

    if not has_env_example:
        violations.append("Missing required .env.example file in archive!")
    if not has_backend_main:
        violations.append("Missing backend/app/main.py in archive!")
    if not has_frontend_pkg:
        violations.append("Missing frontend/package.json in archive!")
    if not has_frontend_lock:
        violations.append("Missing frontend/package-lock.json in archive!")
    if not has_backend_req:
        violations.append("Missing backend/requirements.txt in archive!")
    if not has_setup_demo:
        violations.append("Missing scripts/setup_demo_env.py in archive!")

    return violations


def create_presentation_archive(output_path: Path) -> bool:
    """Creates a clean presentation ZIP archive at output_path."""
    print(f"[*] Packaging repository from: {PROJECT_ROOT}")
    print(f"[*] Target archive: {output_path}")

    # Ensure output parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Temporary archive path to prevent partial writes
    temp_output = output_path.with_suffix(".tmp.zip")
    if temp_output.exists():
        temp_output.unlink()

    total_files = 0
    total_uncompressed_bytes = 0

    root_folder_name = PROJECT_ROOT.name

    with zipfile.ZipFile(temp_output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            root_path = Path(root)

            # Prune excluded directories in-place to avoid descending into them
            dirs[:] = [d for d in dirs if not is_excluded_path(root_path / d)]

            for f in files:
                file_path = root_path / f
                if is_excluded_path(file_path):
                    continue

                rel_path = file_path.relative_to(PROJECT_ROOT)
                arcname = f"{root_folder_name}/{rel_path.as_posix()}"

                zf.write(file_path, arcname=arcname)
                total_files += 1
                total_uncompressed_bytes += file_path.stat().st_size

    # Verify the archive before finalizing
    print(f"[*] Validating archive security and integrity...")
    violations = verify_archive(temp_output)

    if violations:
        temp_output.unlink(missing_ok=True)
        print("\n[!] FATAL PACKAGING ERRORS DETECTED:")
        for v in violations:
            print(f"    - {v}")
        return False

    # Move temp archive to final target
    if output_path.exists():
        output_path.unlink()
    temp_output.rename(output_path)

    archive_size_mb = output_path.stat().st_size / (1024 * 1024)
    uncompressed_mb = total_uncompressed_bytes / (1024 * 1024)

    print(f"[+] Archive successfully created: {output_path}")
    print(f"    - Files packaged: {total_files}")
    print(f"    - Uncompressed: {uncompressed_mb:.2f} MB")
    print(f"    - Compressed: {archive_size_mb:.2f} MB")
    print(f"    - .env.example included: YES")
    print(f"    - .env excluded: YES (zero secrets packaged)")
    print(f"    - node_modules excluded: YES")
    print(f"    - .venv excluded: YES")
    print(f"    - *.db excluded: YES")
    print(f"    - frontend/dist excluded: YES")
    return True


if __name__ == "__main__":
    target = PROJECT_ROOT.parent / f"{PROJECT_ROOT.name}.zip"
    if len(sys.argv) > 1 and sys.argv[1] not in ("-h", "--help"):
        target = Path(sys.argv[1]).resolve()

    success = create_presentation_archive(target)
    sys.exit(0 if success else 1)
