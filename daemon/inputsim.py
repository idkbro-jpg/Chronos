"""
Simulate keyboard input (not a keylogger).

Only the explicit !input command is executed and logged.
Prefers Wayland tools (ydotool, wtype), falls back to xdotool.
"""

from __future__ import annotations

import shutil
import subprocess
import time

# Linux keycodes (evdev) for ydotool key CODE:1 / CODE:0
KEYCODES = {
    "esc": 1,
    "escape": 1,
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 6,
    "6": 7,
    "7": 8,
    "8": 9,
    "9": 10,
    "0": 11,
    "minus": 12,
    "-": 12,
    "equal": 13,
    "=": 13,
    "backspace": 14,
    "tab": 15,
    "q": 16,
    "w": 17,
    "e": 18,
    "r": 19,
    "t": 20,
    "y": 21,
    "u": 22,
    "i": 23,
    "o": 24,
    "p": 25,
    "leftbrace": 26,
    "[": 26,
    "rightbrace": 27,
    "]": 27,
    "enter": 28,
    "return": 28,
    "ctrl": 29,
    "control": 29,
    "leftctrl": 29,
    "a": 30,
    "s": 31,
    "d": 32,
    "f": 33,
    "g": 34,
    "h": 35,
    "j": 36,
    "k": 37,
    "l": 38,
    "semicolon": 39,
    ";": 39,
    "apostrophe": 40,
    "'": 40,
    "grave": 41,
    "`": 41,
    "shift": 42,
    "leftshift": 42,
    "backslash": 43,
    "\\": 43,
    "z": 44,
    "x": 45,
    "c": 46,
    "v": 47,
    "b": 48,
    "n": 49,
    "m": 50,
    "comma": 51,
    ",": 51,
    "dot": 52,
    ".": 52,
    "slash": 53,
    "/": 53,
    "rightshift": 54,
    "alt": 56,
    "leftalt": 56,
    "space": 57,
    "capslock": 58,
    "f1": 59,
    "f2": 60,
    "f3": 61,
    "f4": 62,
    "f5": 63,
    "f6": 64,
    "f7": 65,
    "f8": 66,
    "f9": 67,
    "f10": 68,
    "f11": 87,
    "f12": 88,
    "rightctrl": 97,
    "rightalt": 100,
    "home": 102,
    "up": 103,
    "pageup": 104,
    "left": 105,
    "right": 106,
    "end": 107,
    "down": 108,
    "pagedown": 109,
    "insert": 110,
    "delete": 111,
    "del": 111,
    "super": 125,
    "meta": 125,
    "win": 125,
    "leftmeta": 125,
    "rightmeta": 126,
}

MODIFIERS = {"ctrl", "control", "leftctrl", "rightctrl", "alt", "leftalt", "rightalt",
             "shift", "leftshift", "rightshift", "super", "meta", "win", "leftmeta", "rightmeta"}


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


def _parse_tokens(spec: str) -> tuple[str, list[str]]:
    """
    Returns (mode, tokens).
    mode = "text" | "keys"
    """
    spec = spec.strip()
    if not spec:
        return "keys", []

    low = spec.lower()
    if low.startswith("text:") or low.startswith("type:"):
        return "text", [spec.split(":", 1)[1]]
    if (spec.startswith('"') and spec.endswith('"')) or (spec.startswith("'") and spec.endswith("'")):
        return "text", [spec[1:-1]]

    return "keys", spec.split()


def _ydotool_keys(tokens: list[str]) -> tuple[bool, str]:
    if not shutil.which("ydotool"):
        return False, "ydotool not installed"

    mods = [t.lower() for t in tokens[:-1]] if len(tokens) > 1 else []
    main = tokens[-1].lower() if tokens else ""

    for m in mods:
        if m not in KEYCODES:
            return False, f"unknown key: {m}"
    if main not in KEYCODES:
        return False, f"unknown key: {main}"

    # press modifiers, press+release main, release modifiers
    sequence: list[str] = []
    for m in mods:
        sequence.append(f"{KEYCODES[m]}:1")
    sequence.append(f"{KEYCODES[main]}:1")
    sequence.append(f"{KEYCODES[main]}:0")
    for m in reversed(mods):
        sequence.append(f"{KEYCODES[m]}:0")

    return _run(["ydotool", "key", *sequence])


def _ydotool_type(text: str) -> tuple[bool, str]:
    if not shutil.which("ydotool"):
        return False, "ydotool not installed"
    return _run(["ydotool", "type", "--", text])


def _wtype_keys(tokens: list[str]) -> tuple[bool, str]:
    if not shutil.which("wtype"):
        return False, "wtype not installed"

    mods = [t.lower() for t in tokens[:-1]] if len(tokens) > 1 else []
    main = tokens[-1].lower() if tokens else ""

    # wtype -M alt -k p -m alt
    cmd = ["wtype"]
    for m in mods:
        name = "ctrl" if m in ("control", "leftctrl", "rightctrl") else m
        if name in ("leftshift", "rightshift"):
            name = "shift"
        if name in ("leftalt", "rightalt"):
            name = "alt"
        if name in ("super", "meta", "win", "leftmeta", "rightmeta"):
            name = "logo"
        cmd.extend(["-M", name])
    # single key
    if len(main) == 1 or main in ("enter", "return", "tab", "esc", "escape", "space",
                                    "up", "down", "left", "right", "backspace", "delete"):
        key = "Return" if main in ("enter", "return") else main
        if key == "escape":
            key = "Escape"
        cmd.extend(["-k", key.capitalize() if key in ("return",) else key])
    else:
        cmd.extend(["-k", main])
    for m in reversed(mods):
        name = "ctrl" if m in ("control", "leftctrl", "rightctrl") else m
        if name in ("leftshift", "rightshift"):
            name = "shift"
        if name in ("leftalt", "rightalt"):
            name = "alt"
        if name in ("super", "meta", "win", "leftmeta", "rightmeta"):
            name = "logo"
        cmd.extend(["-m", name])

    return _run(cmd)


def _wtype_type(text: str) -> tuple[bool, str]:
    if not shutil.which("wtype"):
        return False, "wtype not installed"
    return _run(["wtype", "--", text])


def _xdotool_keys(tokens: list[str]) -> tuple[bool, str]:
    if not shutil.which("xdotool"):
        return False, "xdotool not installed"
    # alt p → alt+p
    parts = [t.lower() for t in tokens]
    for i, p in enumerate(parts):
        if p in ("control", "leftctrl", "rightctrl"):
            parts[i] = "ctrl"
        if p in ("super", "meta", "win"):
            parts[i] = "super"
    chord = "+".join(parts)
    return _run(["xdotool", "key", chord])


def _xdotool_type(text: str) -> tuple[bool, str]:
    if not shutil.which("xdotool"):
        return False, "xdotool not installed"
    return _run(["xdotool", "type", "--", text])


def simulate_input(spec: str) -> tuple[bool, str]:
    """
    Execute a keyboard simulation request.

    Examples:
      alt p
      ctrl c
      enter
      text:hello world
      "hello"
    """
    mode, data = _parse_tokens(spec)
    if mode == "keys" and not data:
        return False, "empty input (example: !input alt p)"

    # Small delay so focus can settle after approval click
    time.sleep(0.3)

    errors: list[str] = []

    if mode == "text":
        text = data[0]
        for fn in (_ydotool_type, _wtype_type, _xdotool_type):
            ok, err = fn(text)
            if ok:
                return True, f"typed {len(text)} chars via {fn.__name__}"
            errors.append(f"{fn.__name__}: {err}")
        return False, "; ".join(errors)

    for fn in (_ydotool_keys, _wtype_keys, _xdotool_keys):
        ok, err = fn(data)
        if ok:
            return True, f"keys {'+'.join(t.lower() for t in data)} via {fn.__name__}"
        errors.append(f"{fn.__name__}: {err}")

    return False, "; ".join(errors) + (
        " — install ydotool (Wayland) or xdotool (X11)"
    )
