"""
Chronos Discord Bot – messenger only, no execution rights.

Optional. Prefer running only the daemon (one gateway connection per token).
If both bot and daemon use the same token, Discord will disconnect one of them.
"""

import discord
from discord.ext import commands

from bot.config import (
    DISCORD_TOKEN,
    COMMAND_CHANNEL_ID,
    ALLOWED_USER_IDS,
    COMMAND_PREFIX,
    WHITELIST_ENABLED,
)
from shared.protocol import parse_command

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"[Bot] Watching channel ID: {COMMAND_CHANNEL_ID}")
    print("[Bot] Ready. This bot has no execution rights.")
    print("[Bot] Note: do not run bot+daemon with the same token at once.")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    if WHITELIST_ENABLED:
        if message.author.id not in ALLOWED_USER_IDS:
            return

    cmd = parse_command(message.content)
    if cmd is None:
        return

    try:
        await message.add_reaction("👀")
    except discord.HTTPException:
        pass
    print(f"[Bot] Command seen from {message.author}: {cmd}")


def main():
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
