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
│                  │     - asks for approval (password)
│                  │     - executes command
│                  │     - sends output back
└──────────────────┘
```

## Features (planned / current)

- [x] Clean separation: Bot has no rights
- [x] Prefix commands (`!`)
- [ ] Password / approval before execution
- [ ] Safe command execution (stdout/stderr capture)
- [ ] Binary-safe output handling where possible
- [ ] Allowlist for users / channels
- [ ] systemd service file
- [ ] Logging

## Quick Start (Linux)

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
# edit .env and fill in your Discord bot token + channel ID + approval password
```

### 3. Run

**Terminal 1 – Bot**
```bash
python -m bot.main
```

**Terminal 2 – Daemon**
```bash
python -m daemon.main
```

## Usage

In the configured Discord channel:

```
!neofetch
!cmd uname -a
!cmd ls -la /
```

The daemon will ask for approval in the terminal before running anything.

## Security Notes

- The bot token should only have the minimum permissions needed (message content, send messages).
- The daemon is the only component that can execute code on your machine.
- Always use a strong approval password.
- Run the daemon under a dedicated low-privilege user if possible.
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
