# Chronos

Secure remote command execution via Discord.

Daemon on your Linux machine watches a channel, requires reaction approval, then runs commands. Optional LUKS unlock for secondary volumes after boot.

## Config

| File | Purpose |
|------|--------|
| `.env` | `DISCORD_TOKEN`, `COMMAND_CHANNEL_ID` |
| `config.yml` | Timeouts, emojis, shell, allowlists, LUKS |
| `aliases.yml` | Shortcuts |
| `secrets/` | Encrypted LUKS password + machine key (gitignored) |

```text
!reload          # reload config + aliases without restart
!luksunlock      # unlock configured LUKS volume
```

## Quick Start

```bash
cd ~/Chronos
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill token + channel id
```

Enable **MESSAGE CONTENT INTENT**. Invite bot with send/read/reaction perms.

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
