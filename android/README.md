# Chronos Android – Send Mode (Beta)

Kleine Extension-App für Chronos.

**Aktuell nur Send Mode** mit den drei Notfall-Buttons:

- **Status** → `!status`
- **Lock** → `!lock`
- **Screenshot** → `!screenshot`

Die App postet die Commands einfach in den Discord-Command-Channel.
Der Daemon behandelt sie genau wie eine normale Nachricht (inkl. Approval, Whitelist, Lock usw.).

## Voraussetzungen

- Android Studio (Hedgehog oder neuer empfohlen)
- JDK 17+
- Discord Bot Token (derselbe wie beim Daemon oder ein separater)
- Command-Channel-ID

## Setup

1. Repo klonen / `android/` Ordner öffnen
2. In Android Studio: **Open** → Ordner `android/`
3. App bauen & auf dem Xiaomi installieren
4. App öffnen → **Settings** → Bot-Token + Channel-ID eintragen
5. Buttons benutzen

## Sicherheit

- Token wird nur lokal auf dem Gerät gespeichert (SharedPreferences)
- Die App braucht **keinen** Gateway – sie sendet nur REST-Nachrichten
- Alle Sicherheitsfeatures des Daemons bleiben aktiv (Approval, Whitelist, Rate-Limit, Lock …)

## Bekannte Einschränkungen (Beta)

- Noch kein freies Command-Feld
- Noch kein Receive-Modus / WoL
- Keine schöne Fehlerbehandlung bei Rate-Limits
- Token im Klartext in SharedPreferences (später EncryptedSharedPreferences)

## Nächste Schritte (geplant)

- Freies Textfeld + Senden
- Weitere Schnell-Buttons / Aliases
- Receive-Modus + WoL-Bridge
- Bessere Token-Speicherung
