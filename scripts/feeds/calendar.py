#!/usr/bin/env python3
"""
economic_calendar.py — Economic Calendar for TradeDesk
======================================================
Aggregates macro events, earnings dates, and options expiry into a single
sorted event feed with impact ratings and urgency warnings.

Usage:
    python scripts/economic_calendar.py                  # macro events only
    python scripts/economic_calendar.py AAPL             # macro + AAPL earnings
    python scripts/economic_calendar.py AAPL --days 14   # 14-day lookahead
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Allow running as script or module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_earnings

logger = logging.getLogger(__name__)

# High-impact event keywords — matched case-insensitively against event names
HIGH_IMPACT_KEYWORDS = [
    "fed rate", "interest rate decision", "federal funds rate",
    "fomc", "cpi", "consumer price index",
    "nonfarm payrolls", "non-farm payrolls", "nfp",
    "pce price index", "pce prices", "core pce",
    "gdp growth rate", "gdp",
    "fed press conference", "fed chair",
]

MEDIUM_IMPACT_KEYWORDS = [
    "ism manufacturing", "ism services", "ism non-manufacturing",
    "retail sales", "jolts", "ppi", "producer price index",
    "unemployment rate", "initial jobless claims",
    "housing starts", "building permits",
    "consumer confidence", "michigan consumer sentiment",
    "durable goods", "industrial production",
    "fed speaker", "fed governor", "fed president",
]


def _classify_impact(event_name: str, te_importance: str = "") -> str:
    """Classify event impact as High/Medium/Low."""
    name_lower = event_name.lower()
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in name_lower:
            return "High"
    for kw in MEDIUM_IMPACT_KEYWORDS:
        if kw in name_lower:
            return "Medium"
    # Fall back to tradingeconomics importance if available
    te = te_importance.lower().strip()
    if te in ("high", "3"):
        return "High"
    if te in ("medium", "2"):
        return "Medium"
    return "Low"


def _categorize_event(event_name: str) -> str:
    """Assign category: Fed / Macro / Earnings / OPEX."""
    name_lower = event_name.lower()
    if any(kw in name_lower for kw in ["fomc", "fed ", "federal funds", "interest rate decision"]):
        return "Fed"
    if "opex" in name_lower or "options expir" in name_lower:
        return "OPEX"
    if "earnings" in name_lower:
        return "Earnings"
    return "Macro"


# ─────────────────────────────────────────────
# OPEX dates — 3rd Friday of each month
# ─────────────────────────────────────────────

def _third_friday(year: int, month: int) -> datetime:
    """Calculate 3rd Friday of a given month."""
    # First day of month
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    # Day of week: Monday=0 ... Friday=4
    days_until_friday = (4 - first.weekday()) % 7
    first_friday = first + timedelta(days=days_until_friday)
    return first_friday + timedelta(weeks=2)


def get_opex_dates(start: datetime, days: int) -> list[dict]:
    """Get monthly options expiry dates within the lookahead window."""
    end = start + timedelta(days=days)
    events = []
    # Check current month and next 2 months
    for offset in range(3):
        m = start.month + offset
        y = start.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        opex = _third_friday(y, m)
        if start.date() <= opex.date() <= end.date():
            events.append({
                "date": opex.strftime("%Y-%m-%d"),
                "time": "16:00",
                "event": "Monthly Options Expiration (OPEX)",
                "impact": "Medium",
                "category": "OPEX",
            })
    return events


# ─────────────────────────────────────────────
# Macro events — Trading Economics scrape
# ─────────────────────────────────────────────

def fetch_macro_events(days: int = 7) -> list[dict]:
    """Scrape US macro events from Trading Economics calendar."""
    today = datetime.now(tz=timezone.utc)
    end = today + timedelta(days=days)

    url = "https://tradingeconomics.com/calendar"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to fetch Trading Economics calendar: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    events = []

    # Trading Economics renders calendar as a table
    table = soup.find("table", {"id": "calendar"}) or soup.find("table")
    if not table:
        logger.warning("Could not find calendar table on Trading Economics")
        return []

    rows = table.find_all("tr")
    current_date = None

    for row in rows:
        # Date header rows
        date_header = row.find("td", colspan=True) or row.find("th", colspan=True)
        if date_header and date_header.get_text(strip=True):
            text = date_header.get_text(strip=True)
            try:
                current_date = datetime.strptime(text, "%B %d, %Y").replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    current_date = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            continue

        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # Extract country — look for flag or text
        country_cell = cells[1] if len(cells) > 1 else None
        country = ""
        if country_cell:
            # Check for title attribute on flag images
            flag = country_cell.find("img") or country_cell.find("span")
            if flag and flag.get("title"):
                country = flag["title"]
            elif flag and flag.get("alt"):
                country = flag["alt"]
            else:
                country = country_cell.get_text(strip=True)

        # Only US events
        if "united states" not in country.lower() and "us" != country.strip().upper():
            continue

        # Time
        time_text = cells[0].get_text(strip=True) if cells[0] else ""

        # Event name
        event_name = ""
        for cell in cells[2:5]:
            text = cell.get_text(strip=True)
            if text and len(text) > 3 and not text.replace(".", "").replace("-", "").isdigit():
                event_name = text
                break

        if not event_name:
            continue

        # Importance — some pages encode as a class or data attribute
        importance = ""
        imp_cell = row.find("td", class_=lambda c: c and "calendar" in str(c).lower())
        if imp_cell:
            importance = imp_cell.get("data-importance", "")

        impact = _classify_impact(event_name, importance)

        evt_date = current_date.strftime("%Y-%m-%d") if current_date else today.strftime("%Y-%m-%d")

        events.append({
            "date": evt_date,
            "time": time_text or "TBD",
            "event": event_name,
            "impact": impact,
            "category": _categorize_event(event_name),
        })

    # Filter to lookahead window
    filtered = []
    for evt in events:
        try:
            evt_dt = datetime.strptime(evt["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if today.date() <= evt_dt.date() <= end.date():
                filtered.append(evt)
        except ValueError:
            filtered.append(evt)

    return filtered


# ─────────────────────────────────────────────
# Earnings events (from data_fetcher)
# ─────────────────────────────────────────────

def fetch_earnings_events(ticker: str) -> list[dict]:
    """Get earnings event for a ticker using data_fetcher.get_earnings()."""
    data = get_earnings(ticker)
    if "error" in data or not data.get("next_date"):
        return []

    return [{
        "date": data["next_date"][:10] if data["next_date"] else "Unknown",
        "time": "AMC/BMO",
        "event": f"{ticker.upper()} Earnings Report",
        "impact": "High",
        "category": "Earnings",
        "eps_estimate": data.get("eps_estimate"),
        "revenue_estimate": data.get("revenue_estimate"),
        "implied_move_pct": data.get("implied_move_pct"),
    }]


# ─────────────────────────────────────────────
# Warnings generator
# ─────────────────────────────────────────────

def generate_warnings(events: list[dict]) -> list[str]:
    """Generate urgency warnings for events within 48 hours or today."""
    now = datetime.now(tz=timezone.utc)
    warnings = []

    for evt in events:
        try:
            evt_dt = datetime.strptime(evt["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        hours_until = (evt_dt - now).total_seconds() / 3600

        if evt["impact"] == "High":
            if hours_until <= 0 and hours_until > -24:
                warnings.append(f"TODAY: {evt['event']} — {evt['impact']} impact")
            elif 0 < hours_until <= 48:
                warnings.append(
                    f"WITHIN 48H: {evt['event']} on {evt['date']} — {evt['impact']} impact"
                )

        if evt["category"] == "Earnings" and 0 < hours_until <= 168:  # 7 days
            warnings.append(
                f"EARNINGS ALERT: {evt['event']} in {hours_until/24:.0f} days — elevated IV risk"
            )

        if "fomc" in evt.get("event", "").lower() and hours_until <= 0 and hours_until > -24:
            warnings.append("FOMC DAY: Expect elevated volatility across all assets")

    return list(dict.fromkeys(warnings))  # deduplicate preserving order


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def build_calendar(ticker: str = None, days: int = 7) -> dict:
    """Build the full economic calendar output."""
    now = datetime.now(tz=timezone.utc)
    all_events = []

    # 1. Macro events (graceful failure)
    try:
        macro = fetch_macro_events(days)
        all_events.extend(macro)
    except Exception as e:
        logger.warning(f"Macro events unavailable: {e}")

    # 2. OPEX dates
    opex = get_opex_dates(now, days)
    all_events.extend(opex)

    # 3. Earnings (if ticker provided)
    if ticker:
        earnings = fetch_earnings_events(ticker)
        all_events.extend(earnings)

    # Sort by date
    all_events.sort(key=lambda e: e.get("date", "9999-99-99"))

    # Warnings
    warnings = generate_warnings(all_events)

    # Next high-impact event
    next_high = None
    for evt in all_events:
        if evt["impact"] == "High":
            try:
                evt_dt = datetime.strptime(evt["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if evt_dt.date() >= now.date():
                    next_high = evt
                    break
            except (ValueError, TypeError):
                continue

    return {
        "generated_at": now.isoformat(),
        "lookahead_days": days,
        "ticker": ticker,
        "events": all_events,
        "warnings": warnings,
        "next_high_impact": next_high,
    }


def main():
    parser = argparse.ArgumentParser(description="Economic Calendar for TradeDesk")
    parser.add_argument("ticker", nargs="?", default=None, help="Ticker symbol (optional)")
    parser.add_argument("--days", type=int, default=7, help="Lookahead window in days (default: 7)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = build_calendar(ticker=args.ticker, days=args.days)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
