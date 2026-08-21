"""
Simple rotating-ish daily log files.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from shared.config import logging_enabled, logs_dir, log_denied

_lock = threading.Lock()


def _today_path() -> Path:
    d = logs_dir()
    d.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return d / f"chronos-{day}.log"


def log_event(
    kind: str,
    *,
    user_id: int | None = None,
    user_name: str = "",
    detail: str = "",
    extra: dict | None = None,
) -> None:
    if not logging_enabled():
        return
    if kind in ("denied", "rate_limited", "blocked_lock", "blocked_alarm") and not log_denied():
        return

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "user_id": user_id,
        "user_name": user_name,
        "detail": detail[:2000],
    }
    if extra:
        record["extra"] = extra

    path = _today_path()
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()


def export_recent(max_bytes: int = 7_000_000) -> Path | None:
    """
    Build a single text file with today's + yesterday's logs for Discord upload.
    """
    d = logs_dir()
    if not d.exists():
        return None

    files = sorted(d.glob("chronos-*.log"), reverse=True)[:3]
    if not files:
        return None

    out = d / "export-latest.txt"
    total = 0
    parts: list[str] = []
    for fp in reversed(files):
        chunk = fp.read_text(encoding="utf-8", errors="replace")
        if total + len(chunk) > max_bytes:
            remain = max_bytes - total
            if remain > 0:
                parts.append(chunk[-remain:])
            break
        parts.append(chunk)
        total += len(chunk)

    out.write_text("".join(parts), encoding="utf-8")
    return out
