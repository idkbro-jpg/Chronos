# Chronos Android – Send Mode (legacy beta)

Small companion app for Chronos.

**Prefer the `remote/` app** (same role, more features). This folder is the older send-only beta.

Emergency buttons:

- **Status** → `!status`
- **Lock** → `!lock`
- **Screenshot** → `!screenshot`

The app posts commands into the Discord command channel.
The daemon treats them like any other message (approval, whitelist, lock, etc.).

## Requirements

- Android Studio (Hedgehog or newer recommended)
- JDK 17+
- Discord bot token (same as the daemon, or a separate bot)
- Command channel ID

## Setup

1. Clone the repo / open the `android/` folder
2. In Android Studio: **Open** → `android/`
3. Build the app and install it on your device
4. Open the app → **Settings** → enter bot token + channel ID
5. Use the buttons

## Security

- Token is stored only on the device (SharedPreferences)
- The app does **not** open a Discord gateway — REST send only
- All daemon security features stay active (approval, whitelist, rate limit, lock, …)

## Known limitations (beta)

- No free-form command field
- No receive mode / Wake-on-LAN
- No polished rate-limit error handling
- Token in plaintext SharedPreferences (later: EncryptedSharedPreferences)
- Prefix is hardcoded to `!` (use `remote/` for a configurable prefix)

## Next steps

Use **`remote/`** and **`receiver/`** for current Android support. Prebuilt APKs: [Releases](https://github.com/idkbro-jpg/Chronos/releases).
