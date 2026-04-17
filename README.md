# ✈️ Flight Tracker Agent

A personal flight price monitor that runs silently in the background on your Mac.
It checks Google Flights twice a day, analyses deals with Claude AI, and emails you a
rich HTML digest — completely free (no paid flight APIs, no cloud servers).

---

## How it works

```
macOS LaunchAgent (7 AM + 7 PM)
        │
        ▼
Playwright (headless Chrome)  ──►  Google Flights raw page text
        │
        ▼
Claude Haiku  ──►  ranked flights + best pick + narrative
        │
        ▼
Gmail SMTP  ──►  HTML email digest with booking links
        │
        ▼
Firestore  ──►  price history + drop detection
```

**Why run locally?** Cloud servers (GitHub Actions, AWS, etc.) get blocked by Google's
bot detection. Your home/laptop IP is treated as a normal browser — flights load fine.

---

## Features

- **Best pick card** — top deal with a direct Google Flights booking button
- **Top-5 routes table** — price vs. yesterday trend (🟢↓ / 🔴↑)
- **Cheapest date combo** — flexibility search across ±N days
- **Separate-ticket deals** — hub routes that beat direct fares
- **Positioning flights** — drive/fly to a nearby hub first
- **Mistake fare alerts** — morning scan of deal sites
- **Price history** — Firestore tracks every run; flags drops vs. baseline
- **Settings UI** — browser-based form at `localhost:5050`, no config file editing

---

## Requirements

| Requirement | Notes |
|---|---|
| macOS | Tested on macOS 14+. Linux works too (replace LaunchAgent with cron). |
| Python 3.11 | `brew install python@3.11` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) — Claude Haiku is cheap (~$0.02/day) |
| Gmail account | Needs a [Gmail App Password](https://myaccount.google.com/apppasswords) (not your login password) |
| Google Cloud project | Free tier Firestore is sufficient |

---

## Quick start

### 1 — Clone and install dependencies

```bash
git clone https://github.com/YOUR_USERNAME/flight-tracker-agent.git
cd flight-tracker-agent
python3.11 -m pip install -r requirements.txt
playwright install chromium
```

### 2 — Set up Firestore

1. Create a [Google Cloud project](https://console.cloud.google.com)
2. Enable **Firestore** (Native mode)
3. Create a service account with the **Cloud Datastore User** role
4. Download the JSON key → save as `firestore-key.json` in the project root

### 3 — Open the Settings UI

```bash
bash open_settings.sh
```

This opens `http://localhost:5050` in your browser. Fill in:

| Field | What to enter |
|---|---|
| **Anthropic API Key** | Your `sk-ant-…` key |
| **Gmail Address** | The Gmail account that sends the digest |
| **Gmail App Password** | 16-character app password from Google |
| **Firestore Project ID** | Your GCP project ID |
| **Origin airports** | e.g. `YYZ` (IATA codes, comma-separated) |
| **Destinations** | e.g. `IST, ESB, SAW, AYT` |
| **Outbound / Return dates** | Your target travel window |
| **Recipients** | Comma-separated emails to receive the digest |

Click **Save Settings**, then **▶ Run Now** to test.

### 4 — Install the background scheduler (macOS)

```bash
cp com.flighttracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.flighttracker.plist
```

The tracker now runs automatically at **7:00 AM** and **7:00 PM** every day,
even when the Settings UI is closed.

To stop it:
```bash
launchctl unload ~/Library/LaunchAgents/com.flighttracker.plist
```

### 5 — (Optional) Linux / cron setup

```bash
crontab -e

# Add these two lines (adjust path):
0 7  * * * cd /path/to/flight-tracker-agent && python3.11 main.py >> logs/tracker.log 2>&1
0 19 * * * cd /path/to/flight-tracker-agent && python3.11 main.py >> logs/tracker.log 2>&1
```

---

## Configuration reference

All settings live in `user_config.json` (created by the web UI, never committed to git).
You can also use environment variables or a `.env` file — see `.env.example`.

| Key | Default | Description |
|---|---|---|
| `ORIGINS` | `["YYZ"]` | Departure airport IATA codes |
| `DESTINATIONS` | `["IST","ESB","SAW"]` | Arrival airport IATA codes |
| `OUTBOUND_DATE` | — | Target outbound date `YYYY-MM-DD` |
| `RETURN_DATE` | — | Target return date `YYYY-MM-DD` |
| `OUTBOUND_FLEXIBILITY_DAYS` | `2` | Search ±N days around outbound date |
| `RETURN_FLEXIBILITY_DAYS` | `2` | Search ±N days around return date |
| `ADULTS` | `1` | Number of adult passengers |
| `CHILDREN` | `0` | Number of child passengers |
| `CHILD_AGE` | `7` | Age of child (if children > 0) |
| `MAX_TRAVEL_HOURS` | `20` | Skip itineraries longer than this (hours) |
| `ACTIVE_HUBS_COUNT` | `3` | Hub airports to search (more = slower run) |
| `RECIPIENTS` | `[]` | Email addresses to receive the digest |

---

## Cost estimate

| Service | Monthly cost |
|---|---|
| Claude Haiku (~60 API calls/day × 30 days) | ~$0.50–$1.00 |
| Firestore (free tier) | $0 |
| Gmail SMTP | $0 |
| **Total** | **< $1/month** |

---

## Project structure

```
flight-tracker-agent/
├── main.py                  # Async orchestrator
├── config.py                # All settings (reads user_config.json → env vars → defaults)
├── scraper/
│   └── google_flights.py    # Playwright scraper
├── agent/
│   └── analyzer.py          # Claude Haiku parsing + ranking
├── mailer/
│   └── mailer.py            # HTML email builder + Gmail SMTP
├── data/
│   └── firestore_client.py  # Price history storage
├── web_ui/
│   ├── app.py               # Flask settings server (localhost:5050)
│   └── templates/
│       └── index.html       # Settings form
├── open_settings.sh         # One-click launcher for the settings UI
├── com.flighttracker.plist  # macOS LaunchAgent schedule
├── requirements.txt         # Python dependencies
├── .env.example             # Template for environment variables
└── logs/                    # Tracker run logs (gitignored)
```

---

## Troubleshooting

**No flights in email / empty digest**
- Run `bash open_settings.sh`, click ▶ Run Now, then watch the log box.
- Check that your destinations are valid IATA codes.
- Google Flights works best on home/office IPs. Cloud/VPN IPs may be blocked.

**Email not arriving**
- Confirm Gmail App Password is correct (not your login password).
- Check `logs/tracker.log` for SMTP errors.
- Gmail 2FA must be enabled (required for App Passwords).

**Claude API errors**
- Verify your Anthropic API key has credits at [console.anthropic.com](https://console.anthropic.com).
- Rate limit errors are handled automatically with a built-in delay.

**LaunchAgent not running**
```bash
launchctl list | grep flighttracker   # should show com.flighttracker
tail -50 logs/tracker.log             # see what happened on last run
```

---

## Contributing

Pull requests welcome. Key areas for improvement:
- Additional departure cities / regions
- One-way trip support
- Price alert thresholds (only email when price drops X%)
- Windows support (Task Scheduler instead of LaunchAgent)

---

## License

MIT
