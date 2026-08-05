# Chronos

Secure remote command execution via Discord.

The Discord side is only a messenger.  
A daemon on your Linux machine watches a channel, asks for reaction approval, then executes.

## Config

| File | Purpose |
|------|--------|
| `.env` | Secrets: `DISCORD_TOKEN`, `COMMAND_CHANNEL_ID` |
| `config.yml` | Everything else: timeouts, emojis, shell, prefix, allowlists |
| `aliases.yml` | Command shortcuts (`!backup`, `!aegis`, …) |

After changing `config.yml` or `aliases.yml`:

```text
!reload
```

or restart the systemd service.

## Quick Start (Bazzite / Linux)

```bash
cd ~/Chronos
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
```

Enable **MESSAGE CONTENT INTENT** in the Discord Developer Portal.

Invite (replace CLIENT_ID):

```
https://discord.com/oauth2/authorize?client_id=CLIENT_ID&permissions=274877975552&scope=bot
```

### systemd user service

`~/.config/systemd/user/chronos-daemon.service`:

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

## Usage

```text
!uptime
!cmd uname -a
!aegis example.com -s 2
!aliases
!reload
```

React ✅ to run, ❌ to deny.

## Architecture

```
Discord message  →  Daemon watches channel
                 →  Resolve alias (config)
                 →  Approval reaction
                 →  Execute on machine
                 →  Output back to Discord
```
