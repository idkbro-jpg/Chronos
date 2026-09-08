"""
One-shot status dump to wake.txt when the phone sends ?status.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from shared.config import ROOT
from daemon.history import recent as history_recent
from daemon.security import is_locked, is_alarm, alarm_reason, is_sudomode, sudomode_remaining

WAKE_FILE = ROOT / "wake.txt"
_start_time: float | None = None


def set_start_time(ts: float | None = None) -> None:
    global _start_time
    _start_time = time.time() if ts is None else ts


def _check_wlan() -> tuple[bool, str]:
    """Return (online, detail). Best-effort Linux check."""
    try:
        r = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            p = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if p.returncode == 0:
                return True, "default route + ping 8.8.8.8 ok"
            return True, "default route present, ping failed"
    except Exception as e:
        return False, f"ip/ping error: {e}"

    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "STATE", "general"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        state = (r.stdout or "").strip().lower()
        if "connected" in state:
            return True, f"nmcli state={state}"
        return False, f"nmcli state={state or 'unknown'}"
    except FileNotFoundError:
        return False, "no default route, nmcli not found"
    except Exception as e:
        return False, f"no default route, nmcli error: {e}"


def _try_start_wlan() -> str:
    """Best-effort: turn WiFi radio on / reconnect. Never raises."""
    actions = []
    for cmd, label in (
        (["nmcli", "radio", "wifi", "on"], "nmcli radio wifi on"),
        (["nmcli", "networking", "on"], "nmcli networking on"),
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            actions.append(f"{label} → rc={r.returncode}")
        except FileNotFoundError:
            actions.append(f"{label} → not found")
        except Exception as e:
            actions.append(f"{label} → {e}")
    return "; ".join(actions) if actions else "no action possible"


def _format_uptime(seconds: float) -> str:
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {sec}s"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


def write_wake_status() -> str:
    """
    Write a one-shot status dump to wake.txt (repo root).
    Returns a short human summary for Discord reply.
    """
    lines: list[str] = []
    now = datetime.now(timezone.utc)
    lines.append(f"written_at_utc: {now.isoformat()}")
    lines.append(f"written_at_local: {datetime.now().isoformat()}")

    online, detail = _check_wlan()
    lines.append(f"wlan_online: {online}")
    lines.append(f"wlan_detail: {detail}")
    if not online:
        act = _try_start_wlan()
        lines.append(f"wlan_recover_attempt: {act}")
        online2, detail2 = _check_wlan()
        lines.append(f"wlan_online_after: {online2}")
        lines.append(f"wlan_detail_after: {detail2}")

    if _start_time is None:
        uptime_s = 0.0
        lines.append("chronos_uptime: unknown (start time not set)")
    else:
        uptime_s = time.time() - _start_time
        lines.append(f"chronos_uptime_seconds: {int(uptime_s)}")
        lines.append(f"chronos_uptime: {_format_uptime(uptime_s)}")
        if uptime_s < 10:
            lines.append("note: chronos started less than 10s ago")

    lines.append("last_3_commands:")
    try:
        entries = history_recent(3)
        if not entries:
            lines.append("  (none)")
        else:
            for e in entries:
                ts = e.get("ts", 0)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                cmd = str(e.get("command", ""))[:120]
                uname = str(e.get("user_name", "?"))[:32]
                rc = e.get("returncode")
                rc_s = f" rc={rc}" if rc is not None else ""
                lines.append(f"  - [{dt} UTC] {uname}: {cmd}{rc_s}")
    except Exception as e:
        lines.append(f"  (history error: {e})")

    lines.append(f"locked: {is_locked()}")
    lines.append(f"alarm: {is_alarm()}" + (f" ({alarm_reason()})" if is_alarm() else ""))
    lines.append(
        f"sudomode: {is_sudomode()}"
        + (f" ({sudomode_remaining()}s left)" if is_sudomode() else "")
    )

    body = "\n".join(lines) + "\n"
    try:
        WAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = WAKE_FILE.with_suffix(".tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(WAKE_FILE)
        print(f"[Daemon] wake.txt written → {WAKE_FILE}", flush=True)
        return (
            f"wake.txt written ({WAKE_FILE.name}) · "
            f"wlan={'online' if online else 'offline'} · "
            f"uptime={_format_uptime(uptime_s)}"
        )
    except Exception as e:
        print(f"[Daemon] wake.txt write failed: {e}", flush=True)
        return f"wake.txt write failed: {e}"
