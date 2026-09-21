#!/usr/bin/env python3
"""
MandiQ Demo Environment Initializer.

Safely configures a local .env file from .env.example for local evaluation or judge demonstration.
Generates fresh ephemeral 64-character hex cryptographic secrets via Python's standard `secrets` module
without exposing or checking in any team/production secrets.
"""
import sys
import secrets
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE_PATH = REPOSITORY_ROOT / ".env.example"
ENV_PATH = REPOSITORY_ROOT / ".env"


def generate_secure_hex(num_bytes: int = 32) -> str:
    """Generates a secure cryptographic random hex string."""
    return secrets.token_hex(num_bytes)


def setup_demo_env(force: bool = False) -> bool:
    """
    Creates or updates .env based on .env.example with fresh secure random secrets.
    """
    if not ENV_EXAMPLE_PATH.exists():
        print(f"[-] Error: {ENV_EXAMPLE_PATH} does not exist.")
        return False

    if ENV_PATH.exists() and not force:
        print(f"[*] Notice: {ENV_PATH} already exists. Use --force to regenerate.")
        return True

    example_content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

    # Generate fresh random secrets
    hmac_key = generate_secure_hex(32)
    payout_key = generate_secure_hex(32)

    # Replace empty placeholders
    updated_content = example_content.replace(
        "MANDIQ_SECRET_HMAC_KEY=",
        f"MANDIQ_SECRET_HMAC_KEY={hmac_key}"
    ).replace(
        "MANDIQ_PAYOUT_SECRET_KEY=",
        f"MANDIQ_PAYOUT_SECRET_KEY={payout_key}"
    )

    ENV_PATH.write_text(updated_content, encoding="utf-8")
    print(f"[+] Successfully generated local demo environment: {ENV_PATH}")
    print("    - MANDIQ_SECRET_HMAC_KEY populated with fresh 32-byte hex secret.")
    print("    - MANDIQ_PAYOUT_SECRET_KEY populated with fresh 32-byte hex secret.")
    print("    - Local runtime is ready for development, testing, and judge demonstration.")
    return True


if __name__ == "__main__":
    force_overwrite = "--force" in sys.argv
    success = setup_demo_env(force=force_overwrite)
    sys.exit(0 if success else 1)
