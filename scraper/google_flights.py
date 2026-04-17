"""
scraper/google_flights.py
Playwright (headless Chromium) scraper for Google Flights.

Each call creates a fresh browser context (clears cookies between sessions
to avoid Google's price-inflation for repeat visitors).

Returns raw page-text per search; Claude Haiku in agent/analyzer.py
converts that text into structured flight dicts.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
)

import config

logger = logging.getLogger(__name__)

# ── User-agent pool ───────────────────────────────────────────────────────────
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
]


# ── Public entry-point ────────────────────────────────────────────────────────

async def scrape_all(
    outbound_dates: list[str],
    return_dates: list[str],
) -> dict:
    """
    Run all searches and return a results dict with three keys:
      - direct_and_onestop  : list of raw-text dicts for main O/D combos
      - hub_separate_tickets: list of raw-text dict pairs (leg1 + leg2)
      - positioning         : list of raw-text dict pairs (feeder + longhaul)
    """
    results: dict = {
        "direct_and_onestop": [],
        "hub_separate_tickets": [],
        "positioning": [],
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=config.PLAYWRIGHT_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
            ],
        )

        try:
            # 1. Direct + 1-stop: all origin × destination × date combos
            #    We search all flexibility dates for main routes to find cheapest day.
            for origin in config.ORIGINS:
                for dest in config.DESTINATIONS:
                    for out_d in outbound_dates:
                        for ret_d in return_dates:
                            raw = await _scrape_one(
                                browser, origin, dest,
                                out_d, ret_d,
                                one_way=False,
                            )
                            if raw:
                                results["direct_and_onestop"].append({
                                    "origin": origin,
                                    "destination": dest,
                                    "outbound_date": out_d,
                                    "return_date": ret_d,
                                    "raw_text": raw,
                                    "search_type": "direct_or_onestop",
                                })
                            await asyncio.sleep(
                                random.uniform(
                                    config.SCRAPER_MIN_DELAY_S,
                                    config.SCRAPER_MAX_DELAY_S,
                                )
                            )

            # 2. Hub separate-ticket: main outbound date only (top 5 hubs)
            main_out = outbound_dates[len(outbound_dates) // 2]  # middle = original date
            main_ret = return_dates[len(return_dates) // 2]

            for origin in config.ORIGINS:
                for hub in config.ACTIVE_HUBS:
                    for dest in config.DESTINATIONS:
                        leg1 = await _scrape_one(
                            browser, origin, hub,
                            main_out, None, one_way=True,
                        )
                        await asyncio.sleep(random.uniform(2, 4))
                        leg2 = await _scrape_one(
                            browser, hub, dest,
                            main_out, main_ret, one_way=False,
                        )
                        if leg1 and leg2:
                            results["hub_separate_tickets"].append({
                                "origin": origin,
                                "hub": hub,
                                "destination": dest,
                                "outbound_date": main_out,
                                "return_date": main_ret,
                                "leg1_raw": leg1,
                                "leg2_raw": leg2,
                                "search_type": "hub_separate_ticket",
                            })
                        await asyncio.sleep(random.uniform(2, 4))

            # 3. Positioning: YYZ → JFK/EWR + JFK/EWR → IST/ESB/SAW
            for pos_hub in config.POSITIONING_HUBS:
                for dest in config.DESTINATIONS:
                    leg1 = await _scrape_one(
                        browser, "YYZ", pos_hub,
                        main_out, None, one_way=True,
                    )
                    await asyncio.sleep(random.uniform(2, 4))
                    leg2 = await _scrape_one(
                        browser, pos_hub, dest,
                        main_out, main_ret, one_way=False,
                    )
                    if leg1 and leg2:
                        results["positioning"].append({
                            "origin": "YYZ",
                            "positioning_hub": pos_hub,
                            "destination": dest,
                            "outbound_date": main_out,
                            "return_date": main_ret,
                            "leg1_raw": leg1,
                            "leg2_raw": leg2,
                            "search_type": "positioning",
                        })
                    await asyncio.sleep(random.uniform(2, 4))

        finally:
            await browser.close()

    return results


# ── Mistake-fare scraper (uses requests, not Playwright) ──────────────────────

def scrape_mistake_fare_sites() -> list[dict]:
    """Fetch text from mistake-fare aggregator sites for Claude to scan."""
    import requests
    from bs4 import BeautifulSoup

    pages = []
    headers = {"User-Agent": random.choice(_USER_AGENTS)}

    for url in config.MISTAKE_FARE_SOURCES:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            text = BeautifulSoup(resp.text, "html.parser").get_text(
                separator=" ", strip=True
            )
            pages.append({"source_url": url, "text": text[:15_000]})
            logger.info(f"Fetched mistake-fare source: {url}")
        except Exception as exc:
            logger.warning(f"Could not fetch {url}: {exc}")

    return pages


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _scrape_one(
    browser: Browser,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: Optional[str],
    one_way: bool,
) -> Optional[str]:
    """Open a fresh context, navigate Google Flights, return extracted text."""
    ctx = await _new_context(browser)
    page = await ctx.new_page()
    try:
        url = _build_url(origin, destination, outbound_date, return_date, one_way)
        logger.info(
            f"Searching {origin}→{destination}  {outbound_date}"
            + (f"/{return_date}" if return_date else " [one-way]")
        )
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=config.SCRAPER_PAGE_TIMEOUT_MS,
        )
        await _dismiss_overlays(page)
        # Extra settle time for JS rendering
        await asyncio.sleep(config.SCRAPER_RESULTS_WAIT_MS / 1000)
        text = await _extract_text(page)
        logger.info(f"Extracted {len(text)} chars | preview: {text[:200]!r}")
        return text or None
    except Exception as exc:
        logger.error(f"Scrape failed {origin}→{destination}: {exc}")
        return None
    finally:
        await page.close()
        await ctx.close()


async def _new_context(browser: Browser) -> BrowserContext:
    ctx = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        locale="en-CA",
        timezone_id="America/Toronto",
        viewport={"width": 1280, "height": 800},
        extra_http_headers={"Accept-Language": "en-CA,en;q=0.9"},
    )
    await ctx.clear_cookies()
    return ctx


def _build_url(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: Optional[str],
    one_way: bool,
) -> str:
    """
    Build a Google Flights direct-search URL.

    Hash format:  #flt={orig}.{dest}.{out}[*{dest}.{orig}.{ret}];c:CAD;e:{adults};px:{children};sd:1;t:{r|o}
    """
    adults = config.ADULTS
    children = config.CHILDREN

    if one_way or not return_date:
        trip = f"{origin}.{destination}.{outbound_date}"
        trip_type = "o"
    else:
        trip = (
            f"{origin}.{destination}.{outbound_date}"
            f"*{destination}.{origin}.{return_date}"
        )
        trip_type = "r"

    params = f"c:CAD;e:{adults};px:{children};sd:1;t:{trip_type}"
    return f"https://www.google.com/flights?hl=en&gl=ca&curr=CAD#flt={trip};{params}"


async def _dismiss_overlays(page: Page) -> None:
    """Click away cookie consent / GDPR banners if present."""
    selectors = [
        'button[aria-label*="Reject all"]',
        'button[aria-label*="Accept all"]',
        '[aria-label*="I agree"]',
        'button:has-text("Reject all")',
        'button:has-text("Accept all")',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await asyncio.sleep(1)
                return
        except Exception:
            pass


async def _extract_text(page: Page) -> str:
    """
    Extract the flight-results text from the page.
    Tries progressively broader selectors; falls back to full body text.
    """
    candidates = [
        '[role="main"]',
        "main",
        "body",
    ]
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if await el.count() and await el.is_visible(timeout=2000):
                text = await el.inner_text()
                if text and len(text) > 200:
                    return text[: config.MAX_PAGE_TEXT_CHARS]
        except Exception:
            continue
    return ""


# ── Date-range helper (used by main.py) ──────────────────────────────────────

def build_date_range(base_date: str, flex_days: int) -> list[str]:
    """Return sorted list of YYYY-MM-DD strings within ±flex_days of base_date."""
    base = datetime.strptime(base_date, "%Y-%m-%d")
    return [
        (base + timedelta(days=d)).strftime("%Y-%m-%d")
        for d in range(-flex_days, flex_days + 1)
    ]
