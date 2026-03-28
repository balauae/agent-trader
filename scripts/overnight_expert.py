"""
overnight_expert.py — Overnight Risk & Setup Analysis
======================================================
Analyzes after-hours movement, support/resistance, and earnings risk.

Usage:
    python scripts/overnight_expert.py TICKER
"""

import yfinance as yf
import pandas as pd
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_fetcher import get_ohlcv, get_ohlcv_smart, get_earnings

logger = logging.getLogger(__name__)


def analyze(ticker: str) -> dict:
    """Generate overnight risk analysis for a ticker."""
    ticker = ticker.upper()
    tk = yf.Ticker(ticker)

    # Regular session close
    regular = tk.history(period="1d", interval="1m")
    if regular.empty:
        return {"ticker": ticker, "error": "No regular session data available"}
    regular_close = float(regular["Close"].iloc[-1])

    # After-hours price (prepost=True includes extended hours)
    extended = tk.history(period="1d", interval="1m", prepost=True)
    if extended.empty:
        return {"ticker": ticker, "error": "No extended hours data available"}
    ah_price = float(extended["Close"].iloc[-1])
    ah_change_pct = (ah_price - regular_close) / regular_close * 100

    # Support / Resistance from last 5 daily bars — TV primary
    daily, daily_src = get_ohlcv_smart(ticker, "1D", bars=20)
    if not daily.empty:
        support = float(daily["low"].tail(5).min())
        resistance = float(daily["high"].tail(5).max())
    else:
        support = None
        resistance = None

    # Earnings check
    earnings = get_earnings(ticker)
    earnings_tonight = False
    next_earnings_date = earnings.get("next_date")
    if next_earnings_date:
        try:
            earn_dt = pd.Timestamp(next_earnings_date)
            now = pd.Timestamp(datetime.now(tz=timezone.utc))
            if 0 <= (earn_dt - now).total_seconds() <= 86400:
                earnings_tonight = True
        except Exception:
            pass

    # Risk assessment
    if earnings_tonight or abs(ah_change_pct) > 3:
        risk_level = "High"
    elif abs(ah_change_pct) > 1:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "ticker": ticker,
        "regular_close": regular_close,
        "ah_price": ah_price,
        "ah_change_pct": round(ah_change_pct, 4),
        "support": support,
        "resistance": resistance,
        "next_earnings_date": next_earnings_date,
        "earnings_tonight": earnings_tonight,
        "risk_level": risk_level,
        "data_source": f"extended_hours=yfinance, daily={daily_src}",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python scripts/overnight_expert.py TICKER")
        sys.exit(1)

    result = analyze(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))
