"""
premarket_specialist.py — Pre-market gap analysis for TradeDesk
Usage: python scripts/premarket_specialist.py TICKER
"""
import sys, json, logging
from pathlib import Path
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)

def analyze(ticker: str) -> dict:
    t = ticker.upper()
    tk = yf.Ticker(t)

    # Get 5 days of 1m data with pre/post market
    df = tk.history(period="5d", interval="1m", prepost=True)
    if df.empty:
        return {"ticker": t, "error": "No data"}

    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("America/New_York")

    # Split regular vs pre-market for today
    today = df.index.date[-1]
    today_df = df[df.index.date == today]
    regular = today_df.between_time("09:30", "16:00")
    premarket = today_df.between_time("04:00", "09:29")

    # Prior close
    prior_days = df[df.index.date < today]
    prior_regular = prior_days.between_time("09:30", "16:00")
    prior_close = float(prior_regular["Close"].iloc[-1]) if not prior_regular.empty else None

    if premarket.empty or prior_close is None:
        return {"ticker": t, "error": "No pre-market data available", "prior_close": prior_close}

    pm_price = float(premarket["Close"].iloc[-1])
    pm_high = float(premarket["High"].max())
    pm_low = float(premarket["Low"].min())
    pm_volume = float(premarket["Volume"].sum())

    gap_pct = round((pm_price - prior_close) / prior_close * 100, 2)
    gap_direction = "UP" if gap_pct > 0 else "DOWN" if gap_pct < 0 else "FLAT"

    # Volume ratio vs 20d avg daily volume
    hist = tk.history(period="30d", interval="1d")
    avg_vol = float(hist["Volume"].mean()) if not hist.empty else 0
    vol_ratio = round(pm_volume / (avg_vol * 0.15), 2) if avg_vol > 0 else 0  # PM ~15% of full day

    # Setup classification
    abs_gap = abs(gap_pct)
    if abs_gap >= 3 and vol_ratio >= 1.2:
        setup = "gap-and-go"
        notes = f"Strong {gap_direction} gap with volume — momentum play"
    elif abs_gap >= 1.5 and vol_ratio < 0.8:
        setup = "gap-fill"
        notes = "Gap on low volume — likely to fill back toward prior close"
    elif abs_gap < 1:
        setup = "no-trade"
        notes = "Gap too small — wait for direction at open"
    else:
        setup = "watch"
        notes = "Moderate gap — wait for first 5 min candle to confirm direction"

    return {
        "ticker": t,
        "prior_close": round(prior_close, 2),
        "premarket_price": round(pm_price, 2),
        "gap_pct": gap_pct,
        "gap_direction": gap_direction,
        "pm_high": round(pm_high, 2),
        "pm_low": round(pm_low, 2),
        "pm_volume": int(pm_volume),
        "volume_ratio": vol_ratio,
        "setup": setup,
        "notes": notes,
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python scripts/premarket_specialist.py TICKER")
        sys.exit(1)
    print(json.dumps(analyze(sys.argv[1]), indent=2, default=str))
