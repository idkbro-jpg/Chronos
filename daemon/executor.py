"""
Command executor.

Designed to handle normal text output and be reasonably robust
with binary / weird output (we still try to decode as utf-8 with replacement).
"""

import subprocess
import shlex
from typing import Tuple

def run_command(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    """
    Execute a shell command and return (returncode, stdout, stderr).

    We use shell=False + shlex.split for better safety.
    For complex pipes/redirections the user can still do:
        !cmd bash -c 'your complex command'
    """
    try:
        args = shlex.split(command)
    except ValueError as e:
        return 1, "", f"Failed to parse command: {e}"

    if not args:
        return 1, "", "Empty command"

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            # text=False so we can handle binary-ish output more gracefully
        )
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        return 1, "", f"Command not found: {args[0]}"
    except Exception as e:
        return 1, "", f"Execution error: {e}"

    def safe_decode(data: bytes) -> str:
        if not data:
            return ""
        # Try utf-8, fall back to replacement so binary doesn't crash us
        return data.decode("utf-8", errors="replace")

    stdout = safe_decode(result.stdout)
    stderr = safe_decode(result.stderr)

    return result.returncode, stdout, stderr
