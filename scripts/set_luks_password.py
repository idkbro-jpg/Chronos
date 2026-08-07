#!/usr/bin/env python3
"""
Interactively set / update the encrypted LUKS password file.

Usage (from project root, venv active):

    python -m scripts.set_luks_password

Creates:
  secrets/machine.key   (random, local only)
  secrets/luks.enc      (encrypted LUKS passphrase)
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Allow running as python -m scripts.set_luks_password from repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from daemon.luks import encrypt_password, ensure_machine_secret  # noqa: E402
from shared.config import luks_password_file, luks_machine_secret_file, load_config  # noqa: E402


def main() -> int:
    load_config(force=True)
    print("Chronos – store encrypted LUKS password")
    print(f"  machine secret → {luks_machine_secret_file()}")
    print(f"  password file  → {luks_password_file()}")
    print()

    ensure_machine_secret()

    pw1 = getpass.getpass("LUKS passphrase: ")
    pw2 = getpass.getpass("Repeat passphrase: ")
    if pw1 != pw2:
        print("Passphrases do not match.")
        return 1
    if not pw1:
        print("Empty passphrase refused.")
        return 1

    encrypt_password(pw1)
    print()
    print("Saved.")
    print("Next:")
    print("  1) Set luks.enabled: true and luks.device in config.yml")
    print("  2) systemctl --user restart chronos-daemon.service")
    print("  3) In Discord: !luksunlock  then ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
