"""
news_fetcher.py — Aggregated News Fetcher for TradeDesk
=======================================================
Fetches, merges, deduplicates, and classifies news for a ticker.

Sources:
    - Yahoo Finance (via data_fetcher.get_news)
    - Finviz news table

Usage:
    python scripts/news_fetcher.py AAPL
    python scripts/news_fetcher.py NVDA --limit 20
"""

import sys
import json
import re
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Allow importing from scripts.data_fetcher when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.data_fetcher import get_news

logger = logging.getLogger(__name__)

# --- Impact classification keywords ---
HIGH_IMPACT = re.compile(
    r"\b("
    r"earnings|revenue miss|revenue beat|eps|guidance|outlook|forecast|"
    r"fda|approval|phase\s*[123]|clinical trial|"
    r"merger|acquisition|acquire[sd]?|buyout|takeover|"
    r"sec\b|8-k|10-q|filing|investigation|subpoena|"
    r"upgrade[sd]?|downgrade[sd]?|price target|analyst|"
    r"dividend|buyback|stock split|"
    r"bankruptcy|layoff|restructur"
    r")\b",
    re.IGNORECASE,
)

MEDIUM_IMPACT = re.compile(
    r"\b("
    r"product launch|new product|partnership|collaboration|"
    r"executive|ceo|cfo|cto|appoint|resign|"
    r"contract|deal|expansion|"
    r"ipo|spac|offering"
    r")\b",
    re.IGNORECASE,
)

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}"
FINVIZ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def classify_impact(title: str, summary: str = "") -> str:
    """Classify a news item as High, Medium, or Low impact."""
    text = f"{title} {summary}"
    if HIGH_IMPACT.search(text):
        return "High"
    if MEDIUM_IMPACT.search(text):
        return "Medium"
    return "Low"


def fetch_finviz_news(ticker: str) -> list[dict]:
    """Scrape the Finviz news table for a ticker."""
    try:
        resp = requests.get(
            FINVIZ_URL.format(ticker=ticker.upper()),
            headers=FINVIZ_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        news_table = soup.find("table", {"id": "news-table"})
        if not news_table:
            logger.warning(f"Finviz: no news table found for {ticker}")
            return []

        items = []
        current_date = ""

        for row in news_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            date_cell = cells[0].get_text(strip=True)
            link_tag = cells[1].find("a")
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            url = link_tag.get("href", "")

            # Source is in a small span after the link
            source_tag = cells[1].find("span")
            publisher = source_tag.get_text(strip=True) if source_tag else "Finviz"

            # Date parsing: some rows have full date, some only time
            if len(date_cell) > 8:
                current_date = date_cell
            else:
                date_cell = f"{current_date.split()[0]} {date_cell}" if current_date else date_cell

            items.append({
                "title": title,
                "publisher": publisher,
                "link": url,
                "published_at": date_cell,
                "summary": "",
                "source": "finviz",
            })

        return items
    except Exception as e:
        logger.error(f"Finviz fetch failed for {ticker}: {e}")
        return []


def fetch_all_news(ticker: str, limit: int = 20) -> list[dict]:
    """Fetch news from all sources, merge, deduplicate, classify, and rank."""
    # Fetch from both sources
    yahoo_news = get_news(ticker, limit=limit)
    finviz_news = fetch_finviz_news(ticker)

    # Normalize yahoo news
    for item in yahoo_news:
        item["source"] = "yahoo"

    all_news = yahoo_news + finviz_news

    # Deduplicate by normalized title
    seen = set()
    unique = []
    for item in all_news:
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Classify impact
    for item in unique:
        item["impact"] = classify_impact(item["title"], item.get("summary", ""))

    # Sort: High first, then Medium, then Low
    impact_order = {"High": 0, "Medium": 1, "Low": 2}
    unique.sort(key=lambda x: impact_order.get(x["impact"], 3))

    return unique[:limit]


def main():
    parser = argparse.ArgumentParser(description="Fetch and classify news for a stock ticker")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL, NVDA)")
    parser.add_argument("--limit", type=int, default=20, help="Max number of news items")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    news = fetch_all_news(args.ticker, limit=args.limit)

    output = {
        "ticker": args.ticker.upper(),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "count": len(news),
        "items": news,
    }

    indent = 2 if args.pretty else None
    print(json.dumps(output, indent=indent, default=str))


if __name__ == "__main__":
    main()
