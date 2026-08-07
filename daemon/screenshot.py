"""
Take a screenshot; try several backends (Wayland/X11 friendly).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from shared.config import state_dir


def take_screenshot() -> tuple[bool, str, Path | None]:
    out_dir = state_dir() / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"shot-{int(time.time())}.png"

    # Prefer grim on Wayland (Bazzite), then spectacle, scrot, import
    candidates = []
    if shutil.which("grim"):
        candidates.append(["grim", str(out)])
    if shutil.which("spectacle"):
        candidates.append(["spectacle", "-b", "-n", "-o", str(out)])
    if shutil.which("scrot"):
        candidates.append(["scrot", str(out)])
    if shutil.which("import"):
        candidates.append(["import", "-window", "root", str(out)])

    if not candidates:
        return False, "No screenshot tool found (try: grim, spectacle, scrot)", None

    last_err = ""
    for cmd in candidates:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
                return True, f"ok via {cmd[0]}", out
            err = (r.stderr or b"").decode("utf-8", errors="replace").strip()
            last_err = err or f"{cmd[0]} exit {r.returncode}"
        except Exception as e:
            last_err = str(e)

    return False, last_err or "screenshot failed", None
