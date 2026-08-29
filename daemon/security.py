"""
Lock, alarm, rate-limit, sudomode state.

Note: Discord bots do NOT see the end-user's IP address.
We key everything by Discord user id (and log that).
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
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
    execution_mode,
    allowed_patterns,
)

_rate_lock = threading.Lock()
_flag_lock = threading.Lock()

# Default sudomode lifetime (seconds)
SUDOMODE_TTL = 15 * 60


def _ensure_state_dir() -> Path:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _flag(name: str) -> Path:
    return _ensure_state_dir() / name


def is_locked() -> bool:
    with _flag_lock:
        return _flag("LOCKED").exists()


def is_alarm() -> bool:
    with _flag_lock:
        return _flag("ALARM").exists()


def set_locked(on: bool) -> None:
    with _flag_lock:
        p = _flag("LOCKED")
        if on:
            p.write_text(str(time.time()), encoding="utf-8")
        elif p.exists():
            p.unlink()


def set_alarm(on: bool, reason: str = "") -> None:
    with _flag_lock:
        p = _flag("ALARM")
        if on:
            p.write_text(f"{time.time()}\n{reason}\n", encoding="utf-8")
        elif p.exists():
            p.unlink()


def alarm_reason() -> str:
    with _flag_lock:
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


# --- sudomode (skip ✅ approval for a limited time after DM password) ---

def is_sudomode() -> bool:
    with _flag_lock:
        p = _flag("SUDOMODE")
        if not p.exists():
            return False
        try:
            expires = float(p.read_text(encoding="utf-8").strip().splitlines()[0])
        except Exception:
            p.unlink(missing_ok=True)
            return False
        if time.time() > expires:
            p.unlink(missing_ok=True)
            return False
        return True


def sudomode_remaining() -> int:
    with _flag_lock:
        p = _flag("SUDOMODE")
        if not p.exists():
            return 0
        try:
            expires = float(p.read_text(encoding="utf-8").strip().splitlines()[0])
        except Exception:
            p.unlink(missing_ok=True)
            return 0
        remaining = max(0, int(expires - time.time()))
        if remaining == 0:
            # Match is_sudomode: do not leave a stale expired flag file behind
            p.unlink(missing_ok=True)
        return remaining


def set_sudomode(on: bool, ttl: int = SUDOMODE_TTL, user_id: int | None = None) -> None:
    with _flag_lock:
        p = _flag("SUDOMODE")
        if on:
            expires = time.time() + ttl
            p.write_text(f"{expires}\n{user_id or ''}\n", encoding="utf-8")
        elif p.exists():
            p.unlink()


# --- rate limit ---
_hits: dict[int, deque[float]] = defaultdict(deque)
_hits_loaded = False


def _rate_limit_path() -> Path:
    return _ensure_state_dir() / "rate_limit.json"


def _load_rate_hits_unlocked() -> None:
    global _hits_loaded
    if _hits_loaded:
        return
    _hits_loaded = True
    path = _rate_limit_path()
    if not path.exists():
        return
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        now = time.time()
        window = rate_limit_window()
        for uid_str, timestamps in (data or {}).items():
            try:
                uid = int(uid_str)
            except (TypeError, ValueError):
                continue
            q: deque[float] = deque()
            for t in timestamps or []:
                try:
                    tf = float(t)
                except (TypeError, ValueError):
                    continue
                if now - tf <= window:
                    q.append(tf)
            if q:
                _hits[uid] = q
    except Exception:
        pass


def _save_rate_hits_unlocked() -> None:
    path = _rate_limit_path()
    try:
        import json

        now = time.time()
        window = rate_limit_window()
        out: dict[str, list[float]] = {}
        stale: list[int] = []
        for uid, q in _hits.items():
            recent = [t for t in q if now - t <= window]
            if recent:
                out[str(uid)] = recent
                # Keep the in-memory deque aligned with what we persist
                q.clear()
                q.extend(recent)
            else:
                stale.append(uid)
        for uid in stale:
            _hits.pop(uid, None)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def check_rate_limit(user_id: int) -> tuple[bool, str, int]:
    if not rate_limit_enabled():
        return True, "", 0

    trigger_alarm = False
    msg = ""
    retry_after = 0

    with _rate_lock:
        _load_rate_hits_unlocked()

        now = time.time()
        window = rate_limit_window()
        limit = rate_limit_max()
        q = _hits[user_id]

        while q and now - q[0] > window:
            q.popleft()

        if len(q) >= limit:
            oldest = q[0] if q else now
            retry_after = max(1, int(window - (now - oldest)) + 1)
            msg = f"rate limit: {limit}/{window}s exceeded by user {user_id}"
            if rate_limit_triggers_alarm():
                trigger_alarm = True
            # Do not call set_alarm while holding _rate_lock (avoids nested locks).
        else:
            q.append(now)
            _save_rate_hits_unlocked()
            return True, "", 0

    if trigger_alarm:
        set_alarm(True, msg)
    return False, msg, retry_after


def commands_blocked() -> tuple[bool, str]:
    if is_locked():
        return True, "System is LOCKED. DM the bot: unlock <password>"
    if is_alarm() and alarm_blocks_all():
        return True, f"ALARM active ({alarm_reason() or 'unknown'}). Clear locally or unlock."
    return False, ""


def command_allowed_by_policy(command: str) -> tuple[bool, str]:
    mode = execution_mode()
    if mode != "allowlist":
        return True, ""

    patterns = allowed_patterns()
    if not patterns:
        return False, "allowlist mode with empty allowed_patterns – blocked"

    cmd = command.strip()
    for pat in patterns:
        if not pat:
            continue
        if pat.startswith("re:"):
            try:
                if re.search(pat[3:], cmd):
                    return True, ""
            except re.error:
                continue
            continue

        try:
            regex = re.escape(pat).replace(r"\*", ".*").replace(r"\?", ".")
            if re.fullmatch(regex, cmd):
                return True, ""
        except re.error:
            continue

    return False, "command not in allowlist (mode=allowlist)"
