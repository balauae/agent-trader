"""
pattern_finder.py — Chart pattern detection for TradeDesk
==========================================================
Usage: python scripts/pattern_finder.py TICKER
"""

import sys
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_ohlcv

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def find_swing_highs(df: pd.DataFrame, window: int = 5) -> pd.Series:
    highs = df["high"]
    is_high = highs == highs.rolling(window * 2 + 1, center=True).max()
    return df[is_high].index.tolist()

def find_swing_lows(df: pd.DataFrame, window: int = 5) -> pd.Series:
    lows = df["low"]
    is_low = lows == lows.rolling(window * 2 + 1, center=True).min()
    return df[is_low].index.tolist()

def linreg_slope(series: pd.Series) -> float:
    x = np.arange(len(series))
    slope, _ = np.polyfit(x, series.values, 1)
    return float(slope)


# ─────────────────────────────────────────────
# PATTERN DETECTORS
# ─────────────────────────────────────────────

def detect_bull_flag(df: pd.DataFrame) -> dict | None:
    if len(df) < 15:
        return None
    # Look for flagpole: 5+ bars up >8%
    for i in range(len(df) - 12, len(df) - 5):
        if i < 0:
            continue
        pole_start = df.iloc[i]["close"]
        pole_end = df.iloc[i + 5]["close"]
        pole_gain = (pole_end - pole_start) / pole_start * 100
        if pole_gain < 8:
            continue
        # Flag: consolidation 3-7 bars after pole
        flag = df.iloc[i + 5: i + 10]
        if len(flag) < 3:
            continue
        flag_range = (flag["high"].max() - flag["low"].min()) / flag["high"].max() * 100
        if flag_range < 5:  # tight consolidation
            bars_ago = len(df) - (i + 10)
            target = pole_end + (pole_end - pole_start)
            entry = flag["high"].max()
            stop = flag["low"].min()
            confidence = min(95, int(60 + pole_gain * 0.5 + (5 - flag_range)))
            return {
                "pattern": "Bull Flag",
                "bias": "BULLISH",
                "confidence": confidence,
                "description": f"Flagpole +{pole_gain:.1f}% over 5 bars, consolidation range {flag_range:.1f}%",
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "bars_ago": max(0, bars_ago),
            }
    return None


def detect_bear_flag(df: pd.DataFrame) -> dict | None:
    if len(df) < 15:
        return None
    for i in range(len(df) - 12, len(df) - 5):
        if i < 0:
            continue
        pole_start = df.iloc[i]["close"]
        pole_end = df.iloc[i + 5]["close"]
        pole_drop = (pole_start - pole_end) / pole_start * 100
        if pole_drop < 8:
            continue
        flag = df.iloc[i + 5: i + 10]
        if len(flag) < 3:
            continue
        flag_range = (flag["high"].max() - flag["low"].min()) / flag["high"].max() * 100
        if flag_range < 5:
            bars_ago = len(df) - (i + 10)
            target = pole_end - (pole_start - pole_end)
            entry = flag["low"].min()
            stop = flag["high"].max()
            confidence = min(95, int(60 + pole_drop * 0.5 + (5 - flag_range)))
            return {
                "pattern": "Bear Flag",
                "bias": "BEARISH",
                "confidence": confidence,
                "description": f"Flagpole -{pole_drop:.1f}% over 5 bars, consolidation range {flag_range:.1f}%",
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "bars_ago": max(0, bars_ago),
            }
    return None


def detect_double_bottom(df: pd.DataFrame) -> dict | None:
    if len(df) < 20:
        return None
    lows = df["low"].values
    closes = df["close"].values
    # Find two similar lows in last 30 bars
    for i in range(max(0, len(lows) - 30), len(lows) - 5):
        for j in range(i + 5, len(lows) - 2):
            l1, l2 = lows[i], lows[j]
            if abs(l1 - l2) / l1 > 0.02:  # within 2%
                continue
            # Peak between them (neckline)
            neckline = max(closes[i:j])
            current = closes[-1]
            if current < neckline * 0.99:  # not yet broken out
                continue
            depth = neckline - min(l1, l2)
            target = neckline + depth
            confidence = min(90, 65 + int((1 - abs(l1 - l2) / l1) * 50))
            return {
                "pattern": "Double Bottom",
                "bias": "BULLISH",
                "confidence": confidence,
                "description": f"Two lows at ${l1:.2f} and ${l2:.2f}, neckline ${neckline:.2f} broken",
                "entry": round(neckline, 2),
                "stop": round(min(l1, l2) * 0.99, 2),
                "target": round(target, 2),
                "bars_ago": len(lows) - j - 1,
            }
    return None


def detect_double_top(df: pd.DataFrame) -> dict | None:
    if len(df) < 20:
        return None
    highs = df["high"].values
    closes = df["close"].values
    for i in range(max(0, len(highs) - 30), len(highs) - 5):
        for j in range(i + 5, len(highs) - 2):
            h1, h2 = highs[i], highs[j]
            if abs(h1 - h2) / h1 > 0.02:
                continue
            neckline = min(closes[i:j])
            current = closes[-1]
            if current > neckline * 1.01:
                continue
            depth = max(h1, h2) - neckline
            target = neckline - depth
            confidence = min(90, 65 + int((1 - abs(h1 - h2) / h1) * 50))
            return {
                "pattern": "Double Top",
                "bias": "BEARISH",
                "confidence": confidence,
                "description": f"Two highs at ${h1:.2f} and ${h2:.2f}, neckline ${neckline:.2f} broken",
                "entry": round(neckline, 2),
                "stop": round(max(h1, h2) * 1.01, 2),
                "target": round(target, 2),
                "bars_ago": len(highs) - j - 1,
            }
    return None


def detect_wedge(df: pd.DataFrame) -> dict | None:
    if len(df) < 20:
        return None
    recent = df.tail(20)
    high_slope = linreg_slope(recent["high"])
    low_slope = linreg_slope(recent["low"])
    current = float(recent["close"].iloc[-1])

    # Rising wedge: both slopes positive but converging (bearish)
    if high_slope > 0 and low_slope > 0 and low_slope > high_slope:
        return {
            "pattern": "Rising Wedge",
            "bias": "BEARISH",
            "confidence": 65,
            "description": f"Converging upward channel — high slope {high_slope:.3f}, low slope {low_slope:.3f}",
            "entry": round(current, 2),
            "stop": round(float(recent["high"].max()), 2),
            "target": round(float(recent["low"].min()), 2),
            "bars_ago": 0,
        }
    # Falling wedge: both slopes negative but converging (bullish)
    if high_slope < 0 and low_slope < 0 and high_slope < low_slope:
        return {
            "pattern": "Falling Wedge",
            "bias": "BULLISH",
            "confidence": 65,
            "description": f"Converging downward channel — high slope {high_slope:.3f}, low slope {low_slope:.3f}",
            "entry": round(current, 2),
            "stop": round(float(recent["low"].min()), 2),
            "target": round(float(recent["high"].max()), 2),
            "bars_ago": 0,
        }
    return None


def detect_triangle(df: pd.DataFrame) -> dict | None:
    if len(df) < 20:
        return None
    recent = df.tail(20)
    high_slope = linreg_slope(recent["high"])
    low_slope = linreg_slope(recent["low"])
    # Symmetrical triangle: highs descending, lows ascending
    if high_slope < -0.05 and low_slope > 0.05:
        current = float(recent["close"].iloc[-1])
        apex = (float(recent["high"].iloc[-1]) + float(recent["low"].iloc[-1])) / 2
        return {
            "pattern": "Symmetrical Triangle",
            "bias": "NEUTRAL",
            "confidence": 60,
            "description": "Coiling price action — watch for breakout direction",
            "entry": round(float(recent["high"].iloc[-1]), 2),
            "stop": round(float(recent["low"].iloc[-1]), 2),
            "target": None,
            "bars_ago": 0,
        }
    return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def analyze(ticker: str) -> dict:
    t = ticker.upper()
    df = get_ohlcv(t, "1D", bars=60)
    if df.empty or len(df) < 20:
        return {"ticker": t, "error": "Insufficient data", "patterns_found": [], "overall_bias": "NEUTRAL"}

    detectors = [
        detect_bull_flag,
        detect_bear_flag,
        detect_double_bottom,
        detect_double_top,
        detect_wedge,
        detect_triangle,
    ]

    patterns = []
    for fn in detectors:
        try:
            result = fn(df)
            if result:
                patterns.append(result)
        except Exception as e:
            logger.warning(f"{fn.__name__} failed: {e}")

    # Sort by confidence
    patterns.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    best = patterns[0] if patterns else None

    # Overall bias
    if patterns:
        bull = sum(1 for p in patterns if p["bias"] == "BULLISH")
        bear = sum(1 for p in patterns if p["bias"] == "BEARISH")
        if bull > bear:
            overall_bias = "BULLISH"
        elif bear > bull:
            overall_bias = "BEARISH"
        else:
            overall_bias = "NEUTRAL"
    else:
        overall_bias = "NEUTRAL"

    summary = f"No patterns detected — neutral." if not best else \
        f"{best['pattern']} detected ({best['confidence']}% confidence). {best['description']}"

    return {
        "ticker": t,
        "patterns_found": patterns,
        "best_pattern": best,
        "overall_bias": overall_bias,
        "summary_text": summary,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python scripts/pattern_finder.py TICKER")
        sys.exit(1)
    print(json.dumps(analyze(sys.argv[1]), indent=2, default=str))
