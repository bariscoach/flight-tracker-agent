"""
config.py — All constants and environment variables for flight-tracker-agent.
All hardcoded strings live here. Do not scatter magic values elsewhere.

Priority order for each setting:
  1. user_config.json  (written by the web UI at localhost:5050)
  2. Environment variables / .env file
  3. Hard-coded defaults below
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Load user_config.json (set via web UI) ────────────────────────────────────
_USER_CONFIG: dict = {}
_USER_CONFIG_PATH = Path(__file__).parent / "user_config.json"
if _USER_CONFIG_PATH.exists():
    try:
        _USER_CONFIG = json.loads(_USER_CONFIG_PATH.read_text())
    except Exception:
        pass


def _str(key: str, default: str = "") -> str:
    """Read a string setting: user_config → env var → default."""
    return _USER_CONFIG.get(key) or os.getenv(key) or default


def _int(key: str, default: int) -> int:
    val = _USER_CONFIG.get(key)
    if val is not None:
        return int(val)
    env = os.getenv(key)
    return int(env) if env else default


def _list(key: str, default: list) -> list:
    val = _USER_CONFIG.get(key)
    return val if isinstance(val, list) and val else default


# ── Routes ────────────────────────────────────────────────────────────────────
ORIGINS = _list("ORIGINS", ["YYZ"])
DESTINATIONS = _list("DESTINATIONS", ["IST", "ESB", "SAW"])

# ── Travel dates & flexibility ────────────────────────────────────────────────
OUTBOUND_DATE = _str("OUTBOUND_DATE", "2026-07-18")
RETURN_DATE = _str("RETURN_DATE", "2026-08-22")
OUTBOUND_FLEXIBILITY_DAYS = _int("OUTBOUND_FLEXIBILITY_DAYS", 2)
RETURN_FLEXIBILITY_DAYS = _int("RETURN_FLEXIBILITY_DAYS", 2)

# ── Passengers ────────────────────────────────────────────────────────────────
ADULTS = _int("ADULTS", 1)
CHILDREN = _int("CHILDREN", 1)
CHILD_AGE = _int("CHILD_AGE", 7)
CABIN = "economy"

# ── Travel constraint ─────────────────────────────────────────────────────────
MAX_TRAVEL_HOURS = _int("MAX_TRAVEL_HOURS", 20)
MAX_RESULTS_PER_ROUTE = 5

# ── Hub airports for multi-city / separate-ticket searches ────────────────────
HUB_AIRPORTS = [
    "AMS", "LHR", "FRA", "CDG", "MUC",
    "VIE", "WAW", "BUD", "PRG", "OTP",
    "SOF", "ARN", "HEL",
]
ACTIVE_HUBS = HUB_AIRPORTS[:_int("ACTIVE_HUBS_COUNT", 3)]

# ── Positioning hubs (Porter / Air Canada feeder) ─────────────────────────────
POSITIONING_HUBS = ["JFK", "EWR"]

# ── Email ─────────────────────────────────────────────────────────────────────
RECIPIENTS = _list("RECIPIENTS", ["barishiz@gmail.com", "elifohiz@gmail.com"])

# ── Claude ───────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_API_KEY = _str("ANTHROPIC_API_KEY")

# ── Gmail SMTP ────────────────────────────────────────────────────────────────
GMAIL_USER = _str("GMAIL_USER")
GMAIL_APP_PASSWORD = _str("GMAIL_APP_PASSWORD")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ── Firestore ─────────────────────────────────────────────────────────────────
FIRESTORE_KEY_PATH = _str("FIRESTORE_KEY_PATH", "firestore-key.json")
FIRESTORE_COLLECTION = "flight_prices"
FIRESTORE_PROJECT = _str("FIRESTORE_PROJECT", "flight-tracker")

# ── Mistake-fare monitoring (morning run only) ────────────────────────────────
MISTAKE_FARE_SOURCES = [
    "https://www.secretflying.com/posts/category/canada/",
    "https://www.airfarewatchdog.com/cheap-flights/to-istanbul-ist/",
]

# ── Scraper behaviour ─────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = True
SCRAPER_PAGE_TIMEOUT_MS = 60_000
SCRAPER_RESULTS_WAIT_MS = 7_000      # extra wait after DOM ready
SCRAPER_MIN_DELAY_S = 2.0            # polite delay between requests
SCRAPER_MAX_DELAY_S = 5.0
MAX_PAGE_TEXT_CHARS = 60_000

# ── Scoring weights ───────────────────────────────────────────────────────────
PRICE_WEIGHT = 0.60
TIME_WEIGHT = 0.40

# ── Price-drop threshold ──────────────────────────────────────────────────────
PRICE_DROP_THRESHOLD = 0.95   # flag if current < baseline × 0.95
