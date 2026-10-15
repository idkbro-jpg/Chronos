"""
Chronos permission system (redesign).

Design goals:
- Everything namespaced: chronos:… / bash:… / alias:…
- Only Discord user IDs
- File is re-read on every check (no long-lived cache)
- No entry = deny (multiple walls)
- Broken / missing YAML → Safe-Mode (only super_owner_id keeps rights)
- Writing only allowed for super_owner_id + anyone with rank owner
- Rank + extra + deny model
- needs_approval is a separate boolean

Source of truth: permissions.yml  (see permissions.example.yml)
"""

from __future__ import annotations

import os
import time
from typing import Any

import yaml

from shared.config import ROOT

PERMISSIONS_FILE = ROOT / "permissions.yml"

# Absolute last-resort ID if even the YAML super_owner_id cannot be read.
# Override via env CHRONOS_SUPER_OWNER_ID if you want.
_FALLBACK_SUPER_OWNER = os.environ.get("CHRONOS_SUPER_OWNER_ID", "1528851082288169061")


def _empty_safe() -> dict[str, Any]:
    """Minimal config used in Safe-Mode."""
    return {
        "super_owner_id": str(_FALLBACK_SUPER_OWNER),
        "presets": {
            "owner": {
                "needs_approval": False,
                "permissions": ["chronos:*", "alias:*", "bash:*"],
            }
        },
        "users": {
            str(_FALLBACK_SUPER_OWNER): {
                "rank": "owner",
                "needs_approval": False,
            }
        },
        "_safe_mode": True,
    }


def _load_raw() -> dict[str, Any]:
    """
    Always re-read the file from disk.
    On any failure → Safe-Mode.
    """
    if not PERMISSIONS_FILE.exists():
        print(f"[Permissions] No {PERMISSIONS_FILE} – Safe-Mode")
        return _empty_safe()

    try:
        with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print("[Permissions] YAML root is not a mapping – Safe-Mode")
            return _empty_safe()

        super_id = str(data.get("super_owner_id") or _FALLBACK_SUPER_OWNER).strip()
        presets = data.get("presets") if isinstance(data.get("presets"), dict) else {}
        users = data.get("users") if isinstance(data.get("users"), dict) else {}

        if super_id not in users:
            users[super_id] = {"rank": "owner", "needs_approval": False}

        if "owner" not in presets:
            presets["owner"] = {
                "needs_approval": False,
                "permissions": ["chronos:*", "alias:*", "bash:*"],
            }

        return {
            "super_owner_id": super_id,
            "presets": presets,
            "users": users,
            "_safe_mode": False,
        }
    except Exception as e:
        print(f"[Permissions] Failed to load permissions.yml: {e} – Safe-Mode")
        return _empty_safe()


def is_safe_mode() -> bool:
    return bool(_load_raw().get("_safe_mode"))


def super_owner_id() -> str:
    return str(_load_raw().get("super_owner_id") or _FALLBACK_SUPER_OWNER)


def _normalize_perm(p: str) -> str:
    return str(p).strip().lower()


def _expand_permissions(raw_list: list[Any]) -> set[str]:
    out: set[str] = set()
    for item in raw_list or []:
        if item is None:
            continue
        out.add(_normalize_perm(item))
    return out


def _resolve_permissions(user_id: int | str) -> set[str]:
    """Final effective permission set: rank → + extra → − deny."""
    cfg = _load_raw()
    uid = str(user_id)

    if uid == str(cfg.get("super_owner_id")):
        return {"chronos:*", "alias:*", "bash:*"}

    entry = (cfg.get("users") or {}).get(uid)
    if not entry or not isinstance(entry, dict):
        return set()

    presets = cfg.get("presets") or {}
    rank_name = entry.get("rank")
    rank = presets.get(rank_name) if rank_name else None

    perms: set[str] = set()
    if isinstance(rank, dict):
        perms |= _expand_permissions(rank.get("permissions") or [])

    perms |= _expand_permissions(entry.get("extra") or [])

    for d in _expand_permissions(entry.get("deny") or []):
        perms.discard(d)

    return perms


def _matches(have: set[str], needed: str) -> bool:
    needed = _normalize_perm(needed)
    if not needed:
        return False

    if needed in have:
        return True

    if "chronos:*" in have and needed.startswith("chronos:"):
        return True
    if "alias:*" in have and needed.startswith("alias:"):
        return True
    if "bash:*" in have and needed.startswith("bash:"):
        return True

    for held in have:
        if held.endswith("*") and not held.endswith(":*"):
            prefix = held[:-1]
            if needed.startswith(prefix):
                return True

    return False


def has_permission(user_id: int | str, permission: str) -> bool:
    """
    Check a single namespaced permission.

    Examples:
        has_permission(uid, "chronos:screenshot")
        has_permission(uid, "bash:ls")
        has_permission(uid, "alias:uptime")
        has_permission(uid, "bash:*")
    """
    if user_id is None or permission is None:
        return False
    if not str(user_id).strip():
        return False

    have = _resolve_permissions(user_id)
    if not have:
        return False
    return _matches(have, permission)


def needs_approval(user_id: int | str) -> bool:
    """Separate boolean. Missing entry → True (safe)."""
    cfg = _load_raw()
    uid = str(user_id)

    if uid == str(cfg.get("super_owner_id")):
        return False

    entry = (cfg.get("users") or {}).get(uid)
    if not entry or not isinstance(entry, dict):
        return True

    if "needs_approval" in entry:
        return bool(entry["needs_approval"])

    rank_name = entry.get("rank")
    rank = (cfg.get("presets") or {}).get(rank_name) if rank_name else None
    if isinstance(rank, dict) and "needs_approval" in rank:
        return bool(rank["needs_approval"])

    return True


def can_write_permissions(user_id: int | str) -> bool:
    """Only super-owner and rank owner may write."""
    cfg = _load_raw()
    uid = str(user_id)

    if uid == str(cfg.get("super_owner_id")):
        return True

    entry = (cfg.get("users") or {}).get(uid)
    if not entry or not isinstance(entry, dict):
        return False
    return entry.get("rank") == "owner"


def get_effective_permissions(user_id: int | str) -> set[str]:
    return _resolve_permissions(user_id)


def list_presets() -> dict[str, dict]:
    return dict(_load_raw().get("presets") or {})


def list_users() -> dict[str, dict]:
    return dict(_load_raw().get("users") or {})


_last_write_ts: float = 0.0
_WRITE_COOLDOWN = 2.0


def save_permissions(
    cfg: dict[str, Any],
    *,
    writer_id: int | str | None = None,
) -> tuple[bool, str]:
    global _last_write_ts

    if writer_id is not None and not can_write_permissions(writer_id):
        return False, "not allowed to write permissions"

    now = time.time()
    if now - _last_write_ts < _WRITE_COOLDOWN:
        return False, "write cooldown – try again in a moment"

    if not isinstance(cfg, dict):
        return False, "config must be a dict"

    ordered = {
        "super_owner_id": str(cfg.get("super_owner_id") or _FALLBACK_SUPER_OWNER),
        "presets": cfg.get("presets") if isinstance(cfg.get("presets"), dict) else {},
        "users": cfg.get("users") if isinstance(cfg.get("users"), dict) else {},
    }

    try:
        tmp = PERMISSIONS_FILE.with_suffix(".yml.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                ordered,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        tmp.replace(PERMISSIONS_FILE)
        _last_write_ts = now
        print(f"[Permissions] Saved {PERMISSIONS_FILE}")
        return True, "ok"
    except Exception as e:
        return False, f"write failed: {e}"


def give_permission(
    target_id: int | str,
    permission: str,
    *,
    writer_id: int | str,
) -> tuple[bool, str]:
    if not can_write_permissions(writer_id):
        return False, "not allowed"

    cfg = _load_raw()
    if cfg.get("_safe_mode"):
        return False, "safe-mode active – fix permissions.yml first"

    uid = str(target_id)
    users = dict(cfg.get("users") or {})
    entry = dict(users.get(uid) or {})

    extra = list(entry.get("extra") or [])
    perm = _normalize_perm(permission)
    if perm not in {_normalize_perm(x) for x in extra}:
        extra.append(perm)
    entry["extra"] = extra
    users[uid] = entry

    new_cfg = {
        "super_owner_id": cfg["super_owner_id"],
        "presets": cfg["presets"],
        "users": users,
    }
    return save_permissions(new_cfg, writer_id=writer_id)


def set_rank(
    target_id: int | str,
    rank: str,
    *,
    writer_id: int | str,
) -> tuple[bool, str]:
    if not can_write_permissions(writer_id):
        return False, "not allowed"

    cfg = _load_raw()
    if cfg.get("_safe_mode"):
        return False, "safe-mode active – fix permissions.yml first"

    rank = str(rank).strip().lower()
    if rank not in (cfg.get("presets") or {}):
        return False, f"unknown rank: {rank}"

    uid = str(target_id)
    users = dict(cfg.get("users") or {})
    entry = dict(users.get(uid) or {})
    entry["rank"] = rank
    users[uid] = entry

    new_cfg = {
        "super_owner_id": cfg["super_owner_id"],
        "presets": cfg["presets"],
        "users": users,
    }
    return save_permissions(new_cfg, writer_id=writer_id)
