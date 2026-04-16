"""
mailer/mailer.py
Build a rich HTML flight-digest email and send it via Gmail SMTP.

Note: this directory is named 'mailer/' (not 'email/') to avoid shadowing
Python's stdlib 'email' package, which smtplib depends on internally.
"""

import logging
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)

# ── Public entry-points ───────────────────────────────────────────────────────

def send_digest(
    analysis: dict,
    price_drops: list[dict],
    yesterday_prices: dict,
    mistake_fares: list[dict],
    is_morning: bool,
) -> None:
    """Build and send the HTML flight-digest email."""
    best = analysis.get("best_pick", {})
    best_price = best.get("price_cad", 0)
    today_str = datetime.now().strftime("%Y-%m-%d")

    subject = (
        f"✈️ YYZ→Turkey | Best: ${best_price:,.0f} CAD | {today_str}"
    )
    html = _build_html(
        analysis, price_drops, yesterday_prices, mistake_fares, is_morning
    )
    _send(subject, html, config.RECIPIENTS)


def send_error_email(error_message: str) -> None:
    """Send a plain-text error notification."""
    subject = (
        f"❌ Flight Tracker Error — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    body = f"The flight tracker encountered an error:\n\n{error_message}"
    try:
        _send_plain(subject, body, config.RECIPIENTS)
    except Exception as exc:
        logger.error(f"Failed to send error email: {exc}")


# ── HTML builder ──────────────────────────────────────────────────────────────

def _build_html(
    analysis: dict,
    price_drops: list[dict],
    yesterday_prices: dict,
    mistake_fares: list[dict],
    is_morning: bool,
) -> str:
    sections: list[str] = []

    # 1. Mistake Fare Alert (morning only)
    if is_morning and mistake_fares:
        sections.append(_section_mistake_fares(mistake_fares))

    # 2. Best Pick card
    best = analysis.get("best_pick", {})
    narrative = analysis.get("narrative", "")
    if best:
        sections.append(_section_best_pick(best, narrative))

    # 3. Top-5 routes table
    ranked = analysis.get("ranked_flights", [])
    if ranked:
        sections.append(_section_top5_table(ranked, yesterday_prices))

    # 4. Cheapest date combo callout
    cdc = analysis.get("cheapest_date_combo", {})
    if cdc and cdc.get("outbound") != config.OUTBOUND_DATE:
        sections.append(_section_cheapest_dates(cdc))

    # 5. Separate-ticket deal callout
    sep = analysis.get("separate_ticket_deals", [])
    if sep:
        best_sep = min(sep, key=lambda x: x.get("combined_price_cad", 9999))
        # Compare vs cheapest single-itinerary price
        best_single = ranked[0].get("price_cad", 9999) if ranked else 9999
        if best_sep.get("combined_price_cad", 9999) < best_single:
            sections.append(_section_separate_ticket(best_sep, best_single))

    # 6. Positioning flight option
    pos = analysis.get("positioning_options", [])
    if pos:
        best_pos = min(pos, key=lambda x: x.get("total_price_cad", 9999))
        if best_pos.get("total_duration_minutes", 9999) <= config.MAX_TRAVEL_HOURS * 60:
            sections.append(_section_positioning(best_pos))

    # 7. Footer
    next_run = _next_run_time()
    sections.append(_section_footer(next_run))

    body = "\n".join(sections)
    return _wrap_html(body)


# ── Section builders ──────────────────────────────────────────────────────────

def _section_mistake_fares(fares: list[dict]) -> str:
    rows = "".join(
        f"""<tr>
          <td style="padding:6px 10px">{f.get('route','?')}</td>
          <td style="padding:6px 10px">{f.get('price','?')}</td>
          <td style="padding:6px 10px">{f.get('airline','?')}</td>
          <td style="padding:6px 10px">
            <a href="{f.get('source_url','#')}">Source</a>
          </td>
        </tr>"""
        for f in fares
    )
    return f"""
<div style="background:#fff3cd;border-left:5px solid #ff6b00;padding:16px;margin:16px 0;border-radius:4px">
  <h2 style="margin:0 0 8px;color:#c44900">🚨 Mistake Fare Alert</h2>
  <table style="border-collapse:collapse;width:100%">
    <thead>
      <tr style="background:#ffe0b2">
        <th style="padding:6px 10px;text-align:left">Route</th>
        <th style="padding:6px 10px;text-align:left">Price</th>
        <th style="padding:6px 10px;text-align:left">Airline</th>
        <th style="padding:6px 10px;text-align:left">Link</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def _section_best_pick(best: dict, narrative: str) -> str:
    airline = best.get("airline", "—")
    origin = best.get("origin", "?")
    dest = best.get("destination", "?")
    price = best.get("price_cad", 0)
    dur = _fmt_duration(best.get("total_duration_minutes", 0))
    stops = best.get("stops", 0)
    out_date = best.get("outbound_date", "")
    ret_date = best.get("return_date", "")
    gf_url = best.get("google_flights_url", "")

    buy_btn = (
        f'<a href="{gf_url}" target="_blank" '
        f'style="display:inline-block;margin-top:14px;padding:12px 24px;'
        f'background:#1a73e8;color:#fff;font-weight:bold;font-size:15px;'
        f'text-decoration:none;border-radius:6px">🛒 Book on Google Flights →</a>'
        if gf_url else ""
    )

    return f"""
<div style="background:#e8f5e9;border:2px solid #34a853;padding:20px;margin:16px 0;border-radius:8px">
  <h2 style="margin:0 0 4px;color:#1e7e34">⭐ Best Pick</h2>
  <p style="font-size:22px;font-weight:bold;margin:8px 0;color:#1b5e20">
    {origin} → {dest} &nbsp;|&nbsp; ${price:,.0f} CAD
  </p>
  <p style="margin:4px 0;color:#555">
    {airline} &nbsp;·&nbsp; {dur} &nbsp;·&nbsp; {stops} stop{'s' if stops != 1 else ''}
    &nbsp;·&nbsp; {out_date} → {ret_date}
  </p>
  <p style="margin:12px 0 4px;font-style:italic;color:#333">{narrative}</p>
  {buy_btn}
</div>"""


def _section_top5_table(flights: list[dict], yesterday: dict) -> str:
    rows = ""
    for f in flights[:5]:
        route = f"{f.get('origin','?')}→{f.get('destination','?')}"
        airline = f.get("airline", "—")
        dur = _fmt_duration(f.get("total_duration_minutes", 0))
        stops = f.get("stops", 0)
        price = f.get("price_cad", 0)
        yest_price = yesterday.get(f"{f.get('origin','?')}-{f.get('destination','?')}")
        if yest_price:
            if price < yest_price * 0.99:
                trend = "🟢"
            elif price > yest_price * 1.01:
                trend = "↑"
            else:
                trend = "↓"
            trend_cell = f"${yest_price:,.0f} {trend}"
        else:
            trend_cell = "—"
        gf_url = f.get("google_flights_url", "")
        link = f'<a href="{gf_url}">🔗</a>' if gf_url else ""

        rows += f"""<tr>
          <td style="padding:7px 10px">{route}</td>
          <td style="padding:7px 10px">{airline}</td>
          <td style="padding:7px 10px">{dur}</td>
          <td style="padding:7px 10px">{stops}</td>
          <td style="padding:7px 10px;font-weight:bold">${price:,.0f}</td>
          <td style="padding:7px 10px;color:#777">{trend_cell}</td>
          <td style="padding:7px 10px">{link}</td>
        </tr>"""

    return f"""
<h2 style="color:#1a73e8;margin:20px 0 8px">📋 Top Routes</h2>
<table style="border-collapse:collapse;width:100%;font-size:14px">
  <thead>
    <tr style="background:#f1f3f4;text-align:left">
      <th style="padding:7px 10px">Route</th>
      <th style="padding:7px 10px">Airline</th>
      <th style="padding:7px 10px">Duration</th>
      <th style="padding:7px 10px">Stops</th>
      <th style="padding:7px 10px">Price (CAD)</th>
      <th style="padding:7px 10px">vs Yesterday</th>
      <th style="padding:7px 10px">Link</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""


def _section_cheapest_dates(cdc: dict) -> str:
    out = cdc.get("outbound", config.OUTBOUND_DATE)
    ret = cdc.get("return", config.RETURN_DATE)
    price = cdc.get("price_cad", 0)
    saving = cdc.get("saving_vs_original", "")
    return f"""
<div style="background:#e3f2fd;border-left:4px solid #1a73e8;padding:14px;margin:16px 0;border-radius:4px">
  <h3 style="margin:0 0 6px;color:#1a73e8">📅 Cheapest Date Combo</h3>
  <p style="margin:4px 0">Fly <strong>{out}</strong> → return <strong>{ret}</strong>
    for <strong>${price:,.0f} CAD</strong>
    {f'— saving <strong>{saving}</strong> vs original dates' if saving else ''}</p>
</div>"""


def _section_separate_ticket(deal: dict, best_single: float) -> str:
    saving = round(best_single - deal.get("combined_price_cad", 0), 2)
    return f"""
<div style="background:#f3e5f5;border-left:4px solid #9c27b0;padding:14px;margin:16px 0;border-radius:4px">
  <h3 style="margin:0 0 6px;color:#6a1b9a">🎫 Separate-Ticket Deal</h3>
  <p style="margin:4px 0">
    <strong>{deal.get('origin','?')} → {deal.get('hub','?')}</strong>
    + <strong>{deal.get('hub','?')} → {deal.get('destination','?')}</strong>
    = <strong>${deal.get('combined_price_cad',0):,.0f} CAD</strong>
    (saves ~${saving:,.0f} vs single itinerary)
  </p>
  <p style="margin:4px 0;color:#555;font-size:13px">
    ⚠️ Separate tickets — allow extra connection time and note separate baggage rules.
  </p>
</div>"""


def _section_positioning(pos: dict) -> str:
    dur = _fmt_duration(pos.get("total_duration_minutes", 0))
    return f"""
<div style="background:#fce4ec;border-left:4px solid #e91e63;padding:14px;margin:16px 0;border-radius:4px">
  <h3 style="margin:0 0 6px;color:#880e4f">🛫 Positioning Flight Option</h3>
  <p style="margin:4px 0">
    YYZ → <strong>{pos.get('positioning_hub','?')}</strong>
    → <strong>{pos.get('destination','?')}</strong>
    = <strong>${pos.get('total_price_cad',0):,.0f} CAD</strong>
    · {dur} total travel time
  </p>
  <p style="margin:4px 0;color:#555;font-size:13px">
    ⚠️ Positioning legs are on separate tickets.
  </p>
</div>"""


def _section_footer(next_run: str) -> str:
    return f"""
<hr style="margin:24px 0;border:none;border-top:1px solid #e0e0e0">
<p style="color:#888;font-size:12px;margin:4px 0">
  Next check: {next_run} &nbsp;|&nbsp;
  Prices shown for {config.ADULTS} adult + {config.CHILDREN} child
  (age {config.CHILD_AGE}), economy class, round-trip, currency CAD.
</p>
<p style="color:#aaa;font-size:11px;margin:4px 0">
  Powered by Claude Haiku + Playwright • flight-tracker-agent
</p>"""


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Flight Digest</title>
</head>
<body style="font-family:Arial,Helvetica,sans-serif;max-width:760px;margin:0 auto;padding:16px;color:#222;background:#fff">
  <h1 style="color:#1a73e8;margin-bottom:4px">✈️ YYZ → Turkey Flight Digest</h1>
  <p style="color:#888;margin-top:0">{datetime.now().strftime('%A, %B %d %Y — %H:%M %Z')}</p>
  {body}
</body>
</html>"""


# ── SMTP sender ───────────────────────────────────────────────────────────────

def _send(subject: str, html_body: str, recipients: list[str]) -> None:
    if not config.GMAIL_USER or not config.GMAIL_APP_PASSWORD:
        logger.error("GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping send.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_USER, recipients, msg.as_string())

    logger.info(f"Digest sent to {recipients}")


def _send_plain(subject: str, body: str, recipients: list[str]) -> None:
    if not config.GMAIL_USER or not config.GMAIL_APP_PASSWORD:
        return

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_USER, recipients, msg.as_string())


# ── Utilities ─────────────────────────────────────────────────────────────────

def _fmt_duration(minutes: int) -> str:
    if not minutes:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m"


def _next_run_time() -> str:
    """Return estimated next scheduled run time string."""
    now = datetime.now()
    if now.hour < 19:
        nxt = now.replace(hour=19, minute=0, second=0, microsecond=0)
    else:
        nxt = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    return nxt.strftime("%A %b %d at %-I:%M %p")
