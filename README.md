# Chronos

Secure remote command execution via Discord.

The Discord bot has **zero privileges**.  
It only posts commands into a channel.  
A separate daemon running on your Linux machine watches the channel, requires approval, and then executes the command.

## Architecture

```
Discord User
    │
    │  !neofetch / !cmd <command>
    ▼
┌──────────────────┐
│  Discord Bot     │  ← only messenger, no shell access
│  (bot/)          │
└────────┬─────────┘
         │ posts message into configured channel
         ▼
┌──────────────────┐
│  Discord Channel │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Daemon          │  ← runs on your Linux machine
│  (daemon/)       │     - watches the channel
│                  │     - asks for approval (✅ / ❌ reaction)
│                  │     - executes command
│                  │     - sends output back
└──────────────────┘
```

## Features

- [x] Clean separation: Bot has no rights
- [x] Prefix commands (`!`)
- [x] Approval via Discord reactions (works with systemd)
- [x] Safe command execution (stdout/stderr capture)
- [x] Binary-safe output handling where possible
- [ ] Allowlist for users / channels
- [x] systemd user service
- [ ] Logging improvements

## Quick Start (Linux / Bazzite)

### 1. Clone & install

```bash
git clone https://github.com/idkbro-jpg/Chronos.git
cd Chronos
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# edit .env → DISCORD_TOKEN + COMMAND_CHANNEL_ID
```

### 3. Enable Message Content Intent

In the [Discord Developer Portal](https://discord.com/developers/applications/) → your bot → **Bot** → enable **MESSAGE CONTENT INTENT**.

### 4. Invite the bot

```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=274877975552&scope=bot
```

### 5. Run as systemd user service (recommended)

```bash
mkdir -p ~/.config/systemd/user
```

Create `~/.config/systemd/user/chronos-daemon.service`:

```ini
[Unit]
Description=Chronos Daemon - Discord command watcher
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

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now chronos-daemon.service
```

## Usage

In the configured Discord channel:

```
!neofetch
!cmd uname -a
!cmd ls -la /
```

The daemon will post an approval message. React with ✅ to execute or ❌ to deny.

## Security Notes

- The bot token should only have the minimum permissions needed.
- The daemon is the only component that can execute code on your machine.
- Run the daemon under your normal user (or a dedicated low-privilege user).
- Never commit your real `.env` file.

## Project Structure

```
Chronos/
├── bot/           # Discord bot (messenger only)
├── daemon/        # Watcher + executor on your machine
├── shared/        # Shared constants / protocol
├── .env.example
├── requirements.txt
└── README.md
```
