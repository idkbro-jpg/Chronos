"""
Chronos Daemon

Runs on your Linux machine.
Watches the configured Discord channel for commands,
asks for approval, then executes them.
"""

import asyncio
import discord

from daemon.config import DISCORD_TOKEN, COMMAND_CHANNEL_ID
from daemon.approval import request_approval
from daemon.executor import run_command
from shared.protocol import parse_command

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
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

    author = str(message.author)

    # Approval happens in the terminal of the machine running the daemon
    approved = await asyncio.to_thread(request_approval, cmd, author)

    if not approved:
        await message.reply("❌ Command denied.")
        return

    await message.add_reaction("⚙️")
    await message.reply(f"Executing: `{cmd}` ...")

    returncode, stdout, stderr = await asyncio.to_thread(run_command, cmd)

    # Build response (Discord has a 2000 char limit per message)
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

    # Split if still too long
    if len(response) > 2000:
        response = response[:1990] + "\n... (truncated)"

    await message.reply(response)


def main():
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
