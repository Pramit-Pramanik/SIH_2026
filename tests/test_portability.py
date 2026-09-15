import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_preflight_portability_check():
    """Verify that the automated preflight script succeeds with zero violations."""
    script_path = PROJECT_ROOT / "scripts" / "preflight_check.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT)
    )
    assert result.returncode == 0, f"Preflight check failed:\n{result.stdout}\n{result.stderr}"
    assert "[PASS] All preflight checks PASSED cleanly." in result.stdout
