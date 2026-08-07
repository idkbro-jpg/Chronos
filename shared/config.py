"""
Zentrale Config-Ladung: config.yml + .env (Secrets).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.yml"

load_dotenv(ROOT / ".env")

_cfg: dict[str, Any] = {}
_loaded = False


def _defaults() -> dict[str, Any]:
    return {
        "discord": {
            "command_prefix": "!",
            "allowed_user_ids": [],
        },
        "approval": {
            "timeout_seconds": 60,
            "approve_emoji": "✅",
            "deny_emoji": "❌",
            "allowed_user_ids": [],
        },
        "execution": {
            "timeout_seconds": 300,
            "use_shell": True,
            "max_output_chars": 1800,
            "strip_ansi": True,
        },
        "files": {
            "aliases": "aliases.yml",
        },
        "luks": {
            "enabled": False,
            "device": "/dev/sdX",
            "mapper_name": "crypt_data",
            "password_file": "secrets/luks.enc",
            "machine_secret_file": "secrets/machine.key",
            "post_unlock_command": "",
        },
    }


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(force: bool = False) -> dict[str, Any]:
    global _cfg, _loaded
    if _loaded and not force:
        return _cfg

    cfg = _defaults()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                cfg = _deep_merge(cfg, data)
            print(f"[Config] Loaded {CONFIG_FILE}")
        except Exception as e:
            print(f"[Config] Failed to load config.yml: {e} – using defaults")
    else:
        print(f"[Config] No config.yml at {CONFIG_FILE} – using defaults")

    _cfg = cfg
    _loaded = True
    return _cfg


def get() -> dict[str, Any]:
    return load_config()


def discord_token() -> str:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError("DISCORD_TOKEN missing in .env")
    return token


def command_channel_id() -> int:
    raw = os.getenv("COMMAND_CHANNEL_ID", "0").strip()
    try:
        cid = int(raw)
    except ValueError:
        cid = 0
    if cid == 0:
        raise ValueError("COMMAND_CHANNEL_ID missing or invalid in .env")
    return cid


def command_prefix() -> str:
    return str(get()["discord"].get("command_prefix") or "!")


def allowed_command_user_ids() -> list[int]:
    ids = get()["discord"].get("allowed_user_ids") or []
    return [int(x) for x in ids]


def approval_timeout() -> int:
    return int(get()["approval"].get("timeout_seconds") or 60)


def approve_emoji() -> str:
    return str(get()["approval"].get("approve_emoji") or "✅")


def deny_emoji() -> str:
    return str(get()["approval"].get("deny_emoji") or "❌")


def allowed_approval_user_ids() -> list[int]:
    ids = get()["approval"].get("allowed_user_ids") or []
    return [int(x) for x in ids]


def exec_timeout() -> int:
    return int(get()["execution"].get("timeout_seconds") or 300)


def use_shell() -> bool:
    return bool(get()["execution"].get("use_shell", True))


def max_output_chars() -> int:
    return int(get()["execution"].get("max_output_chars") or 1800)


def strip_ansi() -> bool:
    return bool(get()["execution"].get("strip_ansi", True))


def aliases_path() -> Path:
    name = get()["files"].get("aliases") or "aliases.yml"
    p = Path(name)
    if not p.is_absolute():
        p = ROOT / p
    return p


def _resolve_path(value: str) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    return p


def luks_enabled() -> bool:
    return bool(get().get("luks", {}).get("enabled", False))


def luks_device() -> str:
    return str(get().get("luks", {}).get("device") or "")


def luks_mapper_name() -> str:
    return str(get().get("luks", {}).get("mapper_name") or "crypt_data")


def luks_password_file() -> Path:
    return _resolve_path(str(get().get("luks", {}).get("password_file") or "secrets/luks.enc"))


def luks_machine_secret_file() -> Path:
    return _resolve_path(
        str(get().get("luks", {}).get("machine_secret_file") or "secrets/machine.key")
    )


def luks_post_unlock_command() -> str:
    return str(get().get("luks", {}).get("post_unlock_command") or "").strip()
