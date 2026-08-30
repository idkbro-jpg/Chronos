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


def chunk_text(text: str, limit: int) -> list[str]:
    """Split text into pieces of at most `limit` characters."""
    if not text:
        return []
    if limit <= 0:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def safe_code_block(text: str) -> str:
    """Escape triple-backticks so a fenced Discord block cannot be closed early."""
    if not text:
        return ""
    return text.replace("```", "``\u200b`")


def format_stream_replies(
    label: str,
    text: str,
    char_limit: int,
    max_chunks: int,
) -> list[str]:
    """
    Turn stdout/stderr into Discord reply strings.

    At most `max_chunks` fenced blocks are produced. Extra content is
    replaced by a single note so a huge command cannot flood the channel.
    """
    if not text:
        return []
    if max_chunks <= 0:
        max_chunks = 1
    chunks = chunk_text(text, char_limit)
    out: list[str] = []
    shown = chunks[:max_chunks]
    omitted = len(chunks) - len(shown)
    for i, chunk in enumerate(shown):
        title = f"**{label}:**" if i == 0 else f"**{label} (cont. {i + 1}):**"
        out.append(f"{title}\n```\n{safe_code_block(chunk)}\n```")
    if omitted > 0:
        out.append(
            f"_{label} truncated: {omitted} extra chunk(s) omitted "
            f"(max {max_chunks} per stream)._"
        )
    return out


def format_exec_replies(
    returncode: int,
    stdout: str,
    stderr: str,
    char_limit: int,
    max_chunks: int,
) -> list[str]:
    """Build the full list of Discord replies for a finished command."""
    replies = [f"**Exit code:** `{returncode}`"]
    replies.extend(format_stream_replies("stdout", stdout, char_limit, max_chunks))
    replies.extend(format_stream_replies("stderr", stderr, char_limit, max_chunks))
    if not stdout and not stderr:
        replies.append("_No output_")
    return replies


def fit_discord_message(text: str, limit: int = 1900) -> str:
    """Hard-cap a message so Discord's 2000-char limit cannot reject it."""
    if limit <= 0:
        return text
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
