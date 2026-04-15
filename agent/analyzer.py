"""
agent/analyzer.py
Claude Haiku integration for:
  1. Parsing raw Google Flights text into structured flight dicts.
  2. Ranking by best-value score (price 60% + travel time 40%).
  3. Detecting cheapest date combo, price trends, and producing a narrative.
  4. Scanning mistake-fare site text for Canada→Turkey deals.
"""

import json
import logging
from typing import Any

import anthropic

import config

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# ── Main analysis entry-point ─────────────────────────────────────────────────

def analyze_flights(
    raw_results: dict,
    historical_baseline: dict,
) -> dict:
    """
    Parse scraped data with Claude Haiku and return an analysis dict:
    {
      ranked_flights: [...],
      best_pick: {...},
      cheapest_date_combo: { outbound, return, saving_vs_original },
      price_trend: "up|down|stable",
      narrative: "...",
      separate_ticket_deals: [...],
      positioning_options: [...],
    }
    """
    # Step 1: parse each raw text blob into flight dicts
    all_flights: list[dict] = []

    for item in raw_results.get("direct_and_onestop", []):
        flights = _parse_raw_text(
            raw_text=item["raw_text"],
            origin=item["origin"],
            destination=item["destination"],
            outbound_date=item["outbound_date"],
            return_date=item.get("return_date"),
        )
        all_flights.extend(flights)

    # Step 2: parse hub separate-ticket legs and compute combined price
    separate_ticket_deals: list[dict] = []
    for item in raw_results.get("hub_separate_tickets", []):
        leg1 = _parse_raw_text(
            item["leg1_raw"], item["origin"], item["hub"],
            item["outbound_date"], None,
        )
        leg2 = _parse_raw_text(
            item["leg2_raw"], item["hub"], item["destination"],
            item["outbound_date"], item.get("return_date"),
        )
        if leg1 and leg2:
            best_l1 = min(leg1, key=lambda f: f.get("price_cad", 9999))
            best_l2 = min(leg2, key=lambda f: f.get("price_cad", 9999))
            combined = best_l1["price_cad"] + best_l2["price_cad"]
            separate_ticket_deals.append({
                "origin": item["origin"],
                "hub": item["hub"],
                "destination": item["destination"],
                "outbound_date": item["outbound_date"],
                "return_date": item.get("return_date"),
                "leg1": best_l1,
                "leg2": best_l2,
                "combined_price_cad": combined,
            })

    # Step 3: parse positioning options
    positioning_options: list[dict] = []
    for item in raw_results.get("positioning", []):
        leg1 = _parse_raw_text(
            item["leg1_raw"], "YYZ", item["positioning_hub"],
            item["outbound_date"], None,
        )
        leg2 = _parse_raw_text(
            item["leg2_raw"], item["positioning_hub"], item["destination"],
            item["outbound_date"], item.get("return_date"),
        )
        if leg1 and leg2:
            best_l1 = min(leg1, key=lambda f: f.get("price_cad", 9999))
            best_l2 = min(leg2, key=lambda f: f.get("price_cad", 9999))
            total_price = best_l1["price_cad"] + best_l2["price_cad"]
            total_mins = (
                best_l1.get("total_duration_minutes", 0)
                + best_l2.get("total_duration_minutes", 0)
            )
            if total_mins <= config.MAX_TRAVEL_HOURS * 60:
                positioning_options.append({
                    "positioning_hub": item["positioning_hub"],
                    "destination": item["destination"],
                    "outbound_date": item["outbound_date"],
                    "return_date": item.get("return_date"),
                    "leg1": best_l1,
                    "leg2": best_l2,
                    "total_price_cad": total_price,
                    "total_duration_minutes": total_mins,
                })

    if not all_flights:
        logger.warning("No flights parsed — returning empty analysis")
        return _empty_analysis()

    # Step 4: rank all direct/1-stop flights + compare vs historical
    analysis = _rank_and_summarize(
        all_flights, historical_baseline, separate_ticket_deals, positioning_options
    )
    analysis["separate_ticket_deals"] = separate_ticket_deals
    analysis["positioning_options"] = positioning_options
    return analysis


# ── Mistake-fare scanner ──────────────────────────────────────────────────────

def scan_mistake_fares(pages: list[dict]) -> list[dict]:
    """
    Pass mistake-fare site text to Claude Haiku.
    Returns list of {route, price, airline, source_url} or empty list.
    """
    if not pages:
        return []

    combined = "\n\n---\n\n".join(
        f"SOURCE: {p['source_url']}\n{p['text']}" for p in pages
    )
    prompt = (
        "Find any deals departing from Canadian airports to Turkey "
        "(IST, ESB, SAW, AYT). "
        "Return a JSON array: [{\"route\": \"...\", \"price\": \"...\", "
        "\"airline\": \"...\", \"source_url\": \"...\"}] "
        "or an empty array [] if nothing is found. "
        "Only return the JSON array, no other text.\n\n"
        f"{combined[:20_000]}"
    )

    try:
        resp = _client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error(f"Mistake-fare scan failed: {exc}")
        return []


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_raw_text(
    raw_text: str,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str | None,
) -> list[dict]:
    """Ask Claude Haiku to extract flight dicts from a raw page-text blob."""
    max_dur_min = config.MAX_TRAVEL_HOURS * 60
    trip_label = (
        f"{origin}→{destination} on {outbound_date}"
        + (f" returning {return_date}" if return_date else " [one-way]")
    )

    prompt = f"""You are extracting flight data from raw Google Flights page text.

Route: {trip_label}
Passengers: {config.ADULTS} adult + {config.CHILDREN} child (age {config.CHILD_AGE})
Currency: CAD

Raw page text (may contain extraneous UI text):
---
{raw_text[:config.MAX_PAGE_TEXT_CHARS]}
---

Extract all flight options visible in the text. Return ONLY a JSON array (no other text) with up to {config.MAX_RESULTS_PER_ROUTE} results sorted by price ascending. Each element:
{{
  "airline": "string (e.g. 'Air Canada' or 'Turkish Airlines, Air Canada')",
  "departure_time": "HH:MM",
  "arrival_time": "HH:MM",
  "total_duration_minutes": integer,
  "stops": integer,
  "layover_airports": ["IATA", ...],
  "price_cad": number,
  "child_price_cad": number or null,
  "origin": "{origin}",
  "destination": "{destination}",
  "outbound_date": "{outbound_date}",
  "return_date": "{return_date or ''}",
  "google_flights_url": "string or empty string"
}}

Rules:
- Omit any flight where total_duration_minutes > {max_dur_min}.
- If price looks like USD, multiply by 1.37 to estimate CAD.
- If you cannot find real flight data, return [].
"""

    try:
        resp = _client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        flights = json.loads(raw)
        return [f for f in flights if isinstance(f, dict)]
    except Exception as exc:
        logger.error(f"Parse failed for {trip_label}: {exc}")
        return []


def _rank_and_summarize(
    flights: list[dict],
    historical: dict,
    separate_deals: list[dict],
    positioning: list[dict],
) -> dict:
    """
    Ask Claude Haiku to rank flights and produce the final analysis JSON.
    Also injects Firestore historical comparison.
    """
    flights_json = json.dumps(flights, indent=2)
    hist_json = json.dumps(historical, indent=2)

    prompt = f"""You are a flight deal analyst. Below are parsed flight options and historical price baselines.

FLIGHT OPTIONS:
{flights_json[:30_000]}

HISTORICAL BASELINES (route → min price ever seen):
{hist_json}

Scoring formula:
  best_value_score = {config.PRICE_WEIGHT} × (1 − normalized_price) + {config.TIME_WEIGHT} × (1 − normalized_time)
  where normalized = (value − min) / (max − min), 0 = best

Instructions:
1. Compute best_value_score for each flight.
2. Rank flights by score descending (limit to {config.MAX_RESULTS_PER_ROUTE} total).
3. Flag price_below_baseline=true if price_cad < historical baseline × {config.PRICE_DROP_THRESHOLD}.
4. Flag notable_child_discount=true if child_price_cad is present and > 10% less than adult price_cad.
5. Find the cheapest outbound/return date combo across all flights.
6. Set price_trend based on comparison to historical: "up", "down", or "stable".
7. Write a 2–3 sentence narrative summarising the best deal.

Return ONLY valid JSON (no other text):
{{
  "ranked_flights": [
    {{...flight fields..., "best_value_score": float, "price_below_baseline": bool, "notable_child_discount": bool}}
  ],
  "best_pick": {{...top-ranked flight}},
  "cheapest_date_combo": {{
    "outbound": "YYYY-MM-DD",
    "return": "YYYY-MM-DD",
    "price_cad": number,
    "saving_vs_original": "$X"
  }},
  "price_trend": "up|down|stable",
  "narrative": "string"
}}
"""

    try:
        resp = _client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        logger.error(f"Ranking failed: {exc}")
        return _empty_analysis()


def _empty_analysis() -> dict:
    return {
        "ranked_flights": [],
        "best_pick": {},
        "cheapest_date_combo": {
            "outbound": config.OUTBOUND_DATE,
            "return": config.RETURN_DATE,
            "price_cad": 0,
            "saving_vs_original": "$0",
        },
        "price_trend": "stable",
        "narrative": "No flight data could be retrieved in this run.",
        "separate_ticket_deals": [],
        "positioning_options": [],
    }
