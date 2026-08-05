"""
Simple terminal-based approval.
Later we can add Discord reactions / buttons.
"""

import getpass
from daemon.config import APPROVAL_PASSWORD

def request_approval(command: str, author: str) -> bool:
    print("\n" + "=" * 60)
    print(f"New command request from: {author}")
    print(f"Command: {command}")
    print("=" * 60)

    try:
        password = getpass.getpass("Enter approval password to execute (or leave empty to deny): ")
    except (KeyboardInterrupt, EOFError):
        print("\n[Daemon] Approval cancelled.")
        return False

    if password == APPROVAL_PASSWORD:
        print("[Daemon] Approved.")
        return True

    print("[Daemon] Denied.")
    return False
