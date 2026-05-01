"""
postmarket_summarizer.py — Post-Market Daily Summary
=====================================================
Generates end-of-day summary with VWAP, volume, candle assessment,
after-hours movement, and next-day key levels.

Data source priority: TradingView (extended_session) → yfinance

Usage:
    python scripts/postmarket_summarizer.py TICKER
"""

import sys
import json
import logging
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_ohlcv_smart, get_earnings

logger = logging.getLogger(__name__)

SECRETS = Path(__file__).parent.parent.parent / ".secrets" / "tradingview.json"


def _fetch_extended_tv(ticker: str, n_bars: int = 2000) -> pd.DataFrame | None:
    """Fetch 5m bars with extended session from TradingView Pro Premium."""
    try:
        from tvDatafeed import TvDatafeed, Interval
        token = None
        if SECRETS.exists():
            creds = json.load(open(SECRETS))
            token = creds.get("auth_token")
        tv = TvDatafeed()
        if token:
            tv.token = token
        df = tv.get_hist(ticker, "NASDAQ", Interval.in_5_minute, n_bars=n_bars, extended_session=True)
        if df is None or df.empty:
            for exch in ["NYSE", "AMEX"]:
                df = tv.get_hist(ticker, exch, Interval.in_5_minute, n_bars=n_bars, extended_session=True)
                if df is not None and not df.empty:
                    break
        return df
    except Exception as e:
        logger.warning(f"TV extended fetch failed for {ticker}: {e}")
        return None


def _candle_assessment(open_price: float, high: float, low: float, close: float) -> dict:
    """Assess the daily candle pattern."""
    body = abs(close - open_price)
    full_range = high - low
    if full_range == 0:
        return {"pattern": "doji", "quality": "neutral", "notes": "No range — flat day"}

    body_pct = body / full_range * 100
    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low

    bullish = close > open_price

    if body_pct < 10:
        pattern = "doji"
        quality = "neutral"
        notes = "Indecision candle — wait for next day's direction"
    elif bullish and lower_wick > body * 2:
        pattern = "hammer"
        quality = "bullish"
        notes = "Hammer — bullish reversal signal at support"
    elif not bullish and upper_wick > body * 2:
        pattern = "shooting-star"
        quality = "bearish"
        notes = "Shooting star — bearish reversal signal at resistance"
    elif bullish and body_pct > 70:
        pattern = "strong-bullish"
        quality = "bullish"
        notes = "Strong bullish candle — buyers dominated all day"
    elif not bullish and body_pct > 70:
        pattern = "strong-bearish"
        quality = "bearish"
        notes = "Strong bearish candle — sellers dominated all day"
    elif bullish and close > (high - full_range * 0.25):
        pattern = "close-near-high"
        quality = "bullish"
        notes = "Closed near the high — bullish momentum into close"
    elif not bullish and close < (low + full_range * 0.25):
        pattern = "close-near-low"
        quality = "bearish"
        notes = "Closed near the low — bearish momentum into close"
    else:
        pattern = "inside" if body_pct < 40 else "normal"
        quality = "bullish" if bullish else "bearish"
        notes = f"{'Green' if bullish else 'Red'} candle, {'tight' if body_pct < 40 else 'normal'} range"

    return {"pattern": pattern, "quality": quality, "body_pct": round(body_pct, 1), "notes": notes}


def summarize(ticker: str, fast: bool = False) -> dict:
    """Generate post-market summary for a ticker."""
    ticker = ticker.upper()

    # Intraday 5m bars — TV primary, yfinance fallback
    df, source = get_ohlcv_smart(ticker, "5m", 200)
    if df.empty:
        return {"ticker": ticker, "error": "No intraday data available"}

    df.columns = [c.lower() for c in df.columns]

    # Core price levels
    open_price = float(df["open"].iloc[0])
    close_price = float(df["close"].iloc[-1])
    high = float(df["high"].max())
    low = float(df["low"].min())
    day_change_pct = (close_price - open_price) / open_price * 100

    # Volume analysis
    total_volume = int(df["volume"].sum())
    daily_df, daily_src = get_ohlcv_smart(ticker, "1D", 30)
    daily_df.columns = [c.lower() for c in daily_df.columns]
    avg_volume = float(daily_df["volume"].mean()) if not daily_df.empty else 0
    volume_ratio = total_volume / avg_volume if avg_volume > 0 else 0.0

    # VWAP calculation
    tp = (df["high"] + df["low"] + df["close"]) / 3
    cumvol = df["volume"].cumsum()
    vwap_series = (tp * df["volume"]).cumsum() / cumvol.where(cumvol > 0, 1)
    vwap_close = float(vwap_series.iloc[-1])
    close_vs_vwap = "ABOVE" if close_price > vwap_close else "BELOW"
    vwap_dist_pct = round((close_price - vwap_close) / vwap_close * 100, 2) if vwap_close > 0 else 0

    # Candle assessment
    candle = _candle_assessment(open_price, high, low, close_price)

    # After-hours data — try TV extended session (skip in fast mode)
    ah_price = None
    ah_change_pct = None
    ah_volume = None
    ah_source = None
    ext_df = None if fast else _fetch_extended_tv(ticker, 500)
    if ext_df is not None and not ext_df.empty:
        ext_df.columns = [c.lower() for c in ext_df.columns]
        ext_df.index = pd.to_datetime(ext_df.index)
        # Convert to ET for session filtering
        if ext_df.index.tz is None:
            try:
                ext_df.index = ext_df.index.tz_localize("Asia/Dubai").tz_convert("America/New_York")
            except Exception:
                ext_df.index = ext_df.index.tz_localize("UTC").tz_convert("America/New_York")
        else:
            ext_df.index = ext_df.index.tz_convert("America/New_York")
        today = ext_df.index.date[-1]
        today_ext = ext_df[ext_df.index.date == today]
        ah = today_ext.between_time("16:00", "20:00")
        if not ah.empty:
            ah_price = float(ah["close"].iloc[-1])
            ah_change_pct = round((ah_price - close_price) / close_price * 100, 2)
            ah_volume = int(ah["volume"].sum())
            ah_source = "tradingview"
    # Fallback to yfinance
    if ah_price is None:
        try:
            import yfinance as yf
            ext = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
            if not ext.empty:
                ext.columns = [c.lower() for c in ext.columns]
                ah_price = float(ext["close"].iloc[-1])
                ah_change_pct = round((ah_price - close_price) / close_price * 100, 2)
                ah_source = "yfinance"
        except Exception:
            pass

    # Key levels for tomorrow (from daily bars)
    tomorrow_levels = {}
    if not daily_df.empty and len(daily_df) >= 5:
        tomorrow_levels = {
            "prev_high": round(high, 2),
            "prev_low": round(low, 2),
            "prev_close": round(close_price, 2),
            "vwap": round(vwap_close, 2),
            "5d_high": round(float(daily_df["high"].tail(5).max()), 2),
            "5d_low": round(float(daily_df["low"].tail(5).min()), 2),
        }

    # Earnings check (skip in fast mode)
    next_earnings = None
    if not fast:
        earnings = get_earnings(ticker)
        next_earnings = earnings.get("next_date")

    summary_text = (
        f"{ticker} closed {day_change_pct:+.2f}%, {close_vs_vwap} VWAP "
        f"({vwap_dist_pct:+.2f}%), volume {volume_ratio:.1f}x avg. "
        f"{candle['notes']}"
    )
    if ah_price and ah_change_pct:
        summary_text += f" AH: {ah_change_pct:+.2f}%."

    return {
        "ticker": ticker,
        "open": round(open_price, 2),
        "close": round(close_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "day_change_pct": round(day_change_pct, 2),
        "total_volume": total_volume,
        "avg_volume": round(avg_volume),
        "volume_ratio": round(volume_ratio, 2),
        "vwap_close": round(vwap_close, 2),
        "vwap_dist_pct": vwap_dist_pct,
        "close_vs_vwap": close_vs_vwap,
        "candle": candle,
        "ah_price": ah_price,
        "ah_change_pct": ah_change_pct,
        "ah_volume": ah_volume,
        "ah_source": ah_source,
        "tomorrow_levels": tomorrow_levels,
        "next_earnings": next_earnings,
        "summary_text": summary_text,
        "data_source": f"intraday={source}, daily={daily_src}",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python scripts/postmarket_summarizer.py TICKER [--fast]")
        sys.exit(1)
    fast_mode = "--fast" in sys.argv
    ticker_arg = [a for a in sys.argv[1:] if not a.startswith("--")][0]
    print(json.dumps(summarize(ticker_arg, fast=fast_mode), indent=2, default=str))
