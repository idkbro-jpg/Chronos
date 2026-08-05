"""
Command executor.
"""

from __future__ import annotations

import os
import re
import shlex
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


def run_command(command: str, timeout: int | None = None) -> Tuple[int, str, str]:
    """
    Execute a command and return (returncode, stdout, stderr).
    """
    if timeout is None:
        timeout = exec_timeout()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = env.get("TERM") or "dumb"

    try:
        if use_shell():
            # Needed for &&, pipes, $(), redirects in aliases
            result = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                timeout=timeout,
                env=env,
            )
        else:
            try:
                args = shlex.split(command)
            except ValueError as e:
                return 1, "", f"Failed to parse command: {e}"
            if not args:
                return 1, "", "Empty command"
            result = subprocess.run(
                args,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout} seconds"
    except FileNotFoundError as e:
        return 1, "", f"Command not found: {e.filename or command.split()[0]}"
    except Exception as e:
        return 1, "", f"Execution error: {e}"

    def safe_decode(data: bytes) -> str:
        if not data:
            return ""
        return data.decode("utf-8", errors="replace")

    stdout = _clean(safe_decode(result.stdout))
    stderr = _clean(safe_decode(result.stderr))
    return result.returncode, stdout, stderr
