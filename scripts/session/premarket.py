"""
premarket_specialist.py — Pre-market gap analysis for TradeDesk
================================================================
Professional-grade premarket analysis: gap classification, RVOL, ATR%,
key level proximity, ORB candidate detection, Raschke 80/20 fade.

Data source priority: TradingView (extended_session) → yfinance

Usage:
    python scripts/session/premarket.py TICKER
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_ohlcv_smart

logger = logging.getLogger(__name__)

SECRETS = Path(__file__).parent.parent.parent / ".secrets" / "tradingview.json"


def _fetch_extended_tv(ticker: str, n_bars: int = 2000) -> pd.DataFrame | None:
    """Fetch 1m bars with extended session from TradingView Pro Premium."""
    try:
        from tvDatafeed import TvDatafeed, Interval
        token = None
        if SECRETS.exists():
            creds = json.load(open(SECRETS))
            token = creds.get("auth_token")
        tv = TvDatafeed()
        if token:
            tv.token = token
        df = tv.get_hist(ticker, "NASDAQ", Interval.in_1_minute, n_bars=n_bars, extended_session=True)
        if df is None or df.empty:
            for exch in ["NYSE", "AMEX"]:
                df = tv.get_hist(ticker, exch, Interval.in_1_minute, n_bars=n_bars, extended_session=True)
                if df is not None and not df.empty:
                    break
        return df
    except Exception as e:
        logger.warning(f"TV extended fetch failed for {ticker}: {e}")
        return None


def _fetch_extended_yf(ticker: str) -> pd.DataFrame | None:
    """Fallback: yfinance with prepost=True."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="5d", interval="1m", prepost=True)
        if df.empty:
            return None
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        logger.warning(f"yfinance extended fetch failed for {ticker}: {e}")
        return None


def analyze(ticker: str) -> dict:
    t = ticker.upper()

    # Try TradingView first, then yfinance
    df = _fetch_extended_tv(t)
    source = "tradingview"
    if df is None or df.empty:
        df = _fetch_extended_yf(t)
        source = "yfinance"
    if df is None or df.empty:
        return {"ticker": t, "error": "No data from TV or yfinance"}

    # Normalize
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        try:
            df.index = df.index.tz_localize("Asia/Dubai").tz_convert("America/New_York")
        except Exception:
            df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df.index = df.index.tz_convert("America/New_York")

    import pytz
    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)

    # Find available dates
    all_dates = sorted(set(df.index.date))
    today = all_dates[-1]

    today_df = df[df.index.date == today]
    premarket = today_df.between_time("04:00", "09:29")

    # Fallback to yesterday if no PM bars today
    if premarket.empty and len(all_dates) >= 2:
        yesterday = all_dates[-2]
        premarket = df[df.index.date == yesterday].between_time("04:00", "09:29")
        if not premarket.empty:
            today = yesterday
            today_df = df[df.index.date == today]

    # Prior close
    prior_days = df[df.index.date < today]
    prior_regular = prior_days.between_time("09:30", "16:00")
    prior_close = float(prior_regular["close"].iloc[-1]) if not prior_regular.empty else None

    if premarket.empty or prior_close is None:
        return {
            "ticker": t, "error": "No pre-market data available",
            "prior_close": prior_close, "data_source": source,
            "current_session": now_et.strftime("%I:%M %p ET"),
        }

    pm_price = float(premarket["close"].iloc[-1])
    pm_high = float(premarket["high"].max())
    pm_low = float(premarket["low"].min())
    pm_volume = float(premarket["volume"].sum())
    pm_range = pm_high - pm_low

    gap_pct = round((pm_price - prior_close) / prior_close * 100, 2)
    gap_direction = "UP" if gap_pct > 0.3 else "DOWN" if gap_pct < -0.3 else "FLAT"

    # ── Daily bars for ATR, key levels, volume avg ────────────
    daily_df, daily_src = get_ohlcv_smart(t, "1D", 60)
    daily_df.columns = [c.lower() for c in daily_df.columns]

    # ATR (14-period)
    atr_val = None
    atr_pct = None
    if not daily_df.empty and len(daily_df) >= 14:
        h = daily_df["high"]
        l = daily_df["low"]
        c = daily_df["close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr_val = round(float(tr.rolling(14).mean().iloc[-1]), 2)
        atr_pct = round(atr_val / pm_price * 100, 2) if pm_price else None

    # Volume ratio (premarket vs 15% of avg daily)
    avg_vol = float(daily_df["volume"].mean()) if not daily_df.empty else 0
    if avg_vol == 0:
        try:
            import yfinance as yf
            hist = yf.Ticker(t).history(period="30d", interval="1d")
            avg_vol = float(hist["Volume"].mean()) if not hist.empty else 0
        except Exception:
            avg_vol = 0
    vol_ratio = round(pm_volume / (avg_vol * 0.15), 2) if avg_vol > 0 else 0

    # ── Key levels ───────────────────────────────────────────
    key_levels = {}
    if not daily_df.empty:
        closes = daily_df["close"]
        highs = daily_df["high"]
        lows = daily_df["low"]

        # Prior day H/L
        key_levels["prior_high"] = round(float(highs.iloc[-1]), 2)
        key_levels["prior_low"] = round(float(lows.iloc[-1]), 2)

        # 50/200 SMA
        if len(closes) >= 50:
            key_levels["sma50"] = round(float(closes.tail(50).mean()), 2)
        if len(closes) >= 200:
            key_levels["sma200"] = round(float(closes.tail(200).mean()), 2)

        # 52-week high (approx 252 bars)
        lookback = min(252, len(highs))
        key_levels["52w_high"] = round(float(highs.tail(lookback).max()), 2)
        key_levels["52w_low"] = round(float(lows.tail(lookback).min()), 2)

        # Distance from 52w high
        if key_levels.get("52w_high"):
            key_levels["dist_52w_high_pct"] = round((pm_price - key_levels["52w_high"]) / key_levels["52w_high"] * 100, 2)

    # ── ORB candidate detection ───────────────────────────────
    # Tight premarket range relative to ATR = energy building for breakout
    orb_candidate = False
    orb_score = 0
    if atr_val and atr_val > 0 and pm_range > 0:
        pm_range_vs_atr = pm_range / atr_val
        orb_score = round(pm_range_vs_atr, 2)
        # Tight range = good ORB candidate
        orb_candidate = pm_range_vs_atr < 0.5 and vol_ratio >= 1.0

    # ── Setup classification ─────────────────────────────────
    abs_gap = abs(gap_pct)
    if abs_gap >= 3 and vol_ratio >= 1.5:
        setup = "gap-and-go"
        notes = f"Strong {gap_direction} gap with high RVOL — momentum continuation play"
    elif abs_gap >= 3 and vol_ratio < 0.8:
        setup = "gap-fade"
        notes = "Large gap on low volume — likely to fade back. Watch for reversal candle at open"
    elif abs_gap >= 1.5 and vol_ratio >= 1.2:
        setup = "gap-and-go"
        notes = f"Moderate {gap_direction} gap with confirming volume — follow the trend"
    elif abs_gap >= 1.5 and vol_ratio < 0.8:
        setup = "gap-fill"
        notes = "Gap on weak volume — likely fills back toward prior close"
    elif abs_gap < 0.5:
        setup = "no-trade"
        notes = "Flat open — wait for direction in first 5-minute candle"
    elif orb_candidate:
        setup = "orb-watch"
        notes = f"Tight PM range ({orb_score:.1f}x ATR) — watch for opening range breakout"
    else:
        setup = "watch"
        notes = "Moderate gap — wait for first 5-min candle to confirm direction"

    # ── Raschke 80/20 fade ───────────────────────────────────
    raschke = {"setup": "no-data"}
    if prior_close and not prior_regular.empty:
        prior_high = float(prior_regular["high"].max())
        prior_low = float(prior_regular["low"].min())
        prior_range = prior_high - prior_low
        if prior_range > 0:
            open_pos = (pm_price - prior_low) / prior_range
            if open_pos > 0.80:
                raschke = {
                    "setup": "fade-short", "open_position_pct": round(open_pos * 100, 1),
                    "target": round(prior_low + prior_range * 0.50, 2),
                    "stop": round(pm_high * 1.001, 2),
                    "notes": "Opened top 20% of prior range — fade short candidate",
                }
            elif open_pos < 0.20:
                raschke = {
                    "setup": "fade-long", "open_position_pct": round(open_pos * 100, 1),
                    "target": round(prior_high - prior_range * 0.50, 2),
                    "stop": round(pm_low * 0.999, 2),
                    "notes": "Opened bottom 20% of prior range — fade long candidate",
                }
            else:
                raschke = {"setup": "no-fade", "open_position_pct": round(open_pos * 100, 1)}

    # ── Trade idea ───────────────────────────────────────────
    trade_idea = None
    if setup == "gap-and-go" and atr_val:
        side = "LONG" if gap_pct > 0 else "SHORT"
        entry = pm_high if gap_pct > 0 else pm_low
        stop = entry - atr_val * 0.5 if side == "LONG" else entry + atr_val * 0.5
        target1 = entry + atr_val if side == "LONG" else entry - atr_val
        target2 = entry + atr_val * 2 if side == "LONG" else entry - atr_val * 2
        trade_idea = {
            "side": side, "entry": round(entry, 2),
            "stop": round(stop, 2), "target_1r": round(target1, 2), "target_2r": round(target2, 2),
            "risk_per_share": round(abs(entry - stop), 2),
        }
    elif raschke["setup"] in ("fade-long", "fade-short"):
        trade_idea = {
            "side": "LONG" if raschke["setup"] == "fade-long" else "SHORT",
            "entry": round(pm_price, 2),
            "stop": raschke.get("stop"), "target_1r": raschke.get("target"),
            "risk_per_share": round(abs(pm_price - (raschke.get("stop") or pm_price)), 2),
        }

    return {
        "ticker": t,
        "prior_close": round(prior_close, 2),
        "premarket_price": round(pm_price, 2),
        "gap_pct": gap_pct,
        "gap_direction": gap_direction,
        "pm_high": round(pm_high, 2),
        "pm_low": round(pm_low, 2),
        "pm_range": round(pm_range, 2),
        "pm_volume": int(pm_volume),
        "volume_ratio": vol_ratio,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "key_levels": key_levels,
        "orb_candidate": orb_candidate,
        "orb_score": orb_score,
        "setup": setup,
        "notes": notes,
        "trade_idea": trade_idea,
        "raschke_fade": raschke,
        "premarket_date": str(today),
        "is_live": str(today) == str(now_et.date()),
        "data_source": f"extended_hours={source}, daily={daily_src}",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python scripts/session/premarket.py TICKER")
        sys.exit(1)
    print(json.dumps(analyze(sys.argv[1]), indent=2, default=str))
