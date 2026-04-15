# ✈️ flight-tracker-agent

Twice-daily flight price tracker for **YYZ / YHM / YTZ → IST / ESB / SAW** (Turkey).

Runs via **GitHub Actions**, scrapes **Google Flights** with Playwright, analyses results with **Claude Haiku**, stores history in **Firestore**, and emails a rich HTML digest.

---

## Features

| Feature | Detail |
|---------|--------|
| Routes | All 3 × 3 origin→destination combos |
| Flexibility | Outbound ±3 days (Jul 15–21), Return ±3 days (Aug 19–25) |
| Search types | Direct + 1-stop · Hub separate-ticket · Positioning via JFK/EWR |
| Analysis | Claude Haiku ranks by value score (price 60% + time 40%) |
| Price history | Firestore — detects drops, shows ↑↓🟢 trend vs yesterday |
| Mistake fares | Morning scan of secretflying.com + airfarewatchdog.com |
| Schedule | 8 AM + 6 PM Toronto (GitHub Actions cron) |
| Email | HTML digest with best pick, top-5 table, date-combo callout |

---

## Quick start (local)

### Prerequisites

```bash
python3.11 -m pip install -r requirements.txt
playwright install chromium
```

### Environment variables

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD,
# FIRESTORE_KEY_PATH, FIRESTORE_PROJECT
```

### Firestore setup

1. Create a GCP project and enable the Firestore API.
2. Create a service account with **Cloud Datastore User** role.
3. Download the JSON key → save as `firestore-key.json` (or set `FIRESTORE_KEY_PATH`).
4. Set `FIRESTORE_PROJECT` to your GCP project ID.

The agent works without Firestore (logs a warning and skips price history).

### Run

```bash
python main.py
```

---

## GitHub Actions setup

### 1. Fork / push this repo to GitHub

```bash
git init
git add -A
git commit -m "initial commit"
git remote add origin git@github.com:bariscoach/flight-tracker-agent.git
git push -u origin main
```

### 2. Add repository secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** for each:

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_USER` | Gmail address used to send emails |
| `GMAIL_APP_PASSWORD` | Gmail [App Password](https://support.google.com/accounts/answer/185833) |
| `FIRESTORE_KEY` | Full JSON content of your service-account key file |
| `FIRESTORE_PROJECT` | GCP project ID |

### 3. Enable Actions

The workflow at `.github/workflows/tracker.yml` runs automatically at:
- **13:00 UTC** → 8 AM Toronto (EST) / 9 AM (EDT)
- **23:00 UTC** → 6 PM Toronto (EST) / 7 PM (EDT)

You can also trigger it manually from the **Actions** tab → **Run workflow**.

---

## Project structure

```
flight-tracker-agent/
├── .github/
│   └── workflows/
│       └── tracker.yml        # cron + Playwright CI
├── scraper/
│   └── google_flights.py      # Playwright scraper
├── agent/
│   └── analyzer.py            # Claude Haiku parser + ranker
├── mailer/                    # Named 'mailer/' (not 'email/') to avoid
│   └── mailer.py              #   shadowing Python's stdlib email package
├── data/
│   └── firestore_client.py    # Firestore price history
├── main.py                    # Orchestrator
├── config.py                  # All constants — edit here only
├── requirements.txt
├── .env.example
├── CLAUDE.md
└── README.md
```

> **Note:** The email directory is named `mailer/` rather than `email/` because
> Python's `smtplib` module internally imports `email.utils`, `email.mime`, etc.
> from the standard library. A local `email/` package would shadow those and
> cause `smtplib` to break.

---

## Configuration (`config.py`)

Key values you may want to tweak before running:

```python
ORIGINS            = ["YYZ", "YHM", "YTZ"]
DESTINATIONS       = ["IST", "ESB", "SAW"]
OUTBOUND_DATE      = "2026-07-18"   # ±3 days
RETURN_DATE        = "2026-08-22"   # ±3 days
RECIPIENTS         = ["baris@email.com", "elif@email.com"]  # ← update this!
ACTIVE_HUBS        = HUB_AIRPORTS[:5]   # AMS, LHR, FRA, CDG, MUC
MAX_TRAVEL_HOURS   = 20
```

---

## Email format

1. 🚨 **Mistake Fare Alert** — morning run only, if deals found
2. ⭐ **Best Pick card** — highlighted with Claude's narrative
3. 📋 **Top 5 routes table** — airline · duration · stops · price (CAD) · vs yesterday (↑↓🟢)
4. 📅 **Cheapest date combo** — if different from original dates, shows saving
5. 🎫 **Separate-ticket deal** — if combined legs are cheaper than a single itinerary
6. 🛫 **Positioning flight option** — YYZ→JFK/EWR + JFK/EWR→destination (≤20 h)
7. Footer — next check time · passenger info

---

## Secrets reference

| Variable | Where used |
|----------|-----------|
| `ANTHROPIC_API_KEY` | Claude Haiku API calls |
| `GMAIL_USER` | SMTP login + From address |
| `GMAIL_APP_PASSWORD` | SMTP authentication |
| `FIRESTORE_KEY` | Service-account JSON (GitHub secret, written to file in CI) |
| `FIRESTORE_PROJECT` | GCP project ID for Firestore |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No flights in email | Google Flights DOM may have changed; check `SCRAPER_RESULTS_WAIT_MS` in `config.py` |
| SMTP error | Ensure 2-FA is on and you're using a Gmail App Password (not your main password) |
| Firestore error | Check service-account JSON is valid and has Datastore User role |
| Playwright timeout | Increase `SCRAPER_PAGE_TIMEOUT_MS` in `config.py` |

---

## License

MIT
