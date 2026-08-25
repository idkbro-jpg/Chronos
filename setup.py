#!/usr/bin/env python3
"""
Chronos interactive setup.

    python setup.py

Creates/updates .env, config.yml, lock password, optional systemd user unit.
Optionally creates a venv and installs requirements.txt.
"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        print("  (required)")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{d}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  type y or n")


def ask_int(prompt: str, default: int, minimum: int = 1, maximum: int = 86400) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            v = int(raw)
        except ValueError:
            print("  need an integer")
            continue
        if minimum <= v <= maximum:
            return v
        print(f"  range {minimum}..{maximum}")


def ask_ids(prompt: str) -> list[int]:
    raw = ask(prompt + " (comma-separated, empty = none)", "")
    if not raw:
        return []
    out: list[int] = []
    for part in re.split(r"[,\s]+", raw):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            print(f"  skip invalid id: {part!r}")
    return out


def write_env(token: str, channel_id: str) -> None:
    path = ROOT / ".env"
    path.write_text(
        textwrap.dedent(
            f"""\
            # Secrets only — everything else is in config.yml
            DISCORD_TOKEN={token}
            COMMAND_CHANNEL_ID={channel_id}
            """
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(f"  wrote {path}")


def write_config(
    *,
    prefix: str,
    whitelist: bool,
    allowed_users: list[int],
    audit_channel: int,
    approve_timeout: int,
    approval_users: list[int],
    exec_timeout: int,
    exec_mode: str,
    rate_enabled: bool,
    rate_max: int,
    rate_window: int,
    alarm_blocks: bool,
) -> None:
    users_yml = "\n".join(f"    - {i}" for i in allowed_users) if allowed_users else "    []"
    if allowed_users:
        users_block = "allowed_user_ids:\n" + users_yml
    else:
        users_block = "allowed_user_ids: []"

    appr_yml = "\n".join(f"    - {i}" for i in approval_users) if approval_users else ""
    if approval_users:
        appr_block = "allowed_user_ids:\n" + appr_yml
    else:
        appr_block = "allowed_user_ids: []  # empty = any non-bot may approve"

    text = f"""# Chronos configuration
# Secrets → .env + secrets/
# After changes: !reload  or  systemctl --user restart chronos-daemon

discord:
  # Bot command prefix. Do NOT use "?" — reserved by Android Receiver (?status / ?ping).
  command_prefix: "{prefix}"

  # SECURITY: if false, anyone who can post in the command channel can propose
  # shell commands (still needs approval unless sudomode is on).
  whitelist_enabled: {"true" if whitelist else "false"}
  {users_block}

  # Optional: mirror critical events here. 0 = off.
  audit_channel_id: {audit_channel}

approval:
  timeout_seconds: {approve_timeout}
  approve_emoji: "\u2705"
  deny_emoji: "\u274c"
  {appr_block}

execution:
  timeout_seconds: {exec_timeout}
  use_shell: true
  max_output_chars: 1800
  strip_ansi: true
  # unrestricted | allowlist
  mode: {exec_mode}
  allowed_patterns: []

rate_limit:
  enabled: {"true" if rate_enabled else "false"}
  max_commands: {rate_max}
  window_seconds: {rate_window}
  trigger_alarm: true

security:
  state_dir: "state"
  lock_hash_file: "secrets/lock.hash"
  alarm_blocks_all: {"true" if alarm_blocks else "false"}

logging:
  enabled: true
  dir: "logs"
  also_log_denied: true

history:
  enabled: true
  max_entries: 30

files:
  aliases: aliases.yml

luks:
  enabled: false
  device: "/dev/sdX"
  mapper_name: "crypt_data"
  password_file: "secrets/luks.enc"
  machine_secret_file: "secrets/machine.key"
  post_unlock_command: ""
"""
    path = ROOT / "config.yml"
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path}")


def set_master_password() -> None:
    from daemon.security import save_lock_password
    from shared.config import load_config

    load_config(force=True)
    print()
    print("Master lock password (used for unlock + sudomode via DM).")
    print("Store it in a password manager. It is never saved as plaintext.")
    while True:
        pw1 = getpass.getpass("  password: ")
        pw2 = getpass.getpass("  repeat:   ")
        if pw1 != pw2:
            print("  mismatch, try again")
            continue
        if len(pw1) < 12:
            print("  use at least 12 characters")
            continue
        path = save_lock_password(pw1)
        print(f"  hash saved → {path}")
        return


def write_systemd_unit(python_path: str) -> None:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit = unit_dir / "chronos-daemon.service"
    unit.write_text(
        textwrap.dedent(
            f"""\
            [Unit]
            Description=Chronos Discord command daemon
            After=network-online.target
            Wants=network-online.target

            [Service]
            Type=simple
            WorkingDirectory={ROOT}
            ExecStart={python_path} -m daemon.main
            Restart=on-failure
            RestartSec=5
            Environment=PYTHONUNBUFFERED=1

            [Install]
            WantedBy=default.target
            """
        ),
        encoding="utf-8",
    )
    print(f"  wrote {unit}")
    print("  enable with:")
    print("    systemctl --user daemon-reload")
    print("    systemctl --user enable --now chronos-daemon.service")


def ensure_venv_and_deps() -> str:
    """Optionally create venv + pip install. Returns python path to use for systemd."""
    venv_dir = ROOT / "venv"
    venv_python = venv_dir / "bin" / "python"
    req = ROOT / "requirements.txt"

    if not ask_yes_no("Create/use a local venv and install requirements.txt?", True):
        return str(venv_python) if venv_python.is_file() else sys.executable

    if not venv_python.is_file():
        print("  creating venv…")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, cwd=ROOT)

    py = str(venv_python)
    if req.is_file():
        print("  pip install -r requirements.txt …")
        subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=False, cwd=ROOT)
        r = subprocess.run([py, "-m", "pip", "install", "-r", str(req)], cwd=ROOT)
        if r.returncode != 0:
            print("  pip install failed — fix network/permissions, then re-run setup or:")
            print(f"    {py} -m pip install -r requirements.txt")
        else:
            print("  dependencies OK")
    else:
        print("  no requirements.txt found — skip pip")

    return py


def defaults() -> None:
    """Keep existing files; only ensure minimal structure."""
    print("Using existing files where present (skip full wizard).")
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "secrets").mkdir(exist_ok=True)
    if not (ROOT / ".env").exists() and (ROOT / ".env.example").exists():
        print("  no .env yet — copy from .env.example and fill token + channel id")
    print("Done (minimal).")


def wizard() -> None:
    print()
    print("=== Chronos setup wizard ===")
    print(f"Project root: {ROOT}")
    print()

    confirm = ask("Install / config directory (must be this repo)", str(ROOT))
    if Path(confirm).resolve() != ROOT:
        print("  Note: setup always writes into the repo that contains setup.py.")
        print(f"  Continuing with {ROOT}")

    # Dependencies first so later imports (lock password) work
    python_path = ensure_venv_and_deps()

    prefix = ask("Command prefix (do NOT use '?' — reserved by Android Receiver)", "!")
    if not prefix:
        prefix = "!"
    if prefix.strip() == "?":
        print("  '?' is used by the Receiver for ?status / ?ping — switching to '!' ")
        prefix = "!"

    whitelist = ask_yes_no("Enable command whitelist? (recommended for real use)", True)
    allowed_users: list[int] = []
    if whitelist:
        print("  Discord user IDs allowed to propose commands.")
        print("  (Developer Mode → right-click your user → Copy User ID)")
        allowed_users = ask_ids("  allowed user ids")

    approval_users = ask_ids("Approval user ids (who may react ✅; empty = anyone)")

    token = ask("Discord bot token")
    channel = ask("Command channel ID")
    audit_raw = ask("Audit channel ID (0 = off)", "0")
    try:
        audit_channel = int(audit_raw)
    except ValueError:
        audit_channel = 0

    approve_timeout = ask_int("Approval timeout (seconds)", 60, 10, 600)
    exec_timeout = ask_int("Command execution timeout (seconds)", 300, 10, 3600)

    mode = ask("Execution mode: unrestricted / allowlist", "unrestricted").lower()
    if mode not in ("unrestricted", "allowlist"):
        mode = "unrestricted"

    rate_enabled = ask_yes_no("Enable rate limit?", True)
    rate_max = ask_int("Rate limit max commands", 20, 1, 1000)
    rate_window = ask_int("Rate limit window (seconds)", 60, 5, 3600)
    alarm_blocks = ask_yes_no("Alarm blocks all commands until unlock?", True)

    print()
    print("Writing files…")
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "secrets").mkdir(mode=0o700, exist_ok=True)

    write_env(token, channel)
    write_config(
        prefix=prefix,
        whitelist=whitelist,
        allowed_users=allowed_users,
        audit_channel=audit_channel,
        approve_timeout=approve_timeout,
        approval_users=approval_users,
        exec_timeout=exec_timeout,
        exec_mode=mode,
        rate_enabled=rate_enabled,
        rate_max=rate_max,
        rate_window=rate_window,
        alarm_blocks=alarm_blocks,
    )

    if ask_yes_no("Set master lock password now?", True):
        try:
            set_master_password()
        except Exception as e:
            print(f"  could not set password yet ({e})")
            print("  later: python -m scripts.set_lock_password")
            print(f"  (use the venv python if you created one: {python_path} -m scripts.set_lock_password)")

    if ask_yes_no("Write systemd user unit chronos-daemon.service?", True):
        write_systemd_unit(python_path)

    print()
    print("=== Next steps ===")
    print("1. Discord Developer Portal → Bot → enable MESSAGE CONTENT INTENT")
    print("2. Invite bot with: Send Messages, Read Message History, Add Reactions")
    print("3. systemctl --user enable --now chronos-daemon.service")
    print("4. journalctl --user -u chronos-daemon.service -f")
    print()
    print("Android APKs (optional): https://github.com/idkbro-jpg/Chronos/releases")
    print("Update later: python update.py")
    print()
    print("Done.")


def main() -> int:
    os.chdir(ROOT)
    print("Chronos setup")
    print()
    skip = ask_yes_no(
        "Skip everything and use normal/existing settings?\n"
        "  (not recommended if you use it for the first time)",
        False,
    )
    if skip:
        defaults()
        return 0
    wizard()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
