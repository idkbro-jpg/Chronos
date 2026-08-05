"""
Discord reaction-based approval.

Works when the daemon runs as a background systemd service.
"""

import asyncio
from typing import Optional

import discord

# How long we wait for a reaction (seconds)
APPROVAL_TIMEOUT = 60

APPROVE_EMOJI = "✅"
DENY_EMOJI = "❌"


async def request_approval(
    message: discord.Message,
    command: str,
    client: discord.Client,
    allowed_user_ids: list[int] | None = None,
) -> bool:
    """
    Ask for approval via Discord reactions on the original message.

    Returns True if approved, False if denied or timed out.
    """
    prompt = await message.reply(
        f"**Approval needed** for `{command}`\n"
        f"React with {APPROVE_EMOJI} to execute or {DENY_EMOJI} to deny.\n"
        f"(Timeout: {APPROVAL_TIMEOUT}s)"
    )

    await prompt.add_reaction(APPROVE_EMOJI)
    await prompt.add_reaction(DENY_EMOJI)

    def check(reaction: discord.Reaction, user: discord.User) -> bool:
        if user.bot:
            return False
        if reaction.message.id != prompt.id:
            return False
        if str(reaction.emoji) not in (APPROVE_EMOJI, DENY_EMOJI):
            return False

        # Optional: only allow specific users
        if allowed_user_ids and user.id not in allowed_user_ids:
            return False

        return True

    try:
        reaction, user = await client.wait_for(
            "reaction_add", timeout=APPROVAL_TIMEOUT, check=check
        )
    except asyncio.TimeoutError:
        await prompt.edit(content=f"⏰ Timed out. Command `{command}` was **not** executed.")
        return False

    if str(reaction.emoji) == APPROVE_EMOJI:
        await prompt.edit(content=f"✅ Approved by {user.display_name}. Executing `{command}`...")
        return True

    await prompt.edit(content=f"❌ Denied by {user.display_name}.")
    return False
