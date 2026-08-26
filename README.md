# Chronos

**Secure remote command execution via Discord** — for accessibility and remote access on Linux.

A daemon on your machine watches a Discord channel, waits for ✅ approval, then runs the command. Optional lock / unlock, screenshots, keyboard & mouse, LUKS, and Android companion apps.

---

## Downloads

| What | Where |
|------|--------|
| **Source + setup** | [Clone this repo](https://github.com/idkbro-jpg/Chronos) or download the source zip from [Releases](https://github.com/idkbro-jpg/Chronos/releases) |
| **Android APKs** (Remote + Receiver) | **[Download APKs here →](https://github.com/idkbro-jpg/Chronos/releases)** |

> **No Android Studio needed** if you use the prebuilt APKs from Releases.  
> Prefer building yourself? Sources live in `remote/` and `receiver/`.

---

## Quick start (Linux)

```bash
git clone https://github.com/idkbro-jpg/Chronos.git
cd Chronos

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python setup.py          # interactive wizard — recommended first run
```

Then:

1. Discord Developer Portal → Bot → enable **MESSAGE CONTENT INTENT**
2. Invite the bot with: Send Messages, Read Message History, Add Reactions
3. Start the daemon:

```bash
systemctl --user enable --now chronos-daemon.service
journalctl --user -u chronos-daemon.service -f
```

Update later with:

```bash
python update.py
```

---

## Security (read this)

If `whitelist_enabled` is **false** (default for easy first setup), anyone who can post in the command channel can *propose* shell commands. Approval still needs ✅ — but if the approval list is empty, **any** non-bot user can approve.

**Recommended minimum for real use:**

```yaml
discord:
  whitelist_enabled: true
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
approval:
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
```

Unlock / sudomode passwords are sent **only via DM**. Failed password attempts are **never** written to logs (only the length may be recorded).

More detail: [docs/security.md](docs/security.md)

---

## Useful commands

| Command | What it does |
|---------|----------------|
| `!help` | Overview |
| `!status` | Lock / alarm / sudomode / whitelist |
| `!ping` | Latency check |
| `!lock` | Lock the machine (needs ✅ unless sudomode) |
| `!sudomode` | Status; enable via DM: `sudomode <password>` |
| `!screenshot` | Capture screen |
| `!input …` | Keyboard simulation |
| `!mouse …` | Basic mouse |
| `!reload` | Reload config + aliases |
| `!history` / `!last` | Recent commands |

**Unlock / sudomode:** DM only → `unlock <password>` / `sudomode <password>`

---

## Prefixes (important)

| Prefix | Used by |
|--------|---------|
| `!` (default) | Chronos daemon commands |
| `?` | Android **Receiver** local commands (`?status`, `?ping`) — do **not** set the bot prefix to `?` |

You can change the bot prefix in `config.yml` (`discord.command_prefix`), but keep it different from `?`.

---

## Android apps

| App | Role |
|-----|------|
| **Remote** (`remote/`) | Send commands / emergency buttons from your phone |
| **Receiver** (`receiver/`) | Always-on bridge phone: local `?status` / `?ping`, optional forward to Discord |

Prebuilt APKs: **[Releases](https://github.com/idkbro-jpg/Chronos/releases)**  
Or open the folders in Android Studio and build yourself.

---

## Layout

| Path | Purpose |
|------|---------|
| `.env` | Token + channel ID (secrets) |
| `config.yml` | Prefix, whitelist, timeouts, rate limit, LUKS |
| `aliases.yml` | Shortcuts (e.g. `!uptime`) |
| `secrets/` | Lock hash, LUKS material (gitignored) |
| `setup.py` | First-time / reconfigure wizard |
| `update.py` | `git pull` + pip + restart daemon |
| `remote/` / `receiver/` | Android **source** (build APKs locally or use Releases) |
| `docs/` | Security, input, LUKS notes |

Compiled APKs are **not** kept in the source tree (they bloat every clone). Use Releases or build from source.

**Config tip:** timeouts, rate-limit numbers, history size, and `audit_channel_id` must be integers. If a value is missing or invalid (e.g. text instead of a number), Chronos keeps running and uses the built-in default for that field (see comments in `config.yml` — e.g. approval timeout → **60**, command timeout → **300**, rate limit → **20** / **60** s, history → **30**). Invalid Discord user IDs in allowlists are skipped the same way.

---

## Logs

```bash
journalctl --user -u chronos-daemon.service -f
# or files:
logs/chronos-YYYY-MM-DD.log
```

---

## Requirements

- Linux (systemd user services recommended)
- Python 3.10+
- Discord bot with Message Content Intent
- Optional: `ydotool` / `wtype` / `xdotool` for keyboard & mouse

Windows is **not** supported yet.

---

Made for people who want remote access without fighting the setup for an hour.
