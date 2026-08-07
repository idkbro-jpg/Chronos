#!/usr/bin/env python3
"""
Set the lock password (e.g. from Bitwarden).

    python -m scripts.set_lock_password

Stores only a scrypt hash in secrets/lock.hash — never the plaintext.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from daemon.security import save_lock_password  # noqa: E402
from shared.config import load_config, lock_hash_file  # noqa: E402


def main() -> int:
    load_config(force=True)
    print("Chronos – set lock password")
    print(f"  hash file → {lock_hash_file()}")
    print()
    print("Tipp: langes Passwort aus Bitwarden generieren und einfügen.")
    print()

    pw1 = getpass.getpass("Lock password: ")
    pw2 = getpass.getpass("Repeat: ")
    if pw1 != pw2:
        print("Mismatch.")
        return 1
    if len(pw1) < 12:
        print("Please use at least 12 characters.")
        return 1

    path = save_lock_password(pw1)
    print()
    print(f"Saved hash → {path}")
    print("Usage:")
    print("  !lock              → arm lock")
    print("  DM to bot: unlock <password>  → disarm lock + alarm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
