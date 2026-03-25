"""
postmarket_summarizer.py — Post-Market Daily Summary
=====================================================
Generates end-of-day summary with VWAP, volume analysis, and price action.

Usage:
    python scripts/postmarket_summarizer.py TICKER
"""

import yfinance as yf
import pandas as pd
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def summarize(ticker: str) -> dict:
    """Generate post-market summary for a ticker."""
    ticker = ticker.upper()
    tk = yf.Ticker(ticker)

    # Intraday 5m bars
    df = tk.history(period="1d", interval="5m")
    if df.empty:
        return {"ticker": ticker, "error": "No intraday data available"}

    # Core price levels
    open_price = float(df["Close"].iloc[0])
    close_price = float(df["Close"].iloc[-1])
    high = float(df["High"].max())
    low = float(df["Low"].min())
    day_change_pct = (close_price - open_price) / open_price * 100

    # Volume analysis
    total_volume = int(df["Volume"].sum())
    avg_volume = float(tk.history(period="30d", interval="1d")["Volume"].mean())
    volume_ratio = total_volume / avg_volume if avg_volume > 0 else 0.0

    # VWAP calculation
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vwap = (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()
    vwap_close = float(vwap.iloc[-1])
    close_vs_vwap = "ABOVE" if close_price > vwap_close else "BELOW"

    summary_text = (
        f"{ticker} closed {day_change_pct:+.2f}%, {close_vs_vwap} VWAP, "
        f"volume {volume_ratio:.1f}x avg"
    )

    return {
        "ticker": ticker,
        "open": open_price,
        "close": close_price,
        "high": high,
        "low": low,
        "day_change_pct": round(day_change_pct, 4),
        "total_volume": total_volume,
        "avg_volume": round(avg_volume, 2),
        "volume_ratio": round(volume_ratio, 4),
        "vwap_close": round(vwap_close, 4),
        "close_vs_vwap": close_vs_vwap,
        "summary_text": summary_text,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python scripts/postmarket_summarizer.py TICKER")
        sys.exit(1)

    result = summarize(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))
