"""
vcp_scanner.py — Volatility Contraction Pattern (Minervini SEPA)
Detects VCP setups: tightening price + drying volume before breakout.

Usage: python scripts/vcp_scanner.py TICKER [timeframe] [bars]
       python scripts/vcp_scanner.py NVDA 1D 200
"""
import sys, json, warnings
from pathlib import Path
from datetime import datetime, timezone
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from scripts.data_fetcher import get_ohlcv_smart


def check_sepa_template(df: pd.DataFrame) -> dict:
    """Check Minervini SEPA trend template — 5 criteria."""
    close = df["close"]
    price = float(close.iloc[-1])
    criteria = {}

    if len(close) >= 200:
        ma50  = float(close.rolling(50).mean().iloc[-1])
        ma150 = float(close.rolling(150).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1])
        criteria["above_150_200ma"]   = price > ma150 and price > ma200
        criteria["ma50_above_150_200"] = ma50 > ma150 and ma50 > ma200
        criteria["ma150"] = round(ma150, 2)
        criteria["ma200"] = round(ma200, 2)
        criteria["ma50"]  = round(ma50, 2)

    if len(close) >= 220:
        ma200_now  = float(close.rolling(200).mean().iloc[-1])
        ma200_prev = float(close.rolling(200).mean().iloc[-20])
        criteria["ma200_uptrend"] = ma200_now > ma200_prev

    low_52w  = float(df["low"].tail(252).min())
    high_52w = float(df["high"].tail(252).max())
    criteria["above_52w_low_30pct"]   = price >= low_52w * 1.30
    criteria["within_25pct_52w_high"] = price >= high_52w * 0.75
    criteria["low_52w"]  = round(low_52w, 2)
    criteria["high_52w"] = round(high_52w, 2)

    bools = {k: v for k, v in criteria.items() if isinstance(v, bool)}
    score = sum(bools.values())
    return {"score": f"{score}/{len(bools)}", "score_int": score, "total": len(bools), "criteria": criteria}


def detect_vcp(df: pd.DataFrame) -> dict:
    """Detect Volatility Contraction Pattern."""
    recent = df.tail(60).copy()
    price   = float(recent["close"].iloc[-1])
    avg_vol = float(recent["volume"].mean())
    window  = 5

    contractions = []
    for i in range(window, len(recent) - window):
        h = recent["high"].iloc[i]
        if h == recent["high"].iloc[i - window:i + window + 1].max():
            contractions.append({"bar": i, "high": float(h), "vol": float(recent["volume"].iloc[i])})

    vcp_detected = False
    pivot_level  = None
    contraction_count = 0
    vol_trend = "unknown"

    if len(contractions) >= 2:
        highs = [c["high"] for c in contractions[-4:]]
        vols  = [c["vol"]  for c in contractions[-4:]]
        declining_highs = all(highs[i] < highs[i-1] for i in range(1, len(highs)))
        declining_vols  = all(vols[i]  < vols[i-1]  for i in range(1, len(vols)))
        contraction_count = len(highs)
        vol_trend = "declining" if declining_vols else "mixed"
        if declining_highs and len(highs) >= 2:
            vcp_detected = True
            pivot_level  = round(highs[-1], 2)

    latest_vol = float(recent["volume"].iloc[-1])
    vol_ratio  = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 0
    last10     = recent.tail(10)
    tightness  = round((float(last10["high"].max()) - float(last10["low"].min())) / price * 100, 2)

    return {
        "vcp_detected":      vcp_detected,
        "contractions":      contraction_count,
        "pivot_level":       pivot_level,
        "volume_trend":      vol_trend,
        "latest_vol_ratio":  vol_ratio,
        "tightness_pct":     tightness,
        "setup": ("VCP — Breakout watch" if vcp_detected and tightness < 8
                  else "VCP — Forming"   if vcp_detected
                  else "No VCP"),
    }


def scan(ticker: str, timeframe: str = "1D", bars: int = 200) -> dict:
    df, source = get_ohlcv_smart(ticker, timeframe, bars)
    if df.empty or len(df) < 60:
        return {"ticker": ticker, "error": "Insufficient data"}

    price = float(df["close"].iloc[-1])
    sepa  = check_sepa_template(df)
    vcp   = detect_vcp(df)

    if sepa["score_int"] >= 4 and vcp["vcp_detected"]:
        action = "WATCH_BREAKOUT"
    elif sepa["score_int"] >= 4:
        action = "ON_RADAR"
    else:
        action = "NOT_READY"

    return {
        "ticker":       ticker.upper(),
        "price":        round(price, 2),
        "timeframe":    timeframe,
        "data_source":  source,
        "computed_at":  datetime.now(timezone.utc).isoformat(),
        "sepa":         sepa,
        "vcp":          vcp,
        "action":       action,
        "summary":      f"{ticker} SEPA {sepa['score']} | VCP: {'Yes' if vcp['vcp_detected'] else 'No'} | {action}",
    }


if __name__ == "__main__":
    ticker    = sys.argv[1].upper() if len(sys.argv) > 1 else "NVDA"
    timeframe = sys.argv[2]         if len(sys.argv) > 2 else "1D"
    bars      = int(sys.argv[3])    if len(sys.argv) > 3 else 200
    print(json.dumps(scan(ticker, timeframe, bars), indent=2))
