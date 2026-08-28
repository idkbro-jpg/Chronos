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
            "whitelist_enabled": False,
            "allowed_user_ids": [],
            "audit_channel_id": 0,
        },
        "approval": {
            "timeout_seconds": 60,
            "approve_emoji": "\u2705",
            "deny_emoji": "\u274c",
            "allowed_user_ids": [],
        },
        "execution": {
            "timeout_seconds": 300,
            "use_shell": True,
            "max_output_chars": 1800,
            "strip_ansi": True,
            "mode": "unrestricted",
            "allowed_patterns": [],
        },
        "rate_limit": {
            "enabled": True,
            "max_commands": 20,
            "window_seconds": 60,
            "trigger_alarm": True,
        },
        "security": {
            "state_dir": "state",
            "lock_hash_file": "secrets/lock.hash",
            "alarm_blocks_all": True,
        },
        "logging": {
            "enabled": True,
            "dir": "logs",
            "also_log_denied": True,
        },
        "history": {
            "enabled": True,
            "max_entries": 30,
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


def _validate(cfg: dict[str, Any]) -> None:
    try:
        disc = cfg.get("discord") or {}
        if disc.get("whitelist_enabled") and not (disc.get("allowed_user_ids") or []):
            print("[Config] WARNING: whitelist_enabled=true but allowed_user_ids is empty → all users denied")
        if not disc.get("whitelist_enabled"):
            print(
                "[Config] ⚠️  SECURITY WARNING: whitelist is OFF. "
                "Anyone who can post in the command channel can propose shell commands "
                "on this machine (after reaction approval). "
                "Set discord.whitelist_enabled: true and list your Discord user id(s)."
            )
        prefix = str(disc.get("command_prefix") or "").strip()
        if not prefix:
            print("[Config] WARNING: discord.command_prefix is empty → falling back to '!' at runtime")
        elif prefix == "?":
            print(
                "[Config] WARNING: command_prefix '?' collides with Android Receiver local commands "
                "(?status, ?ping). Prefer '!' or another non-? prefix."
            )
        approval = cfg.get("approval") or {}
        if not (approval.get("allowed_user_ids") or []):
            print(
                "[Config] NOTE: approval.allowed_user_ids is empty → "
                "any non-bot user can approve/deny reactions."
            )
        luks = cfg.get("luks") or {}
        if luks.get("enabled"):
            dev = str(luks.get("device") or "")
            if not dev or dev == "/dev/sdX":
                print("[Config] WARNING: luks.enabled=true but device is still the placeholder /dev/sdX")
        exec_cfg = cfg.get("execution") or {}
        mode = str(exec_cfg.get("mode") or "unrestricted").lower()
        if mode not in ("unrestricted", "allowlist"):
            print(f"[Config] WARNING: unknown execution.mode={mode!r} – treating as unrestricted")
        if mode == "allowlist" and not (exec_cfg.get("allowed_patterns") or []):
            print("[Config] WARNING: execution.mode=allowlist but allowed_patterns is empty")
        for key, section in (
            ("timeout_seconds", "approval"),
            ("timeout_seconds", "execution"),
            ("max_commands", "rate_limit"),
            ("window_seconds", "rate_limit"),
            ("max_output_chars", "execution"),
        ):
            sec = cfg.get(section) or {}
            val = sec.get(key)
            if val is not None:
                try:
                    if int(val) <= 0:
                        print(f"[Config] WARNING: {section}.{key}={val} should be > 0")
                except (TypeError, ValueError):
                    print(f"[Config] WARNING: {section}.{key}={val!r} is not an integer")
    except Exception:
        pass


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
    _validate(cfg)
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
    raw = str(get()["discord"].get("command_prefix") or "").strip()
    # Empty prefix would make every message a command — refuse and use default.
    return raw if raw else "!"


def whitelist_enabled() -> bool:
    return bool(get()["discord"].get("whitelist_enabled", False))


def _parse_id_list(raw: list | None) -> list[int]:
    """Best-effort int conversion; skip invalid entries instead of raising."""
    out: list[int] = []
    for x in raw or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _parse_int(value: Any, default: int) -> int:
    """Best-effort int conversion; return default on invalid values."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_positive_int(value: Any, default: int) -> int:
    """Like _parse_int, but treat 0 / negative as invalid (use default)."""
    n = _parse_int(value, default)
    return n if n > 0 else default


def allowed_command_user_ids() -> list[int]:
    return _parse_id_list(get()["discord"].get("allowed_user_ids"))


def audit_channel_id() -> int:
    return _parse_int(get()["discord"].get("audit_channel_id"), 0)


def approval_timeout() -> int:
    return _parse_positive_int(get()["approval"].get("timeout_seconds"), 60)


def approve_emoji() -> str:
    return str(get()["approval"].get("approve_emoji") or "\u2705")


def deny_emoji() -> str:
    return str(get()["approval"].get("deny_emoji") or "\u274c")


def allowed_approval_user_ids() -> list[int]:
    return _parse_id_list(get()["approval"].get("allowed_user_ids"))


def exec_timeout() -> int:
    return _parse_positive_int(get()["execution"].get("timeout_seconds"), 300)


def use_shell() -> bool:
    return bool(get()["execution"].get("use_shell", True))


def max_output_chars() -> int:
    return _parse_positive_int(get()["execution"].get("max_output_chars"), 1800)


def strip_ansi() -> bool:
    return bool(get()["execution"].get("strip_ansi", True))


def execution_mode() -> str:
    mode = str(get()["execution"].get("mode") or "unrestricted").lower().strip()
    if mode not in ("unrestricted", "allowlist"):
        return "unrestricted"
    return mode


def allowed_patterns() -> list[str]:
    pats = get()["execution"].get("allowed_patterns") or []
    return [str(p) for p in pats if p]


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


def rate_limit_enabled() -> bool:
    return bool(get().get("rate_limit", {}).get("enabled", True))


def rate_limit_max() -> int:
    return _parse_positive_int(get().get("rate_limit", {}).get("max_commands"), 20)


def rate_limit_window() -> int:
    return _parse_positive_int(get().get("rate_limit", {}).get("window_seconds"), 60)


def rate_limit_triggers_alarm() -> bool:
    return bool(get().get("rate_limit", {}).get("trigger_alarm", True))


def state_dir() -> Path:
    return _resolve_path(str(get().get("security", {}).get("state_dir") or "state"))


def lock_hash_file() -> Path:
    return _resolve_path(str(get().get("security", {}).get("lock_hash_file") or "secrets/lock.hash"))


def alarm_blocks_all() -> bool:
    return bool(get().get("security", {}).get("alarm_blocks_all", True))


def logging_enabled() -> bool:
    return bool(get().get("logging", {}).get("enabled", True))


def logs_dir() -> Path:
    return _resolve_path(str(get().get("logging", {}).get("dir") or "logs"))


def log_denied() -> bool:
    return bool(get().get("logging", {}).get("also_log_denied", True))


def history_enabled() -> bool:
    return bool(get().get("history", {}).get("enabled", True))


def history_max_entries() -> int:
    return _parse_positive_int(get().get("history", {}).get("max_entries"), 30)


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
