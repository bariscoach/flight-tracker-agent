"""
config.py — All constants and environment variables for flight-tracker-agent.
All hardcoded strings live here. Do not scatter magic values elsewhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Routes ────────────────────────────────────────────────────────────────────
ORIGINS = ["YYZ", "YHM", "YTZ"]
DESTINATIONS = ["IST", "ESB", "SAW"]

# ── Travel dates & flexibility ────────────────────────────────────────────────
OUTBOUND_DATE = "2026-07-18"          # ±3 days → Jul 15–21
RETURN_DATE = "2026-08-22"            # ±3 days → Aug 19–25
OUTBOUND_FLEXIBILITY_DAYS = 3
RETURN_FLEXIBILITY_DAYS = 3

# ── Passengers ────────────────────────────────────────────────────────────────
ADULTS = 1
CHILDREN = 1
CHILD_AGE = 7
CABIN = "economy"

# ── Travel constraint ─────────────────────────────────────────────────────────
MAX_TRAVEL_HOURS = 20
MAX_RESULTS_PER_ROUTE = 5

# ── Hub airports for multi-city / separate-ticket searches ────────────────────
HUB_AIRPORTS = [
    "AMS", "LHR", "FRA", "CDG", "MUC",
    "VIE", "WAW", "BUD", "PRG", "OTP",
    "SOF", "ARN", "HEL",
]
# Limit active hub searches to top hubs to keep runtime reasonable
ACTIVE_HUBS = HUB_AIRPORTS[:5]   # AMS, LHR, FRA, CDG, MUC

# ── Positioning hubs (Porter / Air Canada feeder) ─────────────────────────────
POSITIONING_HUBS = ["JFK", "EWR"]

# ── Email ─────────────────────────────────────────────────────────────────────
RECIPIENTS = ["baris@email.com", "elif@email.com"]   # ← update before first run

# ── Claude ───────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── Gmail SMTP ────────────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ── Firestore ─────────────────────────────────────────────────────────────────
FIRESTORE_KEY_PATH = os.getenv("FIRESTORE_KEY_PATH", "firestore-key.json")
FIRESTORE_COLLECTION = "flight_prices"
FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "flight-tracker")

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
