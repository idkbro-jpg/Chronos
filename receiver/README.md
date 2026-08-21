# Chronos Receiver (Beta)

Receive-Mode auf dem Xiaomi.

**Aktuell nur:**

- `?status` \u2013 Receiver-Status + ob der Laptop erreichbar wirkt
- `?ping` \u2013 Erreichbarkeitstest (IP des Laptops)

Kein WoL, kein Heartbeat-System, kein Boot-Steuerung (kommt sp\u00e4ter).

## Settings in der App

- Bot Token (gleicher wie Daemon)
- Command Channel ID
- **Laptop IP** (LAN oder Tailscale)
- Timeout in Sekunden (Standard 30)

## Verhalten

- App pollt den Channel auf Nachrichten mit Prefix `?`
- Bei `?status` / `?ping` wird die Laptop-IP gepr\u00fcft
- Immer eine Antwort im Channel:
  - online + ungef\u00e4hre ms **oder**
  - Timeout-Hinweis (Internet/Netz pr\u00fcfen)

## Build

Android Studio \u2192 Ordner `receiver/` \u00f6ffnen \u2192 Build APK (wie bei Remote).
