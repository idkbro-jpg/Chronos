"""
Command executor.
"""

from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
from typing import Tuple

from shared.config import exec_timeout, use_shell, strip_ansi

_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean(text: str) -> str:
    if not text:
        return ""
    if strip_ansi():
        text = _ANSI_RE.sub("", text)
    return text


def _safe_decode(data: bytes | None) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def _kill_process_group(proc: subprocess.Popen) -> None:
    """Best-effort terminate of the whole process group (shell + children)."""
    if proc.pid is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=2)
    except Exception:
        pass


def run_command(command: str, timeout: int | None = None) -> Tuple[int, str, str]:
    """
    Execute a command and return (returncode, stdout, stderr).

    Uses a new process session so that on timeout we can kill the whole
    process group (important for shell=True pipelines / background children).
    """
    if timeout is None:
        timeout = exec_timeout()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = env.get("TERM") or "dumb"

    try:
        if use_shell():
            # Needed for &&, pipes, $(), redirects in aliases
            proc = subprocess.Popen(
                command,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
        else:
            try:
                args = shlex.split(command)
            except ValueError as e:
                return 1, "", f"Failed to parse command: {e}"
            if not args:
                return 1, "", "Empty command"
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )

        try:
            stdout_b, stderr_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            try:
                stdout_b, stderr_b = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                stdout_b, stderr_b = b"", b""
            return 1, _clean(_safe_decode(stdout_b)), (
                f"Command timed out after {timeout} seconds"
            )

        stdout = _clean(_safe_decode(stdout_b))
        stderr = _clean(_safe_decode(stderr_b))
        return proc.returncode if proc.returncode is not None else 1, stdout, stderr

    except FileNotFoundError as e:
        return 1, "", f"Command not found: {e.filename or command.split()[0]}"
    except Exception as e:
        return 1, "", f"Execution error: {e}"
