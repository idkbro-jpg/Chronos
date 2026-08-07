"""
Lock, alarm, rate-limit state.

Note: Discord bots do NOT see the end-user's IP address.
We key everything by Discord user id (and log that).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

from shared.config import (
    state_dir,
    lock_hash_file,
    rate_limit_enabled,
    rate_limit_max,
    rate_limit_window,
    rate_limit_triggers_alarm,
    alarm_blocks_all,
)


def _ensure_state_dir() -> Path:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _flag(name: str) -> Path:
    return _ensure_state_dir() / name


def is_locked() -> bool:
    return _flag("LOCKED").exists()


def is_alarm() -> bool:
    return _flag("ALARM").exists()


def set_locked(on: bool) -> None:
    p = _flag("LOCKED")
    if on:
        p.write_text(str(time.time()), encoding="utf-8")
    elif p.exists():
        p.unlink()


def set_alarm(on: bool, reason: str = "") -> None:
    p = _flag("ALARM")
    if on:
        p.write_text(f"{time.time()}\n{reason}\n", encoding="utf-8")
    elif p.exists():
        p.unlink()


def alarm_reason() -> str:
    p = _flag("ALARM")
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[1] if len(lines) > 1 else ""


def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, hash_hex = stored.strip().split("$", 2)
        if algo != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def save_lock_password(password: str) -> Path:
    path = lock_hash_file()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.write_text(hash_password(password), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def check_lock_password(password: str) -> bool:
    path = lock_hash_file()
    if not path.exists():
        return False
    return verify_password(password, path.read_text(encoding="utf-8"))


# --- rate limit (in-memory; resets on daemon restart — fine for personal use) ---
_hits: dict[int, deque[float]] = defaultdict(deque)


def check_rate_limit(user_id: int) -> tuple[bool, str]:
    """
    Returns (allowed, message).
    If not allowed and trigger_alarm, sets alarm.
    """
    if not rate_limit_enabled():
        return True, ""

    now = time.time()
    window = rate_limit_window()
    limit = rate_limit_max()
    q = _hits[user_id]

    while q and now - q[0] > window:
        q.popleft()

    if len(q) >= limit:
        msg = f"rate limit: {limit}/{window}s exceeded by user {user_id}"
        if rate_limit_triggers_alarm():
            set_alarm(True, msg)
        return False, msg

    q.append(now)
    return True, ""


def commands_blocked() -> tuple[bool, str]:
    """
    Whether normal commands should be refused.
    Unlock via DM still allowed at a higher layer.
    """
    if is_locked():
        return True, "System is LOCKED. DM the bot: unlock <password>"
    if is_alarm() and alarm_blocks_all():
        return True, f"ALARM active ({alarm_reason() or 'unknown'}). Clear locally or unlock."
    return False, ""
