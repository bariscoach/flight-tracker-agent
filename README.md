# ✈️ Flight Tracker Agent

A personal flight price monitor. Configure your routes and API keys in a browser UI,
then hit **Run** whenever you want a fresh price check — it scrapes Google Flights,
analyses deals with Claude AI, and emails you a rich HTML digest.

---

## How it works

```
bash open_settings.sh  →  browser UI at localhost:5050
        │
        ▼ click ▶ Run Now
        │
        ├── Playwright (headless Chrome) scrapes Google Flights
        │
        ├── Claude Haiku ranks deals + writes narrative
        │
        ├── Gmail SMTP sends HTML digest with booking links
        │
        └── Firestore stores price history for trend detection
```

**Why run locally?** Cloud servers get blocked by Google's bot detection.
Your home/laptop IP is treated as a normal browser — flights load fine.

---

## Features

- **Best pick card** — top deal with a direct Google Flights booking button
- **Top-5 routes table** — price vs. yesterday trend (🟢↓ / 🔴↑)
- **Cheapest date combo** — flexibility search across ±N days
- **Separate-ticket deals** — hub routes that beat direct fares
- **Mistake fare alerts** — scans deal sites for Canada→destination errors
- **Price history** — Firestore tracks every run; flags drops vs. baseline

---

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.11 | `brew install python@3.11` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) — Haiku costs ~$0.02/run |
| Gmail account | Needs a [Gmail App Password](https://myaccount.google.com/apppasswords) |
| Google Cloud project | Free-tier Firestore is sufficient |

---

## Setup

### 1 — Clone and install

```bash
git clone https://github.com/bariscoach/flight-tracker-agent.git
cd flight-tracker-agent
python3.11 -m pip install -r requirements.txt
playwright install chromium
```

### 2 — Set up Firestore (one-time)

1. Create a [Google Cloud project](https://console.cloud.google.com)
2. Enable **Firestore** (Native mode)
3. Create a service account → role: **Cloud Datastore User**
4. Download the JSON key → save as `firestore-key.json` in the project root

### 3 — Open the settings UI

```bash
bash open_settings.sh
```

Your browser opens at `http://localhost:5050`. Fill in your details:

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

Click **💾 Save Settings** then **▶ Run Now**.

The log box at the bottom of the page updates every 10 seconds so you can
watch the run in real time. A digest email arrives when it's done (~5–10 min).

---

## Running it again

Any time you want a fresh price check:

```bash
bash open_settings.sh   # opens the UI if it's not already open
```

Then click **▶ Run Now**.

Or run directly from the terminal without opening the UI:

```bash
python3.11 main.py
```

---

## Optional: run on a schedule (macOS)

If you want it to run automatically without clicking anything, you can use
macOS LaunchAgent to fire it at set times:

```bash
# Edit com.flighttracker.plist — replace YOUR_USERNAME with your macOS username
# and adjust the python3.11 path if needed (run: which python3.11)

cp com.flighttracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.flighttracker.plist
```

Default schedule: **7:00 AM** and **7:00 PM** daily.
Edit `com.flighttracker.plist` to change the times.

To stop the schedule:
```bash
launchctl unload ~/Library/LaunchAgents/com.flighttracker.plist
```

For Linux, use `cron` instead:
```bash
crontab -e
# Add:
0 7,19 * * * cd /path/to/flight-tracker-agent && python3.11 main.py >> logs/tracker.log 2>&1
```

---

## Configuration reference

Settings are saved in `user_config.json` (never committed to git).

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
| `ACTIVE_HUBS_COUNT` | `3` | Hub airports to search (more = slower) |
| `RECIPIENTS` | `[]` | Emails to receive the digest |

---

## Cost estimate

| Service | Per run |
|---|---|
| Claude Haiku (~60 API calls) | ~$0.02 |
| Firestore | $0 (free tier) |
| Gmail SMTP | $0 |

---

## Project structure

```
flight-tracker-agent/
├── main.py                  # Orchestrator
├── config.py                # Settings (reads user_config.json → env → defaults)
├── scraper/
│   └── google_flights.py    # Playwright scraper
├── agent/
│   └── analyzer.py          # Claude Haiku parsing + ranking
├── mailer/
│   └── mailer.py            # HTML email + Gmail SMTP
├── data/
│   └── firestore_client.py  # Firestore price history
├── web_ui/
│   ├── app.py               # Settings UI server (localhost:5050)
│   └── templates/
│       └── index.html       # Settings form + log viewer
├── open_settings.sh         # Opens the UI in your browser
├── com.flighttracker.plist  # Optional: macOS schedule
├── requirements.txt
└── .env.example
```

---

## Troubleshooting

**Empty digest / no flights found**
- Watch the log box in the UI while it runs.
- Confirm destination IATA codes are valid (IST, ESB, SAW, AYT, etc.).
- Google Flights works best on home/office IPs — VPN or cloud IPs may be blocked.

**Email not arriving**
- Use a Gmail App Password, not your regular login password.
- Gmail 2FA must be enabled before App Passwords work.
- Check `logs/tracker.log` for SMTP errors.

**Claude API errors**
- Check your API key at [console.anthropic.com](https://console.anthropic.com).

---

## License

MIT
