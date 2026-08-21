# Chronos Receiver

Android bridge on a always-on phone (e.g. Xiaomi).

- `?status` / `?ping` run **locally** (no Discord required)
- CMD line + listening poll for `?` commands in Discord
- Other commands can be forwarded to Discord

## Build

Open the `receiver/` folder in Android Studio → Build APK.

## Settings

- Bot token, channel ID, optional backend channel ID
- Laptop IP (LAN or Tailscale)
- Timeout (seconds)
