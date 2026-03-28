"""
vwap_watcher.py — VWAP setup detection for TradeDesk
=====================================================
Usage:
    python scripts/vwap_watcher.py TICKER
    python scripts/vwap_watcher.py NVDA
    python scripts/vwap_watcher.py AAPL

Outputs JSON with VWAP, bands, setup type, entry/stop/target, and R:R.
"""

import sys
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_ohlcv

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# VWAP + BANDS
# ─────────────────────────────────────────────

def compute_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Compute session VWAP and standard deviation bands."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = tp * df["volume"]
    cum_vol = df["volume"].cumsum()
    cum_tp_vol = tp_vol.cumsum()

    vwap = cum_tp_vol / cum_vol

    # Cumulative variance for bands
    cum_tp2_vol = (tp**2 * df["volume"]).cumsum()
    variance = (cum_tp2_vol / cum_vol) - vwap**2
    variance = variance.clip(lower=0)
    std = np.sqrt(variance)

    df = df.copy()
    df["vwap"] = vwap
    df["vwap_upper_1"] = vwap + std
    df["vwap_upper_2"] = vwap + 2 * std
    df["vwap_lower_1"] = vwap - std
    df["vwap_lower_2"] = vwap - 2 * std
    df["vwap_std"] = std
    return df


# ─────────────────────────────────────────────
# SETUP DETECTION
# ─────────────────────────────────────────────

def detect_setup(df: pd.DataFrame) -> dict:
    """Detect VWAP setup from recent price action."""
    if len(df) < 20:
        return {"setup": "No Setup", "bias": "NEUTRAL", "notes": "Insufficient data"}

    last = df.iloc[-1]
    price = float(last["close"])
    vwap_val = float(last["vwap"])
    upper1 = float(last["vwap_upper_1"])
    upper2 = float(last["vwap_upper_2"])
    lower1 = float(last["vwap_lower_1"])
    lower2 = float(last["vwap_lower_2"])
    vwap_std = float(last["vwap_std"])

    distance_pct = ((price - vwap_val) / vwap_val) * 100 if vwap_val else 0

    # Volume confirmation: last bar vs 20-bar average
    vol_avg = float(df["volume"].tail(20).mean())
    vol_last = float(last["volume"])
    vol_confirmed = vol_last > vol_avg * 1.1

    # Look at recent bars for setup detection
    recent = df.tail(10)
    prev_5 = df.iloc[-6:-1]

    # Price relative to VWAP over recent bars
    above_count = int((recent["close"] > recent["vwap"]).sum())
    below_count = int((recent["close"] < recent["vwap"]).sum())

    # Check for VWAP cross in last few bars
    crosses_above = False
    crosses_below = False
    for i in range(-5, -1):
        if len(df) + i > 0 and len(df) + i + 1 < len(df):
            prev_bar = df.iloc[i]
            next_bar = df.iloc[i + 1]
            if prev_bar["close"] < prev_bar["vwap"] and next_bar["close"] > next_bar["vwap"]:
                crosses_above = True
            if prev_bar["close"] > prev_bar["vwap"] and next_bar["close"] < next_bar["vwap"]:
                crosses_below = True

    # --- Extended ---
    if price > upper2:
        setup = "Extended Short"
        bias = "SHORT"
        notes = "Price >2σ above VWAP — mean reversion fade opportunity"
        entry = round(price, 2)
        stop = round(upper2 + vwap_std * 0.5, 2)
        target = round(upper1, 2)
    elif price < lower2:
        setup = "Extended Long"
        bias = "LONG"
        notes = "Price <2σ below VWAP — mean reversion bounce opportunity"
        entry = round(price, 2)
        stop = round(lower2 - vwap_std * 0.5, 2)
        target = round(lower1, 2)

    # --- Reclaim ---
    elif crosses_above and below_count >= 3 and price > vwap_val:
        setup = "VWAP Reclaim"
        bias = "LONG"
        notes = "Price dipped below VWAP and reclaimed — failed breakdown = long"
        entry = round(vwap_val + vwap_std * 0.1, 2)
        stop = round(vwap_val - vwap_std * 0.5, 2)
        target = round(upper1, 2)

    # --- Rejection ---
    elif crosses_below and above_count >= 3 and price < vwap_val:
        setup = "VWAP Rejection"
        bias = "SHORT"
        notes = "Price broke above VWAP and failed back below — rejection = short"
        entry = round(vwap_val - vwap_std * 0.1, 2)
        stop = round(vwap_val + vwap_std * 0.5, 2)
        target = round(lower1, 2)

    # --- Break Long ---
    elif crosses_above and vol_confirmed and price > vwap_val:
        setup = "VWAP Break Long"
        bias = "LONG"
        notes = "Clean break above VWAP with volume confirmation"
        entry = round(vwap_val + vwap_std * 0.1, 2)
        stop = round(vwap_val - vwap_std * 0.5, 2)
        target = round(upper1, 2)

    # --- Break Short ---
    elif crosses_below and vol_confirmed and price < vwap_val:
        setup = "VWAP Break Short"
        bias = "SHORT"
        notes = "Clean break below VWAP with volume confirmation"
        entry = round(vwap_val - vwap_std * 0.1, 2)
        stop = round(vwap_val + vwap_std * 0.5, 2)
        target = round(lower1, 2)

    # --- Bounce Long ---
    elif price > vwap_val and abs(distance_pct) < 0.5 and above_count >= 5:
        setup = "VWAP Bounce Long"
        bias = "LONG"
        notes = "Price pulled back to VWAP and holding above — bounce long"
        entry = round(vwap_val + vwap_std * 0.1, 2)
        stop = round(vwap_val - vwap_std * 0.5, 2)
        target = round(upper1, 2)

    # --- Bounce Short ---
    elif price < vwap_val and abs(distance_pct) < 0.5 and below_count >= 5:
        setup = "VWAP Bounce Short"
        bias = "SHORT"
        notes = "Price rallied to VWAP from below and rejecting — bounce short"
        entry = round(vwap_val - vwap_std * 0.1, 2)
        stop = round(vwap_val + vwap_std * 0.5, 2)
        target = round(lower1, 2)

    # --- No clear setup ---
    else:
        setup = "No Setup"
        if price > vwap_val:
            bias = "BULLISH"
            notes = "Price above VWAP but no clean setup — wait for pullback or break"
        elif price < vwap_val:
            bias = "BEARISH"
            notes = "Price below VWAP but no clean setup — wait for rally to VWAP or break"
        else:
            bias = "NEUTRAL"
            notes = "Price at VWAP — watch for directional move"
        entry = None
        stop = None
        target = None

    # Price vs VWAP label
    if distance_pct > 0.1:
        price_vs_vwap = "ABOVE"
    elif distance_pct < -0.1:
        price_vs_vwap = "BELOW"
    else:
        price_vs_vwap = "AT"

    # Risk/reward
    risk_reward = None
    if entry and stop and target:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        risk_reward = round(reward / risk, 2) if risk > 0 else 0

    return {
        "setup": setup,
        "bias": bias,
        "price_vs_vwap": price_vs_vwap,
        "distance_pct": round(distance_pct, 3),
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": risk_reward,
        "volume_confirmation": vol_confirmed,
        "notes": notes,
    }


# ─────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────

def analyze(ticker: str, bars: int = 200) -> dict:
    """Run full VWAP analysis on a ticker using 1m bars."""
    df = get_ohlcv(ticker, timeframe="1m", bars=bars)

    if df.empty or len(df) < 20:
        return {
            "ticker": ticker.upper(),
            "error": f"Insufficient data: got {len(df)} bars, need at least 20",
        }

    df = compute_vwap(df)
    last = df.iloc[-1]
    setup = detect_setup(df)

    return {
        "ticker": ticker.upper(),
        "timeframe": "1m",
        "bars": len(df),
        "price": round(float(last["close"]), 2),
        "vwap": round(float(last["vwap"]), 4),
        "bands": {
            "upper_2σ": round(float(last["vwap_upper_2"]), 4),
            "upper_1σ": round(float(last["vwap_upper_1"]), 4),
            "lower_1σ": round(float(last["vwap_lower_1"]), 4),
            "lower_2σ": round(float(last["vwap_lower_2"]), 4),
        },
        "price_vs_vwap": setup["price_vs_vwap"],
        "distance_pct": setup["distance_pct"],
        "setup": setup["setup"],
        "bias": setup["bias"],
        "entry": setup["entry"],
        "stop": setup["stop"],
        "target": setup["target"],
        "risk_reward": setup["risk_reward"],
        "volume_confirmation": setup["volume_confirmation"],
        "notes": setup["notes"],
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    if len(sys.argv) < 2:
        print("Usage: python scripts/vwap_watcher.py TICKER")
        print("  Example: python scripts/vwap_watcher.py NVDA")
        sys.exit(1)

    ticker = sys.argv[1]
    result = analyze(ticker)
    print(json.dumps(result, indent=2, default=str))
