"""
Shared constants and helpers between bot and daemon.
"""

from shared.aliases import resolve_alias, list_aliases

COMMAND_PREFIX = "!"

def is_command(content: str) -> bool:
    return content.strip().startswith(COMMAND_PREFIX)

def parse_command(content: str) -> str | None:
    """
    Extract the actual shell command from a Discord message.
    Aliases are resolved here (before approval).

    Examples:
        !backup            → tar -czf /tmp/home-backup-.... /home
        !neofetch          → neofetch  (if not an alias, used as-is)
        !cmd ls -la        → ls -la
        !cmd uname -a      → uname -a
        !uptime            → uptime (via alias or direct)
    """
    content = content.strip()
    if not content.startswith(COMMAND_PREFIX):
        return None

    body = content[len(COMMAND_PREFIX):].strip()
    if not body:
        return None

    # Special built-in: list aliases
    if body.lower() in ("aliases", "alias", "listaliases"):
        return "__LIST_ALIASES__"

    # Explicit !cmd ... always runs the raw command (no alias)
    if body.lower().startswith("cmd "):
        return body[4:].strip() or None

    # First word might be an alias
    first = body.split()[0]
    rest = body[len(first):].strip()

    aliased = resolve_alias(first)
    if aliased is not None:
        # Allow !backup --extra-flags  (append extra args)
        if rest:
            return f"{aliased} {rest}"
        return aliased

    # No alias → treat the whole body as the command
    return body


def format_alias_list() -> str:
    aliases = list_aliases()
    if not aliases:
        return "No aliases defined."

    lines = ["**Available aliases:**", "```"]
    for name, cmd in sorted(aliases.items()):
        # truncate long commands for display
        display = cmd if len(cmd) <= 80 else cmd[:77] + "..."
        lines.append(f"{name:12} → {display}")
    lines.append("```")
    return "\n".join(lines)
