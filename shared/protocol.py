"""
Shared constants and helpers between bot and daemon.
"""

COMMAND_PREFIX = "!"

# Special command that just runs neofetch for convenience
NEOFETCH_ALIAS = "neofetch"

def is_command(content: str) -> bool:
    return content.strip().startswith(COMMAND_PREFIX)

def parse_command(content: str) -> str | None:
    """
    Extract the actual shell command from a Discord message.

    Examples:
        !neofetch          → neofetch
        !cmd ls -la        → ls -la
        !cmd uname -a      → uname -a
    """
    content = content.strip()
    if not content.startswith(COMMAND_PREFIX):
        return None

    body = content[len(COMMAND_PREFIX):].strip()

    if body.lower() == NEOFETCH_ALIAS:
        return "neofetch"

    if body.lower().startswith("cmd "):
        return body[4:].strip()

    # fallback: treat everything after ! as the command
    return body if body else None
