"""
Load and resolve command aliases from aliases.yml
"""

from pathlib import Path
from typing import Optional

import yaml

# aliases.yml lives in the project root
ALIASES_FILE = Path(__file__).resolve().parent.parent / "aliases.yml"

_aliases: dict[str, str] = {}
_loaded = False


def load_aliases(force: bool = False) -> dict[str, str]:
    global _aliases, _loaded

    if _loaded and not force:
        return _aliases

    _aliases = {}
    if not ALIASES_FILE.exists():
        print(f"[Aliases] No aliases file found at {ALIASES_FILE}")
        _loaded = True
        return _aliases

    try:
        with open(ALIASES_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            # keys lowercased for case-insensitive matching
            _aliases = {str(k).lower().strip(): str(v).strip() for k, v in data.items()}
        print(f"[Aliases] Loaded {len(_aliases)} aliases from {ALIASES_FILE}")
    except Exception as e:
        print(f"[Aliases] Failed to load aliases: {e}")

    _loaded = True
    return _aliases


def resolve_alias(name: str) -> Optional[str]:
    """
    If `name` is an alias, return the real command.
    Otherwise return None.
    """
    aliases = load_aliases()
    return aliases.get(name.lower().strip())


def list_aliases() -> dict[str, str]:
    return load_aliases().copy()
