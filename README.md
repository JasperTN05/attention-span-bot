# 📖 Reading Focus Bot

Telegram-Bot für fokussiertes Lesen und Lernen mit Active Recall und Spaced Repetition.

## Features

| Modus | Was passiert |
|-------|-------------|
| `/lesen [min]` | Reiner Timer – entspannt, kein Recall |
| `/lernen [min]` | Timer + Active Recall + Spaced Repetition |
| `/wiederholungen` | Fällige Reviews anzeigen |
| `/stats` | Deine Lernstatistiken |
| `/stop` | Aktuelle Session abbrechen |

## Architektur

```
GitHub Gist ←→ load/save_gist.py
                        ↓
              bot.py (Polling, läuft in Actions)
                        ↓
              storage.py (JSON, lokal im Runner)
              
GitHub Actions Cron (2x täglich):
  → send_reminders.py → Telegram API
```

## Setup

### 1. Telegram Bot erstellen
1. [@BotFather](https://t.me/BotFather) öffnen
2. `/newbot` → Name und Username vergeben
3. **Token** kopieren

### 2. GitHub Gist als Datenbank anlegen
1. Gehe zu https://gist.github.com
2. Neue Datei: `data.json`, Inhalt: `{"users": {}}`
3. **Gist als Secret (nicht Public!)** anlegen
4. Gist-ID aus der URL kopieren: `gist.github.com/{username}/{GIST_ID}`

### 3. GitHub Token für Gist-Zugriff
1. GitHub → Settings → Developer Settings → Personal Access Tokens
2. Token mit `gist` Scope erstellen

### 4. Repository Secrets anlegen
In deinem GitHub Repo unter Settings → Secrets → Actions:

| Secret | Wert |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Token von BotFather |
| `GIST_ID` | ID des Gists |
| `GIST_TOKEN` | GitHub Personal Access Token |

### 5. Bot starten
- **Automatisch**: Actions → "Reading Focus Bot" → "Run workflow"
- **Geplante Erinnerungen**: laufen automatisch 2x täglich

## Wichtige Limitierung mit GitHub Actions

GitHub Actions kann keinen dauerhaft laufenden Server hosten. Der Bot läuft im **Polling-Modus** – er muss manuell (oder per Cron) gestartet werden. 

**Alternativen für dauerhaften Betrieb:**
- [Railway](https://railway.app) – kostenlos, einfach, persistenter Storage
- [Fly.io](https://fly.io) – kostenlos mit 256 MB RAM
- Eigener VPS (Hetzner ab ~4€/Monat)

## Lokal entwickeln

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="dein_token"
python bot.py
```

## Dateistruktur

```
.
├── bot.py                    # Hauptbot
├── storage.py                # Datenpersistenz (JSON)
├── requirements.txt
├── scripts/
│   ├── load_gist.py          # Daten aus Gist laden
│   ├── save_gist.py          # Daten in Gist speichern
│   └── send_reminders.py     # Scheduled Erinnerungen
└── .github/workflows/
    └── bot.yml               # GitHub Actions Workflow
```
