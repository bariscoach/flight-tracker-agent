"""
main.py — Orchestrator for flight-tracker-agent.

Flow:
  1. Build date ranges (outbound ±3 days, return ±3 days)
  2. Scrape Google Flights for all routes + hubs + positioning
  3. Parse & rank with Claude Haiku
  4. Read Firestore historical baselines; detect price drops
  5. Save new prices to Firestore
  6. Scrape mistake-fare sites (morning run only)
  7. Build & send HTML digest email
  8. On any unhandled error: send plain-text error email
"""

import asyncio
import logging
import sys
from datetime import datetime

import config
from scraper.google_flights import scrape_all, build_date_range, scrape_mistake_fare_sites
from agent.analyzer import analyze_flights, scan_mistake_fares
from data.firestore_client import FirestoreClient
from mailer.mailer import send_digest, send_error_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("=== flight-tracker-agent starting ===")
    now = datetime.now()
    is_morning = now.hour >= 6   # 7 AM run (12:00 UTC) vs 7 PM run (00:00 UTC)

    # ── 1. Build date ranges ─────────────────────────────────────────────────
    outbound_dates = build_date_range(config.OUTBOUND_DATE, config.OUTBOUND_FLEXIBILITY_DAYS)
    return_dates = build_date_range(config.RETURN_DATE, config.RETURN_FLEXIBILITY_DAYS)
    logger.info(
        f"Outbound range: {outbound_dates[0]}…{outbound_dates[-1]} "
        f"({len(outbound_dates)} dates)"
    )
    logger.info(
        f"Return range:   {return_dates[0]}…{return_dates[-1]} "
        f"({len(return_dates)} dates)"
    )

    # ── 2. Scrape Google Flights ──────────────────────────────────────────────
    logger.info("Starting Google Flights scrape…")
    raw_results = await scrape_all(outbound_dates, return_dates)

    total_raw = (
        len(raw_results["direct_and_onestop"])
        + len(raw_results["hub_separate_tickets"])
        + len(raw_results["positioning"])
    )
    logger.info(f"Scrape complete: {total_raw} raw result sets collected.")

    # ── 3. Load Firestore historical baselines ────────────────────────────────
    fs = FirestoreClient()
    historical = fs.get_all_baselines()
    yesterday_prices = fs.get_yesterday_prices()
    logger.info(f"Loaded {len(historical)} historical baselines from Firestore.")

    # ── 4. Parse & rank with Claude Haiku ────────────────────────────────────
    logger.info("Analysing with Claude Haiku…")
    analysis = analyze_flights(raw_results, historical)
    ranked = analysis.get("ranked_flights", [])
    best = analysis.get("best_pick", {})
    logger.info(
        f"Analysis done: {len(ranked)} ranked flights, "
        f"best=${best.get('price_cad',0):,.0f} CAD on "
        f"{best.get('origin','?')}→{best.get('destination','?')}"
    )

    # ── 5. Detect price drops & save to Firestore ─────────────────────────────
    price_drops = fs.detect_price_drops(ranked, historical)
    if price_drops:
        logger.info(f"🔻 {len(price_drops)} price drop(s) detected.")
    fs.save_prices(ranked)

    # ── 6. Mistake-fare monitoring (morning only) ─────────────────────────────
    mistake_fares: list[dict] = []
    if is_morning:
        logger.info("Morning run — scanning mistake-fare sites…")
        pages = scrape_mistake_fare_sites()
        mistake_fares = scan_mistake_fares(pages)
        if mistake_fares:
            logger.info(f"🚨 Found {len(mistake_fares)} mistake fare(s)!")
        else:
            logger.info("No mistake fares found.")

    # ── 7. Send digest email ──────────────────────────────────────────────────
    logger.info("Sending digest email…")
    send_digest(
        analysis=analysis,
        price_drops=price_drops,
        yesterday_prices=yesterday_prices,
        mistake_fares=mistake_fares,
        is_morning=is_morning,
    )
    logger.info("=== flight-tracker-agent finished ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        logger.exception("Unhandled error — sending error email.")
        send_error_email(str(exc))
        sys.exit(1)
