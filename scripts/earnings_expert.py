"""
earnings_expert.py — Earnings play analysis for TradeDesk
Usage: python scripts/earnings_expert.py TICKER
"""
import sys, json, logging
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.data_fetcher import get_earnings, get_ohlcv

logger = logging.getLogger(__name__)


def analyze(ticker: str) -> dict:
    t = ticker.upper()
    tk = yf.Ticker(t)

    # Current price
    daily = get_ohlcv(t, "1D", bars=30)
    if daily.empty:
        return {"ticker": t, "error": "No data"}

    current_price = float(daily["close"].iloc[-1])

    # ATR-based expected move
    daily["tr"] = daily[["high", "low", "close"]].apply(
        lambda r: max(r["high"] - r["low"], abs(r["high"] - r["close"]), abs(r["low"] - r["close"])), axis=1
    )
    atr = float(daily["tr"].tail(14).mean())
    expected_move_pct = round(atr / current_price * 100, 2)
    expected_move_dollar = round(atr, 2)

    # Earnings date
    earnings = get_earnings(t)
    next_earnings_date = earnings.get("next_date")
    if next_earnings_date:
        from datetime import date
        try:
            ned = pd.to_datetime(next_earnings_date).date()
            days_to_earnings = (ned - date.today()).days
        except:
            days_to_earnings = 999
    else:
        days_to_earnings = 999

    # Historical earnings reactions (last 4)
    historical_reactions = []
    avg_historical_move_pct = None
    try:
        edates = tk.earnings_dates
        if edates is not None and not edates.empty:
            past = edates[edates.index < pd.Timestamp.now(tz="UTC")].head(4)
            hist_price = tk.history(period="2y", interval="1d")
            hist_price.index = pd.to_datetime(hist_price.index)
            if hist_price.index.tz is None:
                hist_price.index = hist_price.index.tz_localize("UTC")

            for edate in past.index:
                try:
                    before = hist_price[hist_price.index < edate].iloc[-1]["Close"]
                    after = hist_price[hist_price.index > edate].iloc[0]["Close"]
                    move = round((after - before) / before * 100, 2)
                    historical_reactions.append({
                        "date": str(edate.date()),
                        "move_pct": move,
                        "direction": "UP" if move > 0 else "DOWN"
                    })
                except:
                    pass

            if historical_reactions:
                avg_historical_move_pct = round(
                    float(np.mean([abs(r["move_pct"]) for r in historical_reactions])), 2
                )
    except:
        pass

    # IV crush risk
    if days_to_earnings <= 1:
        iv_crush_risk = "ACTIVE — earnings tonight"
        play_recommendation = "Strangle/straddle for the move — sell contracts right after earnings release to capture IV crush"
    elif days_to_earnings <= 7:
        iv_crush_risk = "HIGH — IV elevated"
        play_recommendation = "Sell premium (credit spread / iron condor) — IV crush will decay rapidly post-earnings"
    elif days_to_earnings <= 30:
        iv_crush_risk = "MEDIUM — IV building"
        play_recommendation = "Directional play if trend is clear — avoid buying options, IV premium too high"
    else:
        iv_crush_risk = "LOW"
        play_recommendation = "Directional trade based on technicals — normal options pricing"

    # Summary
    move_str = f"~{expected_move_pct}% (${expected_move_dollar})"
    hist_str = f"{avg_historical_move_pct}% avg" if avg_historical_move_pct else "N/A"
    summary_text = (
        f"{t} earnings in {days_to_earnings} days ({next_earnings_date})\n"
        f"Expected move: {move_str} | Historical avg: {hist_str}\n"
        f"IV Crush risk: {iv_crush_risk}\n"
        f"Play: {play_recommendation}"
    )

    return {
        "ticker": t,
        "current_price": round(current_price, 2),
        "next_earnings_date": str(next_earnings_date) if next_earnings_date else None,
        "days_to_earnings": days_to_earnings,
        "expected_move_pct": expected_move_pct,
        "expected_move_dollar": expected_move_dollar,
        "avg_historical_move_pct": avg_historical_move_pct,
        "historical_reactions": historical_reactions,
        "iv_crush_risk": iv_crush_risk,
        "play_recommendation": play_recommendation,
        "summary_text": summary_text,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python scripts/earnings_expert.py TICKER")
        sys.exit(1)
    print(json.dumps(analyze(sys.argv[1]), indent=2, default=str))
