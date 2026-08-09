"""
Small Discord message helpers (escaping, safe display).
"""

from __future__ import annotations


def escape_backticks(text: str) -> str:
    """
    Make text safe to put inside a single Discord `inline code` span.
    Replaces backticks so they cannot break the surrounding markdown.
    """
    if not text:
        return ""
    # Zero-width space after each backtick is a common, readable escape
    return text.replace("`", "`\u200b")


def truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def safe_inline(text: str, limit: int = 200) -> str:
    """Truncate + escape for use inside `...` markdown."""
    return escape_backticks(truncate(text, limit))
