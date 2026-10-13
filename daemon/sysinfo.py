"""
Lightweight host / Pi-aware sysinfo for !sysinfo.

Read-only. Never executes user-supplied commands. Missing sensors become
placeholders so the command stays useful on desktops and SBCs alike.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import List

from shared.config import logs_dir


def _read_text(path: Path, max_bytes: int = 4096) -> str:
    try:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace").strip()
    except OSError:
        return ""


def _hostname_line() -> str:
    try:
        import platform

        return (
            f"**Host:** `{socket.gethostname()}` "
            f"({platform.machine()} / {platform.system()} {platform.release()})"
        )
    except Exception:
        try:
            return f"**Host:** `{socket.gethostname()}`"
        except Exception:
            return "**Host:** `n/a`"


def _uptime_line() -> str:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            up = float(f.read().split()[0])
        days, rem = divmod(int(up), 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        return f"**Uptime:** `{days}d {hours}h {mins}m {secs}s`"
    except Exception:
        return "**Uptime:** `n/a`"


def _temp_line() -> str:
    # thermal_zone (most Linux / Pi)
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        val = _read_text(zone)
        if val.isdigit():
            t = int(val) / 1000.0
            name = zone.parent.name
            return f"**Temp ({name}):** `{t:.1f} °C`"
    # vcgencmd fallback (Raspberry Pi)
    try:
        out = subprocess.check_output(
            ["vcgencmd", "measure_temp"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            text=True,
        ).strip()
        if out:
            return f"**Temp (vcgencmd):** `{out}`"
    except Exception:
        pass
    return "**Temp:** `n/a`"


def _throttle_line() -> str:
    try:
        out = subprocess.check_output(
            ["vcgencmd", "get_throttled"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            text=True,
        ).strip()
        if not out:
            return "**Throttled:** `n/a`"
        flags: List[str] = []
        if "0x" in out:
            try:
                val = int(out.split("=")[-1].strip(), 16)
                mapping = {
                    0: "under-voltage now",
                    1: "freq capped now",
                    2: "throttled now",
                    3: "soft temp limit now",
                    16: "under-voltage occurred",
                    17: "freq capped occurred",
                    18: "throttled occurred",
                    19: "soft temp limit occurred",
                }
                for bit, name in mapping.items():
                    if val & (1 << bit):
                        flags.append(name)
            except Exception:
                pass
        extra = (" → " + ", ".join(flags)) if flags else " (ok)"
        return f"**Throttled:** `{out}`{extra}"
    except FileNotFoundError:
        return "**Throttled:** `n/a` (no vcgencmd)"
    except Exception:
        return "**Throttled:** `n/a`"


def _mem_line() -> str:
    try:
        mem: dict[str, str] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = v.strip()
        total = int(mem.get("MemTotal", "0").split()[0])
        avail = int(mem.get("MemAvailable", mem.get("MemFree", "0")).split()[0])
        if not total:
            return "**Mem:** `n/a`"
        used = total - avail
        return (
            f"**Mem:** `{used / 1024:.0f} / {total / 1024:.0f} MiB` "
            f"({100 * used / total:.0f}% used)"
        )
    except Exception:
        return "**Mem:** `n/a`"


def _disk_line() -> str:
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        if not total:
            return "**Disk (/):** `n/a`"
        used = total - free
        return (
            f"**Disk (/):** `{used / 1e9:.1f} / {total / 1e9:.1f} GB` "
            f"({100 * used / total:.0f}% used)"
        )
    except Exception:
        return "**Disk (/):** `n/a`"


def _load_line() -> str:
    try:
        load1, load5, load15 = os.getloadavg()
        cores = os.cpu_count() or "?"
        return f"**Load:** `{load1:.2f} {load5:.2f} {load15:.2f}` ({cores} cores)"
    except Exception:
        return "**Load:** `n/a`"


def _ip_line() -> str:
    ips: List[str] = []
    try:
        import netifaces  # type: ignore

        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            for info in addrs.get(netifaces.AF_INET, []):
                ip = info.get("addr")
                if ip and not ip.startswith("127."):
                    ips.append(ip)
    except Exception:
        # stdlib fallback: UDP connect trick + hostname
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ips.append(s.getsockname()[0])
        except Exception:
            pass
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip and not ip.startswith("127.") and ip not in ips:
                    ips.append(ip)
        except Exception:
            pass
    if ips:
        # unique, stable order
        seen = []
        for ip in ips:
            if ip not in seen:
                seen.append(ip)
        return f"**LAN IP(s):** `{', '.join(seen[:4])}`"
    return "**LAN IP(s):** `n/a`"


def _last_log_lines(n: int = 3) -> str:
    """Last n non-empty lines from the newest chronos-*.log (if any)."""
    try:
        d = logs_dir()
        if not d.is_dir():
            return f"**Last log lines:** `_no log dir ({d})_`"
        files = sorted(d.glob("chronos-*.log"), reverse=True)
        if not files:
            return "**Last log lines:** `_none_`"
        text = files[0].read_text(encoding="utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        tail = lines[-n:] if lines else []
        if not tail:
            return "**Last log lines:** `_empty_`"
        # keep short for Discord
        clipped = []
        for ln in tail:
            if len(ln) > 160:
                ln = ln[:157] + "…"
            clipped.append(ln)
        body = "\n".join(f"`{ln}`" for ln in clipped)
        return f"**Last {len(clipped)} log line(s)** (`{files[0].name}`):\n{body}"
    except Exception as e:
        return f"**Last log lines:** `_error: {e}_`"


def gather_sysinfo() -> str:
    """
    Build a compact multi-line status string.
    Placeholders (`n/a`) when a sensor/path is missing — never raises.
    """
    parts = [
        "**Chronos sysinfo**",
        _hostname_line(),
        _uptime_line(),
        _temp_line(),
        _throttle_line(),
        _mem_line(),
        _disk_line(),
        _load_line(),
        _ip_line(),
        _last_log_lines(3),
    ]
    return "\n".join(parts)
