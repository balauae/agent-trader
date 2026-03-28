"""
technical_analyst.py — Technical indicator analysis for TradeDesk
================================================================
Usage:
    python scripts/technical_analyst.py TICKER [timeframe]
    python scripts/technical_analyst.py NVDA 5m
    python scripts/technical_analyst.py AAPL 1D

Outputs JSON with bias, confluence score, indicators, levels, signals,
stop/target, and risk/reward.
"""

import sys
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running as script with correct imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_ohlcv

logger = logging.getLogger(__name__)

INTRADAY_TFS = {"1m", "5m", "15m", "30m"}


# ─────────────────────────────────────────────
# INDICATOR CALCULATIONS (pure pandas/numpy)
# ─────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def rsi(close: pd.Series, period=14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bollinger_bands(close: pd.Series, period=20, std_dev=2):
    mid = sma(close, period)
    std = close.rolling(window=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    cum_tp_vol = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    return cum_tp_vol / cum_vol


# Williams %R (14-period)
def compute_williams_r(df, period=14):
    highest_high = df["high"].rolling(period).max()
    lowest_low = df["low"].rolling(period).min()
    wr = -100 * (highest_high - df["close"]) / (highest_high - lowest_low)
    return float(wr.iloc[-1])


# ─────────────────────────────────────────────
# SIGNAL DETECTION
# ─────────────────────────────────────────────

def detect_signals(ind: dict, timeframe: str) -> list[str]:
    signals = []

    # EMA crossovers (check last 2 bars worth of data isn't available here,
    # so we check relative position)
    if ind["ema_9"] > ind["ema_21"]:
        signals.append("EMA9 above EMA21 — short-term bullish")
    else:
        signals.append("EMA9 below EMA21 — short-term bearish")

    # Golden / Death cross
    if ind["sma_50"] is not None and ind["sma_200"] is not None:
        if ind["sma_50"] > ind["sma_200"]:
            signals.append("SMA50 above SMA200 — golden cross territory")
        else:
            signals.append("SMA50 below SMA200 — death cross territory")

    # Price vs key MAs
    price = ind["close"]
    if ind["sma_200"] is not None:
        if price > ind["sma_200"]:
            signals.append("Price above SMA200 — long-term uptrend")
        else:
            signals.append("Price below SMA200 — long-term downtrend")

    # MACD
    if ind["macd_histogram"] > 0:
        signals.append("MACD histogram positive — bullish momentum")
    else:
        signals.append("MACD histogram negative — bearish momentum")

    if ind["macd_line"] > ind["macd_signal"]:
        signals.append("MACD line above signal — bullish crossover")
    else:
        signals.append("MACD line below signal — bearish crossover")

    # RSI
    rsi_val = ind["rsi"]
    if rsi_val >= 70:
        signals.append(f"RSI {rsi_val:.1f} — overbought")
    elif rsi_val <= 30:
        signals.append(f"RSI {rsi_val:.1f} — oversold")
    elif rsi_val >= 60:
        signals.append(f"RSI {rsi_val:.1f} — bullish zone")
    elif rsi_val <= 40:
        signals.append(f"RSI {rsi_val:.1f} — bearish zone")
    else:
        signals.append(f"RSI {rsi_val:.1f} — neutral")

    # Bollinger Bands
    if price >= ind["bb_upper"]:
        signals.append("Price at upper Bollinger Band — possible resistance / overbought")
    elif price <= ind["bb_lower"]:
        signals.append("Price at lower Bollinger Band — possible support / oversold")

    bb_width = (ind["bb_upper"] - ind["bb_lower"]) / ind["bb_mid"] if ind["bb_mid"] else 0
    if bb_width < 0.04:
        signals.append("Bollinger Band squeeze — volatility expansion imminent")

    # Volume
    if ind["volume_above_avg"]:
        signals.append("Volume above 20-SMA — confirming move")
    else:
        signals.append("Volume below 20-SMA — weak participation")

    # VWAP (intraday only)
    if timeframe in INTRADAY_TFS and ind.get("vwap") is not None:
        if price > ind["vwap"]:
            signals.append("Price above VWAP — intraday bullish")
        else:
            signals.append("Price below VWAP — intraday bearish")

    return signals


# ─────────────────────────────────────────────
# CONFLUENCE SCORING
# ─────────────────────────────────────────────

def compute_confluence(ind: dict, timeframe: str) -> tuple[int, int, str]:
    """Returns (bullish_count, total_checks, bias)."""
    bullish = 0
    total = 0

    # 1. EMA alignment
    total += 1
    if ind["ema_9"] > ind["ema_21"]:
        bullish += 1

    # 2. MACD
    total += 1
    if ind["macd_histogram"] > 0:
        bullish += 1

    # 3. RSI
    total += 1
    if ind["rsi"] > 50:
        bullish += 1

    # 4. Price vs SMA200 (or SMA50 if 200 unavailable)
    ref_ma = ind["sma_200"] if ind["sma_200"] is not None else ind["sma_50"]
    if ref_ma is not None:
        total += 1
        if ind["close"] > ref_ma:
            bullish += 1

    # 5. VWAP (intraday) or Bollinger position (daily)
    total += 1
    if timeframe in INTRADAY_TFS and ind.get("vwap") is not None:
        if ind["close"] > ind["vwap"]:
            bullish += 1
    else:
        mid = (ind["bb_upper"] + ind["bb_lower"]) / 2
        if ind["close"] > mid:
            bullish += 1

    bearish = total - bullish
    if bullish >= 4:
        bias = "BULLISH"
    elif bearish >= 4:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return bullish, total, bias


# ─────────────────────────────────────────────
# LEVELS
# ─────────────────────────────────────────────

def compute_levels(df: pd.DataFrame, ind: dict, timeframe: str) -> dict:
    recent = df.tail(20)
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    levels = {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "ema_9": round(ind["ema_9"], 2),
        "ema_21": round(ind["ema_21"], 2),
        "bb_upper": round(ind["bb_upper"], 2),
        "bb_lower": round(ind["bb_lower"], 2),
    }

    if ind["sma_50"] is not None:
        levels["sma_50"] = round(ind["sma_50"], 2)
    if ind["sma_200"] is not None:
        levels["sma_200"] = round(ind["sma_200"], 2)
    if timeframe in INTRADAY_TFS and ind.get("vwap") is not None:
        levels["vwap"] = round(ind["vwap"], 2)

    return levels


# ─────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────

def analyze(ticker: str, timeframe: str = "1D", bars: int = 200) -> dict:
    df = get_ohlcv(ticker, timeframe=timeframe, bars=bars)

    if df.empty or len(df) < 30:
        return {
            "ticker": ticker.upper(),
            "timeframe": timeframe,
            "error": f"Insufficient data: got {len(df)} bars, need at least 30",
        }

    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    # Compute indicators
    ema_9 = ema(c, 9)
    ema_21 = ema(c, 21)
    sma_50 = sma(c, 50) if len(df) >= 50 else pd.Series([np.nan] * len(df))
    sma_200 = sma(c, 200) if len(df) >= 200 else pd.Series([np.nan] * len(df))
    macd_line, macd_signal, macd_hist = macd(c)
    rsi_val = rsi(c)
    bb_upper, bb_mid, bb_lower = bollinger_bands(c)
    atr_val = atr(h, l, c)
    vol_sma = sma(v, 20)

    # VWAP only for intraday
    vwap_val = vwap(h, l, c, v) if timeframe in INTRADAY_TFS else pd.Series([np.nan] * len(df))

    # Latest values
    last = len(df) - 1
    price = float(c.iloc[last])

    def safe(s, idx=last):
        val = s.iloc[idx]
        return round(float(val), 4) if pd.notna(val) else None

    williams_r_val = round(compute_williams_r(df), 2) if len(df) >= 14 else None

    ind = {
        "close": price,
        "ema_9": safe(ema_9),
        "ema_21": safe(ema_21),
        "sma_50": safe(sma_50),
        "sma_200": safe(sma_200),
        "macd_line": safe(macd_line),
        "macd_signal": safe(macd_signal),
        "macd_histogram": safe(macd_hist),
        "rsi": safe(rsi_val),
        "williams_r": williams_r_val,
        "bb_upper": safe(bb_upper),
        "bb_mid": safe(bb_mid),
        "bb_lower": safe(bb_lower),
        "atr": safe(atr_val),
        "vwap": safe(vwap_val),
        "volume": float(v.iloc[last]),
        "volume_sma_20": safe(vol_sma),
        "volume_above_avg": bool(v.iloc[last] > vol_sma.iloc[last]) if pd.notna(vol_sma.iloc[last]) else None,
    }

    # Signals
    signals = detect_signals(ind, timeframe)

    # Confluence
    bull_count, total, bias = compute_confluence(ind, timeframe)

    # Levels
    levels = compute_levels(df, ind, timeframe)

    # Stop / target / R:R
    atr_now = ind["atr"] if ind["atr"] else 0
    if bias == "BULLISH":
        stop_loss = round(price - 1.5 * atr_now, 2)
        take_profit = levels["resistance"]
        entry_risk = price - stop_loss
    elif bias == "BEARISH":
        stop_loss = round(price + 1.5 * atr_now, 2)
        take_profit = levels["support"]
        entry_risk = stop_loss - price
    else:
        stop_loss = round(price - 1.5 * atr_now, 2)
        take_profit = levels["resistance"]
        entry_risk = price - stop_loss

    reward = abs(take_profit - price)
    risk_reward = round(reward / entry_risk, 2) if entry_risk > 0 else 0

    # Weinstein Stage Analysis
    def compute_weinstein_stage(df):
        close = df["close"]
        if len(close) < 150:
            return {"stage": 0, "label": "INSUFFICIENT_DATA"}
        ma150 = close.rolling(150).mean()
        current_ma = float(ma150.iloc[-1])
        prev_ma = float(ma150.iloc[-5])
        p = float(close.iloc[-1])
        ma_trend = "up" if current_ma > prev_ma else "down" if current_ma < prev_ma else "flat"
        if p > current_ma and ma_trend == "up":
            stage, label = 2, "ADVANCING"
        elif p > current_ma and ma_trend in ("flat", "down"):
            stage, label = 3, "TOPPING"
        elif p < current_ma and ma_trend == "down":
            stage, label = 4, "DECLINING"
        else:
            stage, label = 1, "BASING"
        return {
            "stage": stage, "label": label,
            "ma_150": round(current_ma, 2), "ma_trend": ma_trend,
            "notes": f"Stage {stage}: {label} — {'BUY ZONE' if stage==2 else 'AVOID' if stage==4 else 'WAIT'}"
        }

    return {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "price": round(price, 2),
        "bias": bias,
        "confluence_score": f"{bull_count}/{total}",
        "indicators": ind,
        "levels": levels,
        "signals": signals,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward": risk_reward,
        "weinstein": compute_weinstein_stage(df),
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    if len(sys.argv) < 2:
        print("Usage: python scripts/technical_analyst.py TICKER [timeframe]")
        print("  timeframe: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1D (default), 1W")
        sys.exit(1)

    ticker = sys.argv[1]
    tf = sys.argv[2] if len(sys.argv) > 2 else "1D"

    result = analyze(ticker, timeframe=tf)
    print(json.dumps(result, indent=2, default=str))
