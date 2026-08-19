"""
Lightweight command history for !history / !last.
Persisted under state/ so it survives restarts.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from shared.config import state_dir, history_enabled, history_max_entries

_lock = threading.Lock()


def _path() -> Path:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "history.json"


def _load_unlocked() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_unlocked(entries: list[dict]) -> None:
    """Atomic write (temp file + rename) to avoid torn JSON on crash."""
    try:
        path = _path()
        payload = json.dumps(entries[-history_max_entries():], ensure_ascii=False)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def record(user_id: int, user_name: str, command: str, returncode: int | None = None) -> None:
    if not history_enabled():
        return
    with _lock:
        entries = _load_unlocked()
        entries.append(
            {
                "ts": time.time(),
                "user_id": user_id,
                "user_name": user_name,
                "command": command[:500],
                "returncode": returncode,
            }
        )
        _save_unlocked(entries)


def recent(n: int = 10) -> list[dict]:
    if not history_enabled():
        return []
    n = max(1, min(n, history_max_entries()))
    with _lock:
        return _load_unlocked()[-n:]


def last_command() -> dict | None:
    entries = recent(1)
    return entries[-1] if entries else None
