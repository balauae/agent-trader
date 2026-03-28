#!/usr/bin/env python3
"""
misc/tradertv/setup_finder.py — Find best trading setups from TraderTV Morning Note PDF

Parses all stocks in the PDF and ranks them by setup quality:
- Clear directional bias
- Tight, well-defined S/R zones
- Catalyst strength (from headline)
- Cross-references with Bala's watchlists (bonus scoring)

Usage:
    python misc/tradertv/setup_finder.py <pdf_path>
    python misc/tradertv/setup_finder.py misc/tradertv/sample3.pdf
    python misc/tradertv/setup_finder.py misc/tradertv/sample3.pdf --top 5
    python misc/tradertv/setup_finder.py misc/tradertv/sample3.pdf --format telegram

Output: JSON to stdout (or Telegram-formatted text)
"""

import json
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from misc.tradertv.parser import parse_pdf


# Bala's full watchlist from USER.md
WATCHLISTS = {
    "momentum":    {"TSLA", "NVDA", "AMD", "MRVL", "PLTR", "COIN", "APP", "HIMS", "CRWV", "ARM", "RKLB", "HOOD", "SOFI", "SOUN", "RGTI", "SMCI"},
    "growth":      {"AAPL", "MSFT", "META", "AMZN", "GOOGL", "AVGO", "MU", "CRWD", "PANW", "NFLX", "ORCL", "TSM", "NU", "AFRM", "SNOW", "TEAM", "DOCU", "WDAY", "DOCN", "UNH", "OKTA", "PYPL", "NVO"},
    "macro":       {"GLD", "SLV", "IBIT", "BABA"},
    "speculative": {"QBTS", "APLD", "IREN", "SMR", "ALAB", "MDB"},
    "swing":       {"AXON", "TTD", "ZS", "ADBE"},
}

ALL_WATCHLIST = {t for tickers in WATCHLISTS.values() for t in tickers}

# High-conviction catalyst keywords → boost score
STRONG_CATALYST = [
    "verdict", "lawsuit", "fda approval", "earnings beat", "earnings miss",
    "upgrade", "downgrade", "acquisition", "merger", "breakout", "ipo",
    "short squeeze", "guidance raised", "guidance cut", "layoffs", "probe",
    "ban", "tariff", "rate cut", "rate hike"
]


def score_setup(stock: dict) -> dict:
    """Score a stock's setup quality. Returns stock with added score fields."""
    score = 0
    reasons = []

    # 1. Bias clarity (clear bias = more actionable)
    if stock["bias"] in ("BULLISH", "BEARISH"):
        score += 20
        reasons.append(f"Clear {stock['bias'].lower()} bias")
    elif stock["bias"] == "NEUTRAL":
        score += 5

    # 2. Number of defined S/R levels (more = better defined setup)
    n_support = len(stock["support"])
    n_resist = len(stock["resistance"])
    if n_support >= 2 and n_resist >= 2:
        score += 15
        reasons.append("Well-defined S/R structure")
    elif n_support >= 1 and n_resist >= 1:
        score += 8

    # 3. Risk/reward — gap between nearest support and resistance
    rr_score = 0
    rr_ratio = None
    if stock["support"] and stock["resistance"]:
        nearest_support = stock["support"][0]["low"]
        nearest_resist = stock["resistance"][0]["low"]
        if nearest_support > 0:
            gap_pct = (nearest_resist - nearest_support) / nearest_support * 100
            # Tighter gaps (5–15%) = cleaner setup
            if 3 <= gap_pct <= 15:
                rr_score = 20
                rr_ratio = round(gap_pct, 1)
                reasons.append(f"Tight S/R gap {gap_pct:.1f}%")
            elif gap_pct <= 25:
                rr_score = 10
                rr_ratio = round(gap_pct, 1)
            score += rr_score

    # 4. Watchlist bonus
    watchlist_name = None
    for wl_name, tickers in WATCHLISTS.items():
        if stock["ticker"] in tickers:
            watchlist_name = wl_name
            score += 25
            reasons.append(f"In {wl_name} watchlist")
            break

    # 5. Catalyst strength
    headline_lower = stock["headline"].lower()
    news_lower = stock["news_summary"].lower()
    combined = headline_lower + " " + news_lower
    for kw in STRONG_CATALYST:
        if kw in combined:
            score += 10
            reasons.append(f"Strong catalyst: {kw}")
            break

    # 6. Trader takeaway present = more conviction
    if len(stock.get("trader_takeaway", "")) > 50:
        score += 5
        reasons.append("Detailed trader takeaway")

    # Determine setup type
    if stock["bias"] == "BULLISH":
        setup_type = "LONG — buy dip to support"
        if stock["support"]:
            entry = stock["support"][0]
            setup_type = f"LONG — buy near ${entry['low']}–${entry['high']} support"
    elif stock["bias"] == "BEARISH":
        setup_type = "SHORT — sell rally to resistance"
        if stock["resistance"]:
            res = stock["resistance"][0]
            setup_type = f"SHORT — fade rally into ${res['low']}–${res['high']} resistance"
    else:
        setup_type = "WATCH — no clear bias"

    return {
        **stock,
        "setup_score": score,
        "setup_type": setup_type,
        "rr_gap_pct": rr_ratio,
        "watchlist": watchlist_name,
        "score_reasons": reasons,
    }


def find_setups(pdf_path: str, top_n: int = 10) -> dict:
    """Parse PDF and return ranked trading setups."""
    data = parse_pdf(pdf_path)
    scored = [score_setup(s) for s in data["stocks"]]
    ranked = sorted(scored, key=lambda x: x["setup_score"], reverse=True)

    return {
        "date": data["date"],
        "source": data["source"],
        "total_parsed": data["total_stocks"],
        "top_setups": ranked[:top_n],
        "watchlist_hits": [s for s in ranked if s["watchlist"]],
    }


def format_telegram(result: dict) -> str:
    """Format setups as Telegram message."""
    lines = [
        f"📰 *TraderTV Morning Note — {result['date']}*",
        f"_{result['total_parsed']} stocks analyzed_",
        "",
    ]

    # Watchlist hits first — deduplicate by ticker (keep highest score)
    seen_tickers = set()
    unique_wl = []
    for s in result["watchlist_hits"]:
        if s["ticker"] not in seen_tickers:
            seen_tickers.add(s["ticker"])
            unique_wl.append(s)

    if unique_wl:
        lines.append("🎯 *Your Watchlist Mentions:*")
        for s in unique_wl[:5]:
            emoji = "🟢" if s["bias"] == "BULLISH" else "🔴" if s["bias"] == "BEARISH" else "⚪"
            lines.append(f"{emoji} *{s['ticker']}* ({s['watchlist']}) — {s['bias']}")
            lines.append(f"   _{s['headline']}_")
            if s["support"]:
                sup = s["support"][0]
                zone = f"${sup['low']}–${sup['high']}" if sup['low'] != sup['high'] else f"${sup['low']}"
                lines.append(f"   S: {zone} — _{sup['notes'][:40]}_")
            if s["resistance"]:
                res = s["resistance"][0]
                zone = f"${res['low']}–${res['high']}" if res['low'] != res['high'] else f"${res['low']}"
                lines.append(f"   R: {zone} — _{res['notes'][:40]}_")
            lines.append(f"   📌 {s['setup_type']}")
            lines.append("")

    # Top setups (excluding watchlist hits already shown)
    wl_tickers = seen_tickers
    other_top = [s for s in result["top_setups"] if s["ticker"] not in wl_tickers][:3]

    if other_top:
        lines.append("⭐ *Top Setups (Other):*")
        for s in other_top:
            emoji = "🟢" if s["bias"] == "BULLISH" else "🔴" if s["bias"] == "BEARISH" else "⚪"
            lines.append(f"{emoji} *{s['ticker']}* — {s['bias']} (score: {s['setup_score']})")
            lines.append(f"   _{s['headline'][:60]}_")
            lines.append(f"   📌 {s['setup_type']}")
            lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_finder.py <pdf_path> [--top N] [--format telegram]", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    top_n = 10
    fmt = "json"

    if "--top" in sys.argv:
        idx = sys.argv.index("--top")
        top_n = int(sys.argv[idx + 1])

    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        fmt = sys.argv[idx + 1]

    if not Path(pdf_path).exists():
        print(f"ERROR: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = find_setups(pdf_path, top_n)

    if fmt == "telegram":
        print(format_telegram(result))
    else:
        # Clean output — remove verbose fields for readability
        out = {
            "date": result["date"],
            "watchlist_hits": [{
                "ticker": s["ticker"],
                "bias": s["bias"],
                "headline": s["headline"],
                "setup_type": s["setup_type"],
                "support": s["support"][:2],
                "resistance": s["resistance"][:2],
                "score": s["setup_score"],
                "watchlist": s["watchlist"],
            } for s in result["watchlist_hits"]],
            "top_setups": [{
                "ticker": s["ticker"],
                "bias": s["bias"],
                "headline": s["headline"],
                "setup_type": s["setup_type"],
                "score": s["setup_score"],
                "rr_gap_pct": s["rr_gap_pct"],
                "watchlist": s["watchlist"],
                "reasons": s["score_reasons"],
            } for s in result["top_setups"]],
        }
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
