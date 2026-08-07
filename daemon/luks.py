"""
LUKS unlock helpers.

Password is stored encrypted at rest.
Key material = SHA256(bot_token + machine_secret) → Fernet key.

The password is only held in memory for the cryptsetup call.
"""

from __future__ import annotations

import os
import secrets
import subprocess
from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from shared.config import (
    discord_token,
    luks_device,
    luks_mapper_name,
    luks_password_file,
    luks_machine_secret_file,
    luks_post_unlock_command,
    luks_enabled,
)


def _derive_fernet_key(token: str, machine_secret: bytes) -> bytes:
    digest = sha256(token.encode("utf-8") + b"|" + machine_secret).digest()
    return urlsafe_b64encode(digest)


def ensure_machine_secret(path: Path | None = None) -> bytes:
    path = path or luks_machine_secret_file()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.exists():
        data = path.read_bytes()
        if len(data) < 16:
            raise ValueError(f"machine secret too short: {path}")
        return data

    data = secrets.token_bytes(32)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    return data


def encrypt_password(plaintext: str) -> None:
    """Encrypt LUKS password and write to password_file."""
    token = discord_token()
    machine = ensure_machine_secret()
    f = Fernet(_derive_fernet_key(token, machine))

    out = luks_password_file()
    out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    out.write_bytes(f.encrypt(plaintext.encode("utf-8")))
    os.chmod(out, 0o600)


def decrypt_password() -> str:
    path = luks_password_file()
    if not path.exists():
        raise FileNotFoundError(
            f"No encrypted password at {path}. Run: python -m scripts.set_luks_password"
        )

    token = discord_token()
    machine = ensure_machine_secret()
    f = Fernet(_derive_fernet_key(token, machine))

    try:
        return f.decrypt(path.read_bytes()).decode("utf-8")
    except InvalidToken as e:
        raise ValueError(
            "Cannot decrypt LUKS password (wrong token/machine secret or corrupt file)"
        ) from e


def is_already_unlocked(mapper_name: str | None = None) -> bool:
    name = mapper_name or luks_mapper_name()
    return Path(f"/dev/mapper/{name}").exists()


def unlock_luks() -> tuple[bool, str]:
    """
    Unlock configured LUKS device.
    Returns (success, message). Never includes the password in message.
    """
    if not luks_enabled():
        return False, "LUKS unlock is disabled in config.yml (luks.enabled: false)"

    device = luks_device()
    mapper = luks_mapper_name()

    if not device or device == "/dev/sdX":
        return False, "luks.device is not configured in config.yml"

    if is_already_unlocked(mapper):
        return True, f"Already unlocked: /dev/mapper/{mapper}"

    if not Path(device).exists():
        return False, f"Device not found: {device}"

    try:
        password = decrypt_password()
    except Exception as e:
        return False, f"Password load failed: {e}"

    try:
        proc = subprocess.run(
            [
                "cryptsetup",
                "luksOpen",
                device,
                mapper,
                "--key-file=-",
            ],
            input=password.encode("utf-8"),
            capture_output=True,
            timeout=60,
        )
    finally:
        # Best-effort wipe of local reference
        password = ""  # noqa: F841

    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        # Never echo anything that might contain secrets; cryptsetup is usually safe
        if not err:
            err = f"cryptsetup exited with code {proc.returncode}"
        return False, f"Unlock failed: {err}"

    msg = f"Unlocked → /dev/mapper/{mapper}"

    post = luks_post_unlock_command()
    if post:
        post_proc = subprocess.run(
            post,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            timeout=120,
        )
        if post_proc.returncode != 0:
            err = (post_proc.stderr or b"").decode("utf-8", errors="replace").strip()
            return False, f"{msg} — but post_unlock_command failed: {err or post_proc.returncode}"
        out = (post_proc.stdout or b"").decode("utf-8", errors="replace").strip()
        if out:
            msg = f"{msg}\nPost: {out[:500]}"

    return True, msg
