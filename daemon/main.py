"""
Chronos Daemon

Runs on your Linux machine.
Watches the configured Discord channel for commands,
resolves aliases, asks for approval via reactions, then executes them.
"""

import asyncio
import discord

from daemon.config import DISCORD_TOKEN, COMMAND_CHANNEL_ID
from daemon.approval import request_approval
from daemon.executor import run_command
from shared.protocol import parse_command, format_alias_list
from shared.aliases import load_aliases

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    load_aliases(force=True)  # load on startup
    print(f"[Daemon] Logged in as {client.user} (ID: {client.user.id})")
    print(f"[Daemon] Watching channel ID: {COMMAND_CHANNEL_ID}")
    print("[Daemon] Ready. Waiting for commands...")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    cmd = parse_command(message.content)
    if cmd is None:
        return

    # Built-in: list aliases (no approval needed)
    if cmd == "__LIST_ALIASES__":
        await message.reply(format_alias_list())
        return

    print(f"[Daemon] Command received from {message.author}: {cmd}")

    # Approval via Discord reactions (shows the *resolved* command)
    approved = await request_approval(message, cmd, client)

    if not approved:
        return

    await message.add_reaction("⚙️")

    returncode, stdout, stderr = await asyncio.to_thread(run_command, cmd)

    parts = []
    parts.append(f"**Exit code:** `{returncode}`")

    if stdout:
        parts.append("**stdout:**")
        parts.append(f"```\n{stdout[:1800]}\n```")
    if stderr:
        parts.append("**stderr:**")
        parts.append(f"```\n{stderr[:1800]}\n```")

    if not stdout and not stderr:
        parts.append("_No output_")

    response = "\n".join(parts)

    if len(response) > 2000:
        response = response[:1990] + "\n... (truncated)"

    await message.reply(response)


def main():
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
