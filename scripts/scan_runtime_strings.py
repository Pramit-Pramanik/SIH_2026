import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

comp_dir = Path("frontend/src/components")
files = [
    "FarmerPortal.tsx",
    "QualityStation.tsx",
    "QueueMonitor.tsx",
    "WeighbridgeStation.tsx",
    "BillingPayoutStation.tsx",
    "GateTerminal.tsx",
    "AdminDashboard.tsx"
]

print("Scanning components for user-facing runtime strings...")

for fname in files:
    fpath = comp_dir / fname
    if not fpath.exists():
        continue
    content = fpath.read_text(encoding="utf-8")
    lines = content.splitlines()
    print(f"\n==================== {fname} ====================")
    
    # 1. Look for message:
    for idx, line in enumerate(lines, 1):
        # setFeedback / message assignments
        if "message:" in line or "message :" in line:
            if "t(" not in line:
                print(f"  Line {idx} [message]: {line.strip()}")
        # throw new Error
        elif "throw new Error(" in line:
            if "t(" not in line:
                print(f"  Line {idx} [throw]: {line.strip()}")
        # alert or confirm
        elif "alert(" in line or "confirm(" in line:
            if "t(" not in line:
                print(f"  Line {idx} [alert/confirm]: {line.strip()}")
        # placeholder=
        elif "placeholder=" in line:
            if "t(" not in line and not line.strip().startswith("//"):
                print(f"  Line {idx} [placeholder]: {line.strip()}")
        # setResolutionError, setMspResolutionError, etc.
        elif ("Error(" in line or "error:" in line or "Error:" in line) and any(kw in line for kw in ["set", "Error"]):
            if "t(" not in line and any(quote in line for quote in ["'", '"', '`']) and not line.strip().startswith("//") and not line.strip().startswith("/*"):
                # filter out simple code
                if any(w in line for w in ["Failed", "Invalid", "Cannot", "Please", "Error", "not found", "offline", "rejected", "missing"]):
                    print(f"  Line {idx} [error-setter]: {line.strip()}")
