"""
Load and resolve command aliases from aliases.yml
"""

from pathlib import Path
from typing import Optional

import yaml

from shared.config import aliases_path

_aliases: dict[str, str] = {}
_loaded = False


def load_aliases(force: bool = False) -> dict[str, str]:
    global _aliases, _loaded

    if _loaded and not force:
        return _aliases

    _aliases = {}
    path = aliases_path()

    if not path.exists():
        print(f"[Aliases] No aliases file found at {path}")
        _loaded = True
        return _aliases

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            _aliases = {
                str(k).lower().strip(): str(v).strip()
                for k, v in data.items()
                if k is not None and v is not None
            }
        print(f"[Aliases] Loaded {len(_aliases)} aliases from {path}")
    except Exception as e:
        print(f"[Aliases] Failed to load aliases: {e}")

    _loaded = True
    return _aliases


def resolve_alias(name: str) -> Optional[str]:
    aliases = load_aliases()
    return aliases.get(name.lower().strip())


def list_aliases() -> dict[str, str]:
    return load_aliases().copy()
