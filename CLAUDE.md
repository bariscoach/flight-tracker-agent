# CLAUDE.md — Session instructions for flight-tracker-agent

## Auto git commit + push at end of every session

At the end of every coding session, automatically:
1. `git add -A`
2. `git commit -m "chore: end-of-session auto-commit [Claude]"`
3. `git push origin main`

Do this without asking for confirmation unless there are merge conflicts or the push would force-push.

## Project overview

Python 3.11 flight price tracker:
- Scrapes Google Flights via Playwright (headless Chromium)
- Analyses with Claude Haiku (`claude-haiku-4-5-20251001`)
- Stores price history in Firestore
- Sends HTML digest via Gmail SMTP
- Runs twice daily via GitHub Actions (8 AM + 6 PM Toronto)

## Key files

| File | Purpose |
|------|---------|
| `config.py` | All constants — edit here, nowhere else |
| `scraper/google_flights.py` | Playwright scraper |
| `agent/analyzer.py` | Claude Haiku parsing + ranking |
| `mailer/mailer.py` | HTML email builder + SMTP sender |
| `data/firestore_client.py` | Firestore price history |
| `main.py` | Orchestrator |
| `.github/workflows/tracker.yml` | GitHub Actions cron |

## Style conventions

- Python 3.11+, type hints where practical
- `logging` (not `print`) for all output
- All secrets via environment variables / `.env`
- No hardcoded strings outside `config.py`
