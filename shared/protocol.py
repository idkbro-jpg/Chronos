"""
Shared command parsing helpers.
"""

from shared.aliases import resolve_alias, list_aliases
from shared.config import command_prefix


def is_command(content: str) -> bool:
    prefix = command_prefix()
    return content.strip().startswith(prefix)


def parse_command(content: str) -> str | None:
    """
    Extract the actual shell command from a Discord message.
    Aliases are resolved here (before approval).
    """
    content = content.strip()
    prefix = command_prefix()

    if not content.startswith(prefix):
        return None

    body = content[len(prefix):].strip()
    if not body:
        return None

    lower = body.lower()

    # Built-ins (no execution)
    if lower in ("aliases", "alias", "listaliases"):
        return "__LIST_ALIASES__"
    if lower in ("reload", "reloadaliases", "reloadconfig"):
        return "__RELOAD__"

    # Explicit !cmd ... → raw command, no alias
    if lower.startswith("cmd "):
        return body[4:].strip() or None

    first = body.split()[0]
    rest = body[len(first):].strip()

    aliased = resolve_alias(first)
    if aliased is not None:
        if rest:
            return f"{aliased} {rest}"
        return aliased

    return body


def format_alias_list() -> str:
    aliases = list_aliases()
    if not aliases:
        return "No aliases defined."

    lines = ["**Available aliases:**", "```"]
    for name, cmd in sorted(aliases.items()):
        display = cmd if len(cmd) <= 80 else cmd[:77] + "..."
        lines.append(f"{name:12} → {display}")
    lines.append("```")
    lines.append("_Built-ins: `!aliases` · `!reload`_")
    return "\n".join(lines)
