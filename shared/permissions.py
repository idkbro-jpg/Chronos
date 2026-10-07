"""
Chronos permission system.

- Source of truth: permissions.yml
- Discord roles → Chronos ranks (by name or ID)
- Higher ranks inherit all lower ranks
- Optional per-user overrides (extra / denied permissions + extra ranks)
- Permission names = special names OR any command/alias name
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.config import ROOT

PERMISSIONS_FILE = ROOT / "permissions.yml"

_cfg: dict[str, Any] = {}
_loaded = False


def _defaults() -> dict[str, Any]:
    return {
        "special_permissions": {
            "sudo": "Bypass every permission check",
            "manage_permissions": "Use !perm and edit permissions",
            "manage_bot": "Restart / shutdown / change prefix etc.",
        },
        "role_map": {},
        "ranks": {
            "owner": {"level": 100, "permissions": ["*"]},
        },
        "user_overrides": {},
    }


def load_permissions(force: bool = False) -> dict[str, Any]:
    global _cfg, _loaded
    if _loaded and not force:
        return _cfg

    cfg = _defaults()
    if PERMISSIONS_FILE.exists():
        try:
            with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                # shallow merge is enough for our structure
                for key in ("special_permissions", "role_map", "ranks", "user_overrides"):
                    if key in data and isinstance(data[key], dict):
                        cfg[key] = data[key]
            print(f"[Permissions] Loaded {PERMISSIONS_FILE}")
        except Exception as e:
            print(f"[Permissions] Failed to load permissions.yml: {e} – using defaults")
    else:
        print(f"[Permissions] No permissions.yml at {PERMISSIONS_FILE} – using defaults")

    _cfg = cfg
    _loaded = True
    return _cfg


def save_permissions(cfg: dict[str, Any] | None = None) -> None:
    """Write current (or provided) config back to permissions.yml."""
    global _cfg, _loaded
    data = cfg if cfg is not None else _cfg
    if not data:
        data = load_permissions()

    # Keep a clean order for humans
    ordered = {
        "special_permissions": data.get("special_permissions") or {},
        "role_map": data.get("role_map") or {},
        "ranks": data.get("ranks") or {},
        "user_overrides": data.get("user_overrides") or {},
    }

    tmp = PERMISSIONS_FILE.with_suffix(".yml.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(ordered, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    tmp.replace(PERMISSIONS_FILE)
    _cfg = ordered
    _loaded = True
    print(f"[Permissions] Saved {PERMISSIONS_FILE}")


def _collect_ranks(member) -> list[dict]:
    """Return list of rank dicts the member currently holds (via Discord roles + overrides)."""
    cfg = load_permissions()
    ranks_found: list[dict] = []

    role_map = cfg.get("role_map") or {}
    all_ranks = cfg.get("ranks") or {}

    # Discord roles → Chronos ranks
    member_role_ids = {str(r.id) for r in member.roles}
    member_role_names = {r.name for r in member.roles}

    for key, rank_name in role_map.items():
        key_str = str(key)
        if key_str in member_role_ids or key_str in member_role_names:
            rank = all_ranks.get(rank_name)
            if rank:
                ranks_found.append(rank)

    # User overrides – extra ranks
    override = (cfg.get("user_overrides") or {}).get(str(member.id)) or {}
    for rank_name in override.get("extra_ranks") or []:
        rank = all_ranks.get(rank_name)
        if rank:
            ranks_found.append(rank)

    return ranks_found


def has_permission(member, permission: str) -> bool:
    """
    Check whether the Discord member has the given Chronos permission.

    permission can be a special name ("sudo") or any command/alias name ("aegis").
    """
    if member is None or permission is None:
        return False

    permission = str(permission).lower().strip()
    cfg = load_permissions()

    ranks = _collect_ranks(member)
    if not ranks:
        # No Chronos rank at all → only allow if somehow granted via override extras alone
        override = (cfg.get("user_overrides") or {}).get(str(member.id)) or {}
        extras = {str(p).lower() for p in (override.get("extra_permissions") or [])}
        denied = {str(p).lower() for p in (override.get("denied_permissions") or [])}
        if permission in denied:
            return False
        return permission in extras or "*" in extras or "sudo" in extras

    # Highest level wins for inheritance
    highest_level = max(r.get("level", 0) for r in ranks)

    all_perms: set[str] = set()
    for rank_name, rank in (cfg.get("ranks") or {}).items():
        if rank.get("level", 0) <= highest_level:
            for p in rank.get("permissions") or []:
                all_perms.add(str(p).lower())

    # Apply user overrides
    override = (cfg.get("user_overrides") or {}).get(str(member.id)) or {}
    for p in override.get("extra_permissions") or []:
        all_perms.add(str(p).lower())
    for p in override.get("denied_permissions") or []:
        all_perms.discard(str(p).lower())

    if "*" in all_perms or "sudo" in all_perms:
        return True
    return permission in all_perms


def get_user_effective_permissions(member) -> set[str]:
    """Return the full set of permission names the member currently has."""
    cfg = load_permissions()
    ranks = _collect_ranks(member)
    if not ranks:
        override = (cfg.get("user_overrides") or {}).get(str(member.id)) or {}
        extras = {str(p).lower() for p in (override.get("extra_permissions") or [])}
        denied = {str(p).lower() for p in (override.get("denied_permissions") or [])}
        return extras - denied

    highest_level = max(r.get("level", 0) for r in ranks)
    all_perms: set[str] = set()
    for rank in (cfg.get("ranks") or {}).values():
        if rank.get("level", 0) <= highest_level:
            for p in rank.get("permissions") or []:
                all_perms.add(str(p).lower())

    override = (cfg.get("user_overrides") or {}).get(str(member.id)) or {}
    for p in override.get("extra_permissions") or []:
        all_perms.add(str(p).lower())
    for p in override.get("denied_permissions") or []:
        all_perms.discard(str(p).lower())

    return all_perms


def list_special_permissions() -> dict[str, str]:
    return dict(load_permissions().get("special_permissions") or {})


def list_ranks() -> dict[str, dict]:
    return dict(load_permissions().get("ranks") or {})
