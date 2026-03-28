#!/usr/bin/env python3
"""
misc/tradertv/parser.py — Parse TraderTV Morning Note PDF into structured JSON

Uses PyMuPDF (fitz) to extract text per page, then parses:
- Ticker symbol
- Headline
- News bullets
- Support/Resistance price zones
- Bias (BULLISH/BEARISH/NEUTRAL) + bias detail text
- Trader takeaway

Usage:
    python misc/tradertv/parser.py misc/tradertv/sample_Mar27.pdf
    python misc/tradertv/parser.py misc/tradertv/downloads/morning_note_2026-03-27.pdf

Output: JSON to stdout
"""

import json
import re
import sys
from pathlib import Path


# --- Ticker map: company name keywords → ticker symbol ---
COMPANY_TO_TICKER = {
    "meta": "META",
    "amazon": "AMZN",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "apple": "AAPL",
    "nvidia": "NVDA",
    "micron": "MU",
    "netflix": "NFLX",
    "uber": "UBER",
    "arm ": "ARM",
    "arm explodes": "ARM",
    "arm holdings": "ARM",
    "super micro": "SMCI",
    "supermicro": "SMCI",
    "alibaba": "BABA",
    "warner bros": "WBD",
    "target ": "TGT",
    "target faces": "TGT",
    "oil ": "USO",
    "crude": "USO",
    "sk hynix": "000660.KS",
    "tesla": "TSLA",
    "palantir": "PLTR",
    "coinbase": "COIN",
    "broadcom": "AVGO",
    "amd": "AMD",
    "intel": "INTC",
    "salesforce": "CRM",
    "snowflake": "SNOW",
    "crowdstrike": "CRWD",
    "palo alto": "PANW",
    "unity": "U",
    "synopsys": "SNPS",
    "mastercard": "MA",
    "visa": "V",
    "jpmorgan": "JPM",
    "goldman": "GS",
    "morgan stanley": "MS",
    "bank of america": "BAC",
    "citigroup": "C",
    "wells fargo": "WFC",
    "disney": "DIS",
    "exxon": "XOM",
    "chevron": "CVX",
    "gold": "GLD",
    "silver": "SLV",
    "bitcoin": "IBIT",
    "spacex": "SPCE",
    "pony ai": "PONY",
    "jetblue": "JBLU",
    "qualcomm": "QCOM",
    "jefferies": "JEF",
    "raytheon": "RTX",
    "rtx": "RTX",
    "kweb": "KWEB",
}

# Bias keywords
BEARISH_WORDS = ["drops", "falls", "risk", "freeze", "freezes", "cuts", "warns",
                 "liability", "decline", "selloff", "sell-off", "slump", "struggles",
                 "bearish", "bear market", "correction", "losses", "plunges", "probe"]
BULLISH_WORDS = ["surges", "ramps", "expands", "explodes", "gains", "bullish",
                 "breakout", "defended", "defended", "boost", "higher", "momentum",
                 "rally", "upgrade", "strong", "beats"]


def extract_ticker(headline: str, text: str) -> str:
    """Extract ticker from headline or body text."""
    # Look for explicit $TICKER mentions
    tickers = re.findall(r'\$([A-Z]{1,5})\b', text)
    if tickers:
        return tickers[0]

    # Match company name in headline
    headline_lower = headline.lower()
    for name, ticker in COMPANY_TO_TICKER.items():
        if name in headline_lower:
            return ticker

    return "UNKNOWN"


def parse_price_zones(section: str) -> list[dict]:
    """Parse price zones from Support: or Resistance: section text."""
    zones = []

    # Pattern: $XXX – $XXX — description  OR  $XXX.XX – description
    # Also handles: $XXX.XX – $XXX.XX – description
    price_pattern = re.compile(
        r'\$([\d,]+\.?\d*)\s*[–\-—]+\s*\$([\d,]+\.?\d*)\s*[–\-—]+\s*([^\n$]{5,80})',
        re.MULTILINE
    )
    single_pattern = re.compile(
        r'\$([\d,]+\.?\d*)\s*[–\-—]+\s*([^\n$]{5,80})',
        re.MULTILINE
    )

    for m in price_pattern.finditer(section):
        low = float(m.group(1).replace(",", ""))
        high = float(m.group(2).replace(",", ""))
        notes = m.group(3).strip().rstrip(".")
        zones.append({
            "low": low,
            "high": high,
            "zone": f"{low}–{high}",
            "notes": notes
        })

    # If no range zones found, try single price zones
    if not zones:
        for m in single_pattern.finditer(section):
            price = float(m.group(1).replace(",", ""))
            notes = m.group(2).strip().rstrip(".")
            zones.append({
                "low": price,
                "high": price,
                "zone": str(price),
                "notes": notes
            })

    return zones


def infer_bias(headline: str, bias_text: str) -> str:
    """Infer BULLISH/BEARISH/NEUTRAL from headline and explicit bias text."""
    combined = (headline + " " + bias_text).lower()

    # Explicit bias text wins
    if "bearish" in bias_text.lower() or "downside" in bias_text.lower():
        return "BEARISH"
    if "bullish" in bias_text.lower() or "upside" in bias_text.lower():
        return "BULLISH"

    # Score from keywords
    bear_score = sum(1 for w in BEARISH_WORDS if w in combined)
    bull_score = sum(1 for w in BULLISH_WORDS if w in combined)

    if bear_score > bull_score:
        return "BEARISH"
    elif bull_score > bear_score:
        return "BULLISH"
    return "NEUTRAL"


def parse_page(text: str) -> dict | None:
    """Parse a single stock page into structured dict."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return None

    # Skip TOC page (page 1)
    if "CHERIF'S MORNING NOTE" in text.upper():
        return None

    headline = lines[0] if lines else ""

    # Split into sections
    support_text = ""
    resistance_text = ""
    bias_text = ""
    takeaway_text = ""
    news_lines = []

    current_section = "news"
    for line in lines[1:]:
        line_lower = line.lower()
        if line_lower.startswith("support:") or line_lower == "support":
            current_section = "support"
            continue
        elif line_lower.startswith("resistance:") or line_lower == "resistance":
            current_section = "resistance"
            continue
        elif line_lower.startswith("bias:") or "intraday structure" in line_lower:
            current_section = "bias"
        elif "trader takeaway" in line_lower:
            current_section = "takeaway"
            continue

        if current_section == "news":
            news_lines.append(line)
        elif current_section == "support":
            support_text += " " + line
        elif current_section == "resistance":
            resistance_text += " " + line
        elif current_section == "bias":
            bias_text += " " + line
        elif current_section == "takeaway":
            takeaway_text += " " + line

    support_zones = parse_price_zones(support_text)
    resistance_zones = parse_price_zones(resistance_text)
    bias = infer_bias(headline, bias_text)
    ticker = extract_ticker(headline, text)

    # Skip if no meaningful data
    if not support_zones and not resistance_zones:
        return None

    return {
        "ticker": ticker,
        "headline": headline,
        "bias": bias,
        "bias_detail": bias_text.strip(),
        "support": support_zones,
        "resistance": resistance_zones,
        "trader_takeaway": takeaway_text.strip(),
        "news_summary": " ".join(news_lines[:5]).strip()[:400]
    }


def parse_pdf(pdf_path: str) -> dict:
    """Parse full PDF and return structured morning note."""
    try:
        import fitz  # pymupdf
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: uv pip install pymupdf", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(pdf_path)
    date_str = "unknown"

    # Try to extract date from filename
    fname = Path(pdf_path).stem
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
    if date_match:
        date_str = date_match.group(1)
    else:
        # Try from page 1 text
        page1 = doc[0].get_text()
        d = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})', page1)
        if d:
            from datetime import datetime
            try:
                dt = datetime.strptime(f"{d.group(1)} {d.group(2)} 2026", "%B %d %Y")
                date_str = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    stocks = []
    seen = set()
    for i, page in enumerate(doc):
        text = page.get_text()
        parsed = parse_page(text)
        if parsed:
            # Deduplicate by ticker + headline
            key = (parsed["ticker"], parsed["headline"][:40])
            if key not in seen:
                seen.add(key)
                stocks.append(parsed)

    return {
        "date": date_str,
        "source": "TraderTV Live — Cherif's Morning Note",
        "total_stocks": len(stocks),
        "stocks": stocks
    }


def filter_watchlist(data: dict, watchlist: list[str]) -> list[dict]:
    """Filter stocks to only those in the watchlist."""
    return [s for s in data["stocks"] if s["ticker"] in watchlist]


def main():
    if len(sys.argv) < 2:
        print("Usage: python parser.py <pdf_path> [--watchlist AAPL,NVDA,META]", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    watchlist = None

    if "--watchlist" in sys.argv:
        idx = sys.argv.index("--watchlist")
        watchlist = sys.argv[idx + 1].upper().split(",")

    if not Path(pdf_path).exists():
        print(f"ERROR: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = parse_pdf(pdf_path)

    if watchlist:
        result["stocks"] = filter_watchlist(result, watchlist)
        result["total_stocks"] = len(result["stocks"])
        result["watchlist_filter"] = watchlist

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
