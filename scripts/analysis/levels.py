"""
Support & Resistance Detector
Detects key price levels using swing pivots, volume clusters,
round numbers, previous day/week highs-lows, and moving averages.

Usage: python scripts/support_resistance.py TICKER [timeframe] [bars]
Output: JSON to stdout
"""
import sys
import json
import warnings
from pathlib import Path
from datetime import datetime, timezone

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf
from scripts.data.fetcher import get_ohlcv_smart

# ── config ────────────────────────────────────────────────────────────────────
SWING_WINDOW     = 5      # bars left/right to confirm pivot
CLUSTER_PCT      = 0.003  # merge levels within 0.3%
HVN_MULTIPLIER   = 1.5    # volume threshold for high-volume node
ROUND_INCREMENTS = [1, 2, 5, 10, 25, 50]  # round number steps to check
PROXIMITY_RANGE  = 0.05   # only show levels within 5% of current price
MAX_LEVELS       = 6      # max resistance / support levels to return


# ── helpers ───────────────────────────────────────────────────────────────────

def fetch_data_yfinance(ticker: str, timeframe: str, bars: int) -> pd.DataFrame:
    tf_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "60m", "2h": "90m", "4h": "1h",
        "1D": "1d", "1W": "1wk",
    }
    period_map = {
        "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
        "1h": "730d", "60m": "730d", "90m": "730d",
        "1d": "2y", "1wk": "5y",
    }
    yf_tf = tf_map.get(timeframe, "1d")
    period = period_map.get(yf_tf, "2y")
    df = yf.download(ticker, period=period, interval=yf_tf,
                     progress=False, auto_adjust=True)
    if df.empty:
        return df
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower()
                  for c in df.columns]
    return df.tail(bars).copy()


def fetch_data(ticker: str, timeframe: str, bars: int, source: str = "smart") -> pd.DataFrame:
    """
    Fetch OHLCV data.
    source='smart' (default) = TV primary, yfinance fallback
    source='tv'              = TV only (fallback to yf if TV fails)
    source='yf'              = yfinance only
    """
    if source == "yf":
        return fetch_data_yfinance(ticker, timeframe, bars)
    # smart or tv — use get_ohlcv_smart (TV → yf fallback)
    df, _ = get_ohlcv_smart(ticker, timeframe, bars)
    if not df.empty:
        return df
    return fetch_data_yfinance(ticker, timeframe, bars)


def find_swing_pivots(df: pd.DataFrame, window: int = SWING_WINDOW):
    highs, lows = [], []
    for i in range(window, len(df) - window):
        h = df["high"].iloc[i]
        l = df["low"].iloc[i]
        if h == df["high"].iloc[i - window:i + window + 1].max():
            highs.append((i, float(h), len(df) - i))
        if l == df["low"].iloc[i - window:i + window + 1].min():
            lows.append((i, float(l), len(df) - i))
    return highs, lows


def find_volume_clusters(df: pd.DataFrame, bins: int = 20):
    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    bin_size = (price_max - price_min) / bins
    if bin_size == 0:
        return []

    vol_bins = {}
    for _, row in df.iterrows():
        bin_idx = int((row["close"] - price_min) / bin_size)
        bin_idx = min(bin_idx, bins - 1)
        vol_bins[bin_idx] = vol_bins.get(bin_idx, 0) + row["volume"]

    avg_vol = np.mean(list(vol_bins.values()))
    hvns = []
    for idx, vol in vol_bins.items():
        if vol >= avg_vol * HVN_MULTIPLIER:
            level = price_min + (idx + 0.5) * bin_size
            hvns.append(float(level))
    return hvns


def find_round_numbers(price: float, price_range_pct: float = PROXIMITY_RANGE):
    lo = price * (1 - price_range_pct)
    hi = price * (1 + price_range_pct)
    rounds = []
    # pick best increment for this price range
    if price > 200:
        increments = [5, 10, 25, 50]
    elif price > 50:
        increments = [1, 2, 5, 10]
    else:
        increments = [0.5, 1, 2, 5]

    for inc in increments:
        start = (int(lo / inc) + 1) * inc
        val = start
        while val <= hi:
            rounds.append(round(val, 2))
            val += inc
    return list(set(rounds))


def prev_day_week_levels(df: pd.DataFrame):
    levels = {}
    if len(df) >= 2:
        prev = df.iloc[-2]
        levels["PDH"] = float(prev["high"])
        levels["PDL"] = float(prev["low"])
    if len(df) >= 6:
        week = df.iloc[-6:-1]
        levels["PWH"] = float(week["high"].max())
        levels["PWL"] = float(week["low"].min())
    return levels


def moving_average_levels(df: pd.DataFrame):
    close = df["close"]
    levels = {}
    if len(close) >= 9:
        levels["EMA9"] = float(close.ewm(span=9).mean().iloc[-1])
    if len(close) >= 21:
        levels["EMA21"] = float(close.ewm(span=21).mean().iloc[-1])
    if len(close) >= 50:
        levels["SMA50"] = float(close.rolling(50).mean().iloc[-1])
    if len(close) >= 200:
        levels["SMA200"] = float(close.rolling(200).mean().iloc[-1])
    return levels


def cluster_levels(raw_levels: list, cluster_pct: float = CLUSTER_PCT):
    """Merge levels within cluster_pct of each other."""
    if not raw_levels:
        return []
    sorted_levels = sorted(raw_levels, key=lambda x: x["level"])
    clusters = [sorted_levels[0]]
    for item in sorted_levels[1:]:
        last = clusters[-1]
        if abs(item["level"] - last["level"]) / last["level"] <= cluster_pct:
            # merge: keep higher strength, average level
            if item["strength"] > last["strength"]:
                last["strength"] = item["strength"]
                last["label"] = item["label"]
                last["type"] = item["type"]
            last["level"] = round((last["level"] + item["level"]) / 2, 2)
        else:
            clusters.append(item)
    return clusters


def score_level(level: float, price: float, tests: int, is_hvn: bool,
                is_round: bool, bars_ago: int, is_ma: bool) -> int:
    score = 1
    if tests >= 3:
        score += 2
    elif tests >= 2:
        score += 1
    if is_hvn:
        score += 2
    if is_round:
        score += 1
    if bars_ago <= 20:
        score += 1
    if is_ma:
        score += 1
    return min(score, 5)


# ── main ──────────────────────────────────────────────────────────────────────

def compute_sr(ticker: str, timeframe: str = "1D", bars: int = 200, source: str = "yf") -> dict:
    df = fetch_data(ticker, timeframe, bars, source)
    actual_source = "tv" if source in ("tv", "smart") else "yfinance"
    if df.empty or len(df) < 30:
        return {"error": f"Insufficient data for {ticker}"}

    price = float(df["close"].iloc[-1])
    lo = price * (1 - PROXIMITY_RANGE)
    hi = price * (1 + PROXIMITY_RANGE)

    # ── swing pivots ─────────────────────────────────────────────────────────
    swing_highs, swing_lows = find_swing_pivots(df)

    # ── volume clusters ───────────────────────────────────────────────────────
    hvns = set(find_volume_clusters(df))

    # ── round numbers ─────────────────────────────────────────────────────────
    rounds = set(find_round_numbers(price))

    # ── PDH/PDL/PWH/PWL ──────────────────────────────────────────────────────
    prev_levels = prev_day_week_levels(df)

    # ── moving averages ───────────────────────────────────────────────────────
    ma_levels = moving_average_levels(df)

    # ── build resistance candidates ───────────────────────────────────────────
    resistance_raw = []
    support_raw = []

    # swing highs → resistance
    for idx, level, bars_ago in swing_highs:
        if lo <= level <= hi * 1.02:
            is_hvn = any(abs(level - h) / level < CLUSTER_PCT for h in hvns)
            is_round = any(abs(level - r) / level < CLUSTER_PCT for r in rounds)
            tests = sum(1 for _, l2, _ in swing_highs
                        if abs(l2 - level) / level < CLUSTER_PCT)
            strength = score_level(level, price, tests, is_hvn, is_round, bars_ago, False)
            if level > price:
                resistance_raw.append({
                    "level": round(level, 2),
                    "type": "swing_high",
                    "strength": strength,
                    "label": f"Swing high ({bars_ago}b ago)",
                })
            else:
                support_raw.append({
                    "level": round(level, 2),
                    "type": "swing_high_flipped",
                    "strength": strength - 1,
                    "label": f"Broken resistance → support ({bars_ago}b ago)",
                })

    # swing lows → support
    for idx, level, bars_ago in swing_lows:
        if lo * 0.98 <= level <= hi:
            is_hvn = any(abs(level - h) / level < CLUSTER_PCT for h in hvns)
            is_round = any(abs(level - r) / level < CLUSTER_PCT for r in rounds)
            tests = sum(1 for _, l2, _ in swing_lows
                        if abs(l2 - level) / level < CLUSTER_PCT)
            strength = score_level(level, price, tests, is_hvn, is_round, bars_ago, False)
            if level < price:
                support_raw.append({
                    "level": round(level, 2),
                    "type": "swing_low",
                    "strength": strength,
                    "label": f"Swing low ({bars_ago}b ago)",
                })

    # HVNs
    for h in hvns:
        if lo <= h <= hi:
            is_round = any(abs(h - r) / h < CLUSTER_PCT for r in rounds)
            s = {"level": round(h, 2), "type": "hvn", "strength": 3 + int(is_round),
                 "label": "High volume node"}
            if h > price:
                resistance_raw.append(s)
            else:
                support_raw.append(s)

    # Round numbers
    for r in rounds:
        if lo <= r <= hi:
            s = {"level": r, "type": "round_number", "strength": 2,
                 "label": f"Round number ${r:.0f}"}
            if r > price:
                resistance_raw.append(s)
            else:
                support_raw.append(s)

    # PDH/PDL/PWH/PWL
    for name, level in prev_levels.items():
        if lo <= level <= hi:
            s = {"level": round(level, 2), "type": name.lower(),
                 "strength": 3, "label": name}
            if level > price:
                resistance_raw.append(s)
            else:
                support_raw.append(s)

    # Moving averages
    for name, level in ma_levels.items():
        if lo <= level <= hi:
            s = {"level": round(level, 2), "type": "ma",
                 "strength": 3, "label": name}
            if level > price:
                resistance_raw.append(s)
            else:
                support_raw.append(s)

    # ── cluster + sort ────────────────────────────────────────────────────────
    resistance = sorted(
        cluster_levels(resistance_raw),
        key=lambda x: x["level"]
    )[:MAX_LEVELS]

    support = sorted(
        cluster_levels(support_raw),
        key=lambda x: -x["level"]
    )[:MAX_LEVELS]

    # ── key levels (strength >= 3) ────────────────────────────────────────────
    key_levels = sorted(
        [l["level"] for l in resistance + support if l["strength"] >= 3]
    )

    nearest_r = resistance[0]["level"] if resistance else None
    nearest_s = support[0]["level"] if support else None

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "timeframe": timeframe,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "resistance": resistance,
        "support": support,
        "key_levels": key_levels,
        "nearest_resistance": nearest_r,
        "nearest_support": nearest_s,
        "nearest_resistance_dist_pct": round(((nearest_r - price) / price) * 100, 2) if nearest_r else None,
        "nearest_support_dist_pct": round(((price - nearest_s) / price) * 100, 2) if nearest_s else None,
        "data_source": actual_source,
        "livermore_pivot": compute_livermore_pivot(df, price),
    }



def compute_livermore_pivot(df: pd.DataFrame, price: float) -> dict:
    """Detect Livermore-style pivot breakout with volume confirmation."""
    if len(df) < 20:
        return {}
    recent = df.tail(20)
    pivot_high = float(recent["high"].max())
    avg_vol = float(df["volume"].tail(50).mean())
    latest_vol = float(df["volume"].iloc[-1])
    vol_ratio = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 0
    above_pivot = price > pivot_high
    confirmed = above_pivot and vol_ratio >= 1.5
    ma20 = float(df["close"].rolling(20).mean().iloc[-1])
    lor = "UP" if price > ma20 else "DOWN"
    return {
        "pivot_level": round(pivot_high, 2),
        "price_vs_pivot": "ABOVE" if above_pivot else "BELOW",
        "volume_ratio": vol_ratio,
        "breakout_confirmed": confirmed,
        "line_of_least_resistance": lor,
        "notes": (f"Breakout confirmed on {vol_ratio}x volume" if confirmed
                  else f"Watching ${pivot_high:.2f} pivot — needs 1.5x volume to confirm")
    }


def compute_multi_sr(ticker: str, timeframes: list = None, bars: int = 200, source: str = "yf") -> dict:
    """Run S/R across multiple timeframes and find confluent levels."""
    if timeframes is None:
        timeframes = ["1D", "1h", "5m"]

    results = {}
    for tf in timeframes:
        r = compute_sr(ticker, tf, bars, source)
        if "error" not in r:
            results[tf] = r

    if not results:
        return {"error": "No data returned for any timeframe"}

    price = list(results.values())[0]["price"]

    # Collect all key levels across timeframes
    all_levels = {}
    for tf, data in results.items():
        for lvl in data.get("key_levels", []):
            matched = False
            for existing in list(all_levels.keys()):
                if abs(lvl - existing) / existing <= CLUSTER_PCT:
                    all_levels[existing].append(tf)
                    matched = True
                    break
            if not matched:
                all_levels[lvl] = [tf]

    # Confluent = appears in 2+ timeframes
    confluent = []
    for lvl, tfs in all_levels.items():
        if len(tfs) >= 2:
            confluent.append({
                "level": round(lvl, 2),
                "timeframes": tfs,
                "confluence_count": len(tfs),
                "side": "resistance" if lvl > price else "support",
                "strength": min(len(tfs) * 2, 5),
            })

    confluent.sort(key=lambda x: x["level"])

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "timeframes_analyzed": timeframes,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "confluent_levels": confluent,
        "by_timeframe": {tf: {
            "nearest_resistance": d["nearest_resistance"],
            "nearest_support": d["nearest_support"],
            "nearest_resistance_dist_pct": d["nearest_resistance_dist_pct"],
            "nearest_support_dist_pct": d["nearest_support_dist_pct"],
            "key_levels": d["key_levels"],
        } for tf, d in results.items()},
    }


if __name__ == "__main__":
    # Usage:
    #   Single:  python support_resistance.py GLD 1D 200 [--source tv]
    #   Multi:   python support_resistance.py GLD multi 1D,1h 200 [--source tv]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    source = "tv" if "--source" in sys.argv and "tv" in sys.argv[sys.argv.index("--source") + 1] else "yf"
    # Also support --source=tv
    for a in sys.argv:
        if a == "--source=tv":
            source = "tv"
        elif a == "--source=yf":
            source = "yf"

    ticker = args[0].upper() if len(args) > 0 else "AAPL"
    mode   = args[1] if len(args) > 1 else "1D"

    if mode == "multi":
        tfs  = args[2].split(",") if len(args) > 2 else ["1D", "1h", "5m"]
        bars = int(args[3]) if len(args) > 3 else 200
        result = compute_multi_sr(ticker, tfs, bars, source)
    else:
        bars = int(args[2]) if len(args) > 2 else 200
        result = compute_sr(ticker, mode, bars, source)

    print(json.dumps(result, indent=2))
