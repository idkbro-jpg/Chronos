"""
Chronos Daemon – watches Discord, approves, executes.
"""

import asyncio

import discord

from daemon.config import DISCORD_TOKEN, COMMAND_CHANNEL_ID
from daemon.approval import request_approval
from daemon.executor import run_command
from daemon.luks import unlock_luks
from shared.protocol import parse_command, format_alias_list
from shared.aliases import load_aliases
from shared.config import (
    load_config,
    max_output_chars,
    allowed_command_user_ids,
    luks_enabled,
    luks_device,
    luks_mapper_name,
)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)


def _chunk_text(text: str, limit: int) -> list[str]:
    if not text:
        return []
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


async def _send_output(message: discord.Message, returncode: int, stdout: str, stderr: str):
    limit = max_output_chars()
    header = f"**Exit code:** `{returncode}`"
    await message.reply(header)

    if stdout:
        for i, chunk in enumerate(_chunk_text(stdout, limit)):
            label = "**stdout:**" if i == 0 else f"**stdout (cont. {i + 1}):**"
            await message.reply(f"{label}\n```\n{chunk}\n```")

    if stderr:
        for i, chunk in enumerate(_chunk_text(stderr, limit)):
            label = "**stderr:**" if i == 0 else f"**stderr (cont. {i + 1}):**"
            await message.reply(f"{label}\n```\n{chunk}\n```")

    if not stdout and not stderr:
        await message.reply("_No output_")


async def _handle_luks_unlock(message: discord.Message):
    summary = (
        f"LUKS unlock\n"
        f"device=`{luks_device()}` → mapper=`{luks_mapper_name()}`"
    )
    approved = await request_approval(message, summary, client)
    if not approved:
        return

    await message.add_reaction("🔓")
    ok, msg = await asyncio.to_thread(unlock_luks)
    if ok:
        await message.reply(f"🔓 **Success**\n{msg}")
    else:
        await message.reply(f"🔒 **Failed**\n{msg}")


@client.event
async def on_ready():
    load_config(force=True)
    load_aliases(force=True)
    print(f"[Daemon] Logged in as {client.user} (ID: {client.user.id})")
    print(f"[Daemon] Watching channel ID: {COMMAND_CHANNEL_ID}")
    print(f"[Daemon] LUKS unlock enabled: {luks_enabled()}")
    print("[Daemon] Ready. Waiting for commands...")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    allowed = allowed_command_user_ids()
    if allowed and message.author.id not in allowed:
        await message.reply("You are not allowed to send commands.")
        return

    cmd = parse_command(message.content)
    if cmd is None:
        return

    if cmd == "__LIST_ALIASES__":
        await message.reply(format_alias_list())
        return

    if cmd == "__RELOAD__":
        load_config(force=True)
        load_aliases(force=True)
        await message.reply("🔄 Config + aliases reloaded.")
        return

    if cmd == "__LUKS_UNLOCK__":
        print(f"[Daemon] LUKS unlock requested by {message.author}")
        await _handle_luks_unlock(message)
        return

    print(f"[Daemon] Command received from {message.author}: {cmd}")

    approved = await request_approval(message, cmd, client)
    if not approved:
        return

    await message.add_reaction("⚙️")

    returncode, stdout, stderr = await asyncio.to_thread(run_command, cmd)
    await _send_output(message, returncode, stdout, stderr)


def main():
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
