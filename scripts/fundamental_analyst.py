"""
fundamental_analyst.py — Fundamental Analysis for TradeDesk
============================================================
Pulls fundamentals + earnings, grades valuation/growth, flags risks.

Usage:
    python scripts/fundamental_analyst.py AAPL
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_fetcher import get_fundamentals, get_earnings

logger = logging.getLogger(__name__)


def _safe(val):
    """Return val if it's a real number, else None."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pct_fmt(val):
    """Format a decimal ratio as percentage string."""
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _earnings_proximity(next_date_str: str) -> dict:
    """Compute days to earnings and risk level."""
    if not next_date_str:
        return {"days_to_earnings": None, "earnings_risk": "UNKNOWN"}
    try:
        earn_dt = datetime.fromisoformat(next_date_str.split(" ")[0])
        days = (earn_dt - datetime.now()).days
        if days < 0:
            risk = "PASSED"
        elif days < 8:
            risk = "HIGH"
        elif days <= 30:
            risk = "MEDIUM"
        else:
            risk = "LOW"
        return {"days_to_earnings": days, "earnings_risk": risk}
    except Exception:
        return {"days_to_earnings": None, "earnings_risk": "UNKNOWN"}


def _valuation_grade(pe, forward_pe) -> dict:
    """Grade valuation from PE ratio."""
    grade = "N/A"
    outlook = None

    if pe is not None:
        if pe < 15:
            grade = "Cheap"
        elif pe <= 25:
            grade = "Fair"
        elif pe <= 40:
            grade = "Pricey"
        else:
            grade = "Expensive"

    if pe is not None and forward_pe is not None and forward_pe < pe:
        outlook = "Improving earnings outlook"

    return {"valuation_grade": grade, "earnings_outlook": outlook}


def _growth_grade(revenue_growth) -> str:
    """Grade growth from revenue growth rate (decimal ratio)."""
    if revenue_growth is None:
        return "N/A"
    pct = revenue_growth * 100
    if pct > 20:
        return "High growth"
    elif pct >= 5:
        return "Moderate growth"
    else:
        return "Slow growth"


def _build_risk_flags(fundamentals: dict, earnings_risk: str) -> list:
    """Build list of risk flag strings."""
    flags = []
    pe = _safe(fundamentals.get("pe_ratio"))
    if pe is not None and pe > 40:
        flags.append(f"High PE ({pe:.1f})")

    net_margin = _safe(fundamentals.get("net_margin"))
    if net_margin is not None and net_margin < 0:
        flags.append(f"Negative net margin ({_pct_fmt(net_margin)})")

    gross_margin = _safe(fundamentals.get("gross_margin"))
    if gross_margin is not None and gross_margin < 0:
        flags.append(f"Negative gross margin ({_pct_fmt(gross_margin)})")

    dte = _safe(fundamentals.get("debt_to_equity"))
    if dte is not None and dte > 150:
        flags.append(f"High debt-to-equity ({dte:.1f})")

    if earnings_risk == "HIGH":
        flags.append("Earnings within 8 days")

    return flags


def _build_summary(ticker: str, val: dict, growth_grade: str,
                   risk_flags: list, fundamentals: dict,
                   earnings_prox: dict) -> str:
    """Build a human-readable summary."""
    lines = [f"{ticker} — {fundamentals.get('name', '')}"]
    lines.append(f"Sector: {fundamentals.get('sector', 'N/A')} | Industry: {fundamentals.get('industry', 'N/A')}")

    pe = _safe(fundamentals.get("pe_ratio"))
    fwd = _safe(fundamentals.get("forward_pe"))
    lines.append(f"Valuation: {val['valuation_grade']} (PE {pe or 'N/A'}, Fwd PE {fwd or 'N/A'})")
    if val["earnings_outlook"]:
        lines.append(f"  -> {val['earnings_outlook']}")

    rev = fundamentals.get("revenue_growth")
    lines.append(f"Growth: {growth_grade} (Revenue growth {_pct_fmt(rev)})")

    target = _safe(fundamentals.get("price_target"))
    rating = fundamentals.get("analyst_rating", "N/A")
    lines.append(f"Analysts: {rating} | Target ${target or 'N/A'}")

    days = earnings_prox["days_to_earnings"]
    risk = earnings_prox["earnings_risk"]
    if days is not None:
        lines.append(f"Earnings: {days} days away ({risk} risk)")
    else:
        lines.append(f"Earnings: date unknown ({risk})")

    if risk_flags:
        lines.append(f"Risk flags: {', '.join(risk_flags)}")
    else:
        lines.append("Risk flags: None")

    return "\n".join(lines)


def analyze(ticker: str) -> dict:
    """Run full fundamental analysis on a ticker."""
    ticker = ticker.upper()
    fundamentals = get_fundamentals(ticker)
    earnings = get_earnings(ticker)

    if "error" in fundamentals:
        return {"ticker": ticker, "error": fundamentals["error"]}

    # Earnings proximity
    earnings_prox = _earnings_proximity(earnings.get("next_date"))

    # Valuation grade
    pe = _safe(fundamentals.get("pe_ratio"))
    forward_pe = _safe(fundamentals.get("forward_pe"))
    val = _valuation_grade(pe, forward_pe)

    # Growth grade
    rev_growth = _safe(fundamentals.get("revenue_growth"))
    growth = _growth_grade(rev_growth)

    # Risk flags
    risk_flags = _build_risk_flags(fundamentals, earnings_prox["earnings_risk"])

    # Summary
    summary = _build_summary(ticker, val, growth, risk_flags, fundamentals, earnings_prox)

    return {
        "ticker":             ticker,
        "name":               fundamentals.get("name"),
        "sector":             fundamentals.get("sector"),
        "industry":           fundamentals.get("industry"),
        "market_cap":         fundamentals.get("market_cap"),
        "pe_ratio":           pe,
        "forward_pe":         forward_pe,
        "peg_ratio":          _safe(fundamentals.get("peg_ratio")),
        "price_to_book":      _safe(fundamentals.get("pb_ratio")),
        "profit_margin":      _safe(fundamentals.get("net_margin")),
        "revenue_growth":     rev_growth,
        "gross_margin":       _safe(fundamentals.get("gross_margin")),
        "debt_to_equity":     _safe(fundamentals.get("debt_to_equity")),
        "analyst_target":     _safe(fundamentals.get("price_target")),
        "analyst_rating":     fundamentals.get("analyst_rating"),
        "next_earnings_date": earnings.get("next_date"),
        "days_to_earnings":   earnings_prox["days_to_earnings"],
        "earnings_risk":      earnings_prox["earnings_risk"],
        "valuation_grade":    val["valuation_grade"],
        "earnings_outlook":   val["earnings_outlook"],
        "growth_grade":       growth,
        "risk_flags":         risk_flags,
        "summary_text":       summary,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python scripts/fundamental_analyst.py TICKER")
        sys.exit(1)

    ticker = sys.argv[1]
    result = analyze(ticker)
    print(json.dumps(result, indent=2, default=str))
