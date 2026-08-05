"""
Chronos Discord Bot

This bot has ZERO privileges on the target machine.
It only accepts commands and posts them into the configured channel
so the daemon can pick them up.
"""

import discord
from discord.ext import commands

from bot.config import DISCORD_TOKEN, COMMAND_CHANNEL_ID, ALLOWED_USER_IDS, COMMAND_PREFIX
from shared.protocol import parse_command

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"[Bot] Watching channel ID: {COMMAND_CHANNEL_ID}")
    print("[Bot] Ready. This bot has no execution rights.")


@bot.event
async def on_message(message: discord.Message):
    # Ignore own messages
    if message.author == bot.user:
        return

    # Only listen in the configured channel
    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    # Optional user allowlist
    if ALLOWED_USER_IDS and message.author.id not in ALLOWED_USER_IDS:
        await message.reply("You are not allowed to send commands.")
        return

    cmd = parse_command(message.content)
    if cmd is None:
        return

    # Just acknowledge – the daemon will handle execution
    await message.add_reaction("👀")
    print(f"[Bot] Command received from {message.author}: {cmd}")

    # The daemon is watching the same channel and will pick this up.
    # We do NOT execute anything here on purpose.


def main():
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
