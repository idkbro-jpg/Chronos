# Chronos

Secure remote command execution via Discord.

A daemon on your Linux machine watches a channel, requires reaction approval, then runs commands. Optional LUKS unlock for secondary volumes. Android companions: **remote** (send) and **receiver** (status/ping bridge).

## Security warning

If `discord.whitelist_enabled` is `false` (default), anyone who can post in the command channel can propose shell commands. Approval still needs ✅, but if `approval.allowed_user_ids` is empty, **any** non-bot user can approve.

Recommended minimum:

```yaml
discord:
  whitelist_enabled: true
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
approval:
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
```

## Quick start

```bash
cd ~/Chronos   # or your clone path
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python setup.py          # interactive wizard (recommended first run)
```

Or manually:

```bash
cp .env.example .env     # token + channel id
# edit config.yml
python -m scripts.set_lock_password
```

Enable **MESSAGE CONTENT INTENT** for the bot. Invite with send / read history / add reactions.

```bash
systemctl --user enable --now chronos-daemon.service
journalctl --user -u chronos-daemon.service -f
```

## Update

```bash
python update.py
```

## Useful commands

| Command | Meaning |
|---------|---------|
| `!help` | Overview |
| `!status` | Lock / alarm / sudomode / whitelist |
| `!lock` | Lock machine (needs ✅ unless sudomode) |
| `!sudomode` | Status; enable via DM `sudomode <password>` |
| `!screenshot` | Capture screen |
| `!reload` | Reload config + aliases |

Unlock / sudomode password: **DM only** — `unlock <password>` / `sudomode <password>`.

## Layout

| Path | Purpose |
|------|---------|
| `.env` | `DISCORD_TOKEN`, `COMMAND_CHANNEL_ID` |
| `config.yml` | Prefix, whitelist, timeouts, rate limit, LUKS |
| `aliases.yml` | Shortcuts |
| `secrets/` | Lock hash, LUKS material (gitignored) |
| `remote/` | Android send APK |
| `receiver/` | Android receive APK (local `?status` / `?ping`) |
| `setup.py` | First-time / reconfigure wizard |
| `update.py` | git pull + pip + restart |

## Logs

- Live: `journalctl --user -u chronos-daemon.service -f`
- Files: `logs/chronos-YYYY-MM-DD.log`
