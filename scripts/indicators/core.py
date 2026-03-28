"""
indicators/core.py — Centralized technical indicator math.
All indicator calculations live here. Import from this module.

Usage:
    from scripts.indicators.core import rsi, ema, sma, macd, atr, bollinger, williams_r, vwap
"""
import pandas as pd
import numpy as np


def rsi(close: pd.Series, period: int = 14) -> float:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    r = 100 - (100 / (1 + rs))
    return float(r.iloc[-1])


def ema(close: pd.Series, span: int) -> float:
    """Exponential Moving Average — latest value."""
    return float(close.ewm(span=span, adjust=False).mean().iloc[-1])


def ema_series(close: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average — full series."""
    return close.ewm(span=span, adjust=False).mean()


def sma(close: pd.Series, period: int) -> float:
    """Simple Moving Average — latest value."""
    return float(close.rolling(period).mean().iloc[-1])


def sma_series(close: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average — full series."""
    return close.rolling(period).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD line, signal line, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd":      float(macd_line.iloc[-1]),
        "signal":    float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
    }


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def bollinger(close: pd.Series, period: int = 20, std: float = 2.0) -> dict:
    """Bollinger Bands — upper, middle (SMA), lower."""
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std()
    return {
        "upper":  float((mid + std * sd).iloc[-1]),
        "middle": float(mid.iloc[-1]),
        "lower":  float((mid - std * sd).iloc[-1]),
    }


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Williams %R oscillator. Range: -100 to 0. Overbought > -20, Oversold < -80."""
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    wr = -100 * (hh - close) / (hh - ll).replace(0, float("nan"))
    return float(wr.iloc[-1])


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> float:
    """Volume Weighted Average Price."""
    tp = (high + low + close) / 3
    return float((tp * volume).cumsum().iloc[-1] / volume.cumsum().iloc[-1])


def vwap_bands(high: pd.Series, low: pd.Series, close: pd.Series,
               volume: pd.Series, std_mult: float = 1.0) -> dict:
    """VWAP with standard deviation bands."""
    tp = (high + low + close) / 3
    cum_vol = volume.cumsum()
    cum_tp_vol = (tp * volume).cumsum()
    vwap_series = cum_tp_vol / cum_vol
    variance = ((tp - vwap_series) ** 2 * volume).cumsum() / cum_vol
    std_dev = variance.apply(lambda x: x ** 0.5 if x >= 0 else 0)
    v = float(vwap_series.iloc[-1])
    sd = float(std_dev.iloc[-1])
    return {
        "vwap":       v,
        "upper_2":    round(v + 2 * sd, 2),
        "upper_1":    round(v + sd, 2),
        "lower_1":    round(v - sd, 2),
        "lower_2":    round(v - 2 * sd, 2),
    }
