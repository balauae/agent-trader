"""
market_open_scalper.py — Opening Range Breakout for TradeDesk
Usage: python scripts/market_open_scalper.py TICKER
"""
import sys, json, logging
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.data_fetcher import get_ohlcv
logger = logging.getLogger(__name__)

def analyze(ticker: str) -> dict:
    t = ticker.upper()
    df = get_ohlcv(t, "1m", bars=120)
    if df.empty or len(df) < 10:
        return {"ticker": t, "error": "Insufficient data"}

    # Opening range = first 5 bars
    or_df = df.head(5)
    orh = float(or_df["high"].max())
    orl = float(or_df["low"].min())
    or_mid = round((orh + orl) / 2, 2)
    or_size = round(orh - orl, 2)

    current_price = float(df["close"].iloc[-1])
    current_vol = float(df["volume"].iloc[-1])
    avg_vol = float(df["volume"].mean())
    vol_confirmed = current_vol > avg_vol * 1.1

    # ORB detection
    if current_price > orh:
        setup = "ORB Long"
        bias = "LONG"
        entry = round(orh + 0.01, 2)
        stop = or_mid
        target = round(orh + or_size, 2)
        notes = "Price broke above opening range high — long breakout"
    elif current_price < orl:
        setup = "ORB Short"
        bias = "SHORT"
        entry = round(orl - 0.01, 2)
        stop = or_mid
        target = round(orl - or_size, 2)
        notes = "Price broke below opening range low — short breakdown"
    elif current_price > or_mid:
        setup = "Watch Long"
        bias = "LONG"
        entry = round(orh + 0.01, 2)
        stop = or_mid
        target = round(orh + or_size, 2)
        notes = f"Above OR midpoint — watching for ORH break at ${orh}"
    else:
        setup = "Watch Short"
        bias = "SHORT"
        entry = round(orl - 0.01, 2)
        stop = or_mid
        target = round(orl - or_size, 2)
        notes = f"Below OR midpoint — watching for ORL break at ${orl}"

    risk = abs(entry - stop) if stop else 0
    reward = abs(target - entry) if target else 0
    rr = round(reward / risk, 2) if risk > 0 else 0

    # Williams volatility breakout levels
    try:
        prev_open = float(df["Open"].iloc[-2]) if len(df) >= 2 else float(df["Open"].iloc[-1])
        atr_val = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
        williams_buy = round(prev_open + atr_val * 0.6, 2)
        williams_short = round(prev_open - atr_val * 0.6, 2)
        williams_breakout = {
            "buy_level": williams_buy, "short_level": williams_short,
            "atr": round(atr_val, 2),
            "notes": f"Break above ${williams_buy} = momentum long | Below ${williams_short} = momentum short"
        }
    except Exception:
        williams_breakout = {}

    return {
        "ticker": t,
        "current_price": round(current_price, 2),
        "orh": round(orh, 2),
        "orl": round(orl, 2),
        "or_midpoint": or_mid,
        "or_size": or_size,
        "setup": setup,
        "bias": bias,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": rr,
        "volume_confirmed": vol_confirmed,
        "notes": notes,
        "williams_breakout": williams_breakout,
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python scripts/market_open_scalper.py TICKER")
        sys.exit(1)
    print(json.dumps(analyze(sys.argv[1]), indent=2, default=str))
