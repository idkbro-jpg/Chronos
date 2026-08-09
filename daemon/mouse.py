"""Mouse simulation helpers (accessibility)."""

from __future__ import annotations

import shutil
import subprocess
import time


def _run(cmd: list[str], timeout: float = 10) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            err = (r.stderr or b"").decode("utf-8", errors="replace").strip()
            return False, err or f"exit {r.returncode}"
        return True, ""
    except FileNotFoundError:
        return False, f"not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def simulate_mouse(spec: str) -> tuple[bool, str]:
    """
    Mouse simulation for accessibility.

    Examples:
      click
      click left
      click right
      move 100 200
    """
    spec = (spec or "").strip()
    if not spec:
        return False, "empty mouse spec (example: !mouse click  or  !mouse move 100 200)"

    parts = spec.split()
    action = parts[0].lower()
    time.sleep(0.3)
    errors: list[str] = []

    if action in ("click", "left", "right", "middle", "btn1", "btn2", "btn3"):
        button = "left"
        if action in ("right", "btn3"):
            button = "right"
        elif action in ("middle", "btn2"):
            button = "middle"
        elif action == "click" and len(parts) > 1:
            button = parts[1].lower()
            if button in ("1",):
                button = "left"
            elif button in ("2",):
                button = "middle"
            elif button in ("3",):
                button = "right"
            if button not in ("left", "right", "middle"):
                button = "left"

        if shutil.which("ydotool"):
            code = {"left": "0", "right": "1", "middle": "2"}.get(button, "0")
            ok, err = _run(["ydotool", "click", code])
            if ok:
                return True, f"click {button} via ydotool"
            errors.append(f"ydotool: {err}")

        if shutil.which("xdotool"):
            btn = {"left": "1", "middle": "2", "right": "3"}.get(button, "1")
            ok, err = _run(["xdotool", "click", btn])
            if ok:
                return True, f"click {button} via xdotool"
            errors.append(f"xdotool: {err}")

        return False, "; ".join(errors) or "no mouse tool (ydotool/xdotool)"

    if action in ("move", "mousemove", "moveto"):
        if len(parts) < 3:
            return False, "move needs x y (example: !mouse move 100 200)"
        try:
            x, y = int(parts[1]), int(parts[2])
        except ValueError:
            return False, "x and y must be integers"

        if shutil.which("ydotool"):
            ok, err = _run(["ydotool", "mousemove", "--absolute", "-x", str(x), "-y", str(y)])
            if not ok:
                ok, err = _run(["ydotool", "mousemove", str(x), str(y)])
            if ok:
                return True, f"move {x},{y} via ydotool"
            errors.append(f"ydotool: {err}")

        if shutil.which("xdotool"):
            ok, err = _run(["xdotool", "mousemove", "--sync", str(x), str(y)])
            if ok:
                return True, f"move {x},{y} via xdotool"
            errors.append(f"xdotool: {err}")

        return False, "; ".join(errors) or "no mouse tool"

    return False, f"unknown mouse action: {action} (use click|move)"
