"""
Daily log files + stdout (journalctl).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from shared.config import logging_enabled, logs_dir, log_denied

_lock = threading.Lock()

# kinds that should scream in the journal
_LOUD = {
    "unlock_fail",
    "unlock_ok",
    "lock",
    "sudomode_on",
    "sudomode_off",
    "sudomode_fail",
    "denied",
    "denied_approval",
    "denied_policy",
    "blocked_lock",
    "blocked_alarm",
    "rate_limited",
    "error",
    "executed",
}


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
        "detail": detail[:4000],
    }
    if extra:
        # keep extra reasonably sized for the file
        safe_extra = {}
        for k, v in extra.items():
            if isinstance(v, str) and len(v) > 8000:
                safe_extra[k] = v[:8000] + "…"
            else:
                safe_extra[k] = v
        record["extra"] = safe_extra

    path = _today_path()
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    # Always mirror to stdout so journalctl -f sees it live
    _print_human(kind, user_id, user_name, detail, extra)


def _print_human(
    kind: str,
    user_id: int | None,
    user_name: str,
    detail: str,
    extra: dict | None,
) -> None:
    uid = user_id if user_id is not None else "-"
    who = f"{user_name}({uid})" if user_name else f"uid={uid}"

    if kind == "unlock_fail":
        pw = (extra or {}).get("password_attempted", "?")
        # Loud / easy to spot in journalctl
        print(
            f"[Daemon] \033[1;31m*** UNLOCK FAIL ***\033[0m user={who} "
            f"password_attempted={pw!r} detail={detail!r}",
            flush=True,
        )
        return

    if kind == "sudomode_fail":
        pw = (extra or {}).get("password_attempted", "?")
        print(
            f"[Daemon] \033[1;31m*** SUDOMODE FAIL ***\033[0m user={who} "
            f"password_attempted={pw!r}",
            flush=True,
        )
        return

    if kind == "executed":
        rc = (extra or {}).get("returncode")
        out = (extra or {}).get("stdout", "")
        err = (extra or {}).get("stderr", "")
        print(f"[Daemon] EXECUTED user={who} cmd={detail!r} rc={rc}", flush=True)
        if out:
            for line in out.splitlines()[:80]:
                print(f"[Daemon]   stdout| {line}", flush=True)
            if out.count("\n") >= 80:
                print("[Daemon]   stdout| … (truncated)", flush=True)
        if err:
            for line in err.splitlines()[:40]:
                print(f"[Daemon]   stderr| {line}", flush=True)
        return

    if kind in _LOUD:
        print(f"[Daemon] {kind.upper()} user={who} {detail}", flush=True)
    else:
        print(f"[Daemon] {kind} user={who} {detail[:200]}", flush=True)


def export_recent(max_bytes: int = 7_000_000) -> Path | None:
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
