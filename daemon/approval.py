"""
Discord reaction-based approval.
"""

import asyncio

import discord

from shared.config import (
    approval_timeout,
    approve_emoji,
    deny_emoji,
    allowed_approval_user_ids,
)
from shared.discord_utils import safe_inline


async def request_approval(
    message: discord.Message,
    command: str,
    client: discord.Client,
) -> bool:
    timeout = approval_timeout()
    ok = approve_emoji()
    no = deny_emoji()
    allowed = allowed_approval_user_ids()

    # Truncate + escape backticks so Discord markdown cannot break
    shown = safe_inline(command, 200)

    prompt = await message.reply(
        f"**Approval needed** for `{shown}`\n"
        f"React with {ok} to execute or {no} to deny.\n"
        f"(Timeout: {timeout}s)"
    )

    try:
        await prompt.add_reaction(ok)
        await prompt.add_reaction(no)
    except discord.HTTPException as e:
        try:
            await prompt.edit(
                content=(
                    f"Cannot add approval reactions ({e.status}). "
                    f"Grant the bot **Add Reactions** (and **Read Message History**) "
                    f"in this channel. Command was **not** executed."
                )
            )
        except discord.HTTPException:
            pass
        return False

    def check(reaction: discord.Reaction, user: discord.User) -> bool:
        if user.bot:
            return False
        if reaction.message.id != prompt.id:
            return False
        if str(reaction.emoji) not in (ok, no):
            return False
        if allowed and user.id not in allowed:
            return False
        return True

    try:
        reaction, user = await client.wait_for(
            "reaction_add", timeout=timeout, check=check
        )
    except asyncio.TimeoutError:
        try:
            await prompt.edit(
                content=f"⏰ Timed out. Command `{shown}` was **not** executed."
            )
        except discord.HTTPException:
            pass
        return False

    if str(reaction.emoji) == ok:
        try:
            await prompt.edit(
                content=f"{ok} Approved by {user.display_name}. Executing `{shown}`..."
            )
        except discord.HTTPException:
            pass
        return True

    try:
        await prompt.edit(content=f"{no} Denied by {user.display_name}.")
    except discord.HTTPException:
        pass
    return False
