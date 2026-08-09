# Chronos

Secure remote command execution via Discord.

Daemon on your Linux machine watches a channel, requires reaction approval, then runs commands. Optional LUKS unlock for secondary volumes after boot.

## ⚠️ Security warning

**If `discord.whitelist_enabled` is `false` (the default), anyone who can post in the command channel can propose shell commands on this machine.**

Approval still requires a `✅` reaction, but if `approval.allowed_user_ids` is also empty, **any** non-bot user in the channel can approve — including strangers in a public server.

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

The daemon prints a loud warning on startup when the whitelist is off. Shell commands run as the user that owns the daemon process (often with substantial privileges).

## Config

| File | Purpose |
|------|--------|
| `.env` | `DISCORD_TOKEN`, `COMMAND_CHANNEL_ID` |
| `config.yml` | Timeouts, emojis, shell, allowlists, LUKS, audit channel |
| `aliases.yml` | Shortcuts |
| `secrets/` | Encrypted LUKS password + machine key (gitignored) |

```text
!help            # command overview
!status          # lock / alarm / rate-limit / luks / whitelist
!reload          # reload config + aliases without restart
!history         # recent executed commands
!last            # last executed command
!luksunlock      # unlock configured LUKS volume
!input alt p     # keyboard simulation
!mouse click     # mouse simulation
```

## Quick Start

```bash
cd ~/Chronos
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill token + channel id
```

Enable **MESSAGE CONTENT INTENT**. Invite bot with send/read/reaction perms.

### Update

```bash
cd ~/Chronos
python update.py
```

Pulls from git, installs requirements, restarts `chronos-daemon.service`.  
See `python update.py --help` for `--stash` / `--force` / `--no-restart`.

### systemd user service

```ini
[Unit]
Description=Chronos Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/Chronos
ExecStart=%h/Chronos/venv/bin/python -m daemon.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now chronos-daemon.service
```

## LUKS

See [docs/luks.md](docs/luks.md).

Short version: works for volumes unlocked **after** boot. Not for pre-boot root unlock.

```bash
python -m scripts.set_luks_password
# then enable + set device in config.yml
# !luksunlock in Discord
```

## Optional hardening

- `execution.mode: allowlist` + `allowed_patterns` — only matching commands run
- `discord.audit_channel_id` — mirror exec/lock/unlock events to a private channel
- Prefer a private Discord channel + whitelist always on
- See [docs/security.md](docs/security.md)

## Note on `bot/`

Prefer running **only the daemon**. The optional `bot/` package is messenger-only; sharing the same token with the daemon causes Discord to disconnect one of them.
