"""
scanner.py — Two-stage watchlist scanner for TradeDesk
=======================================================
Stage 1: yfinance bulk download — screen all 50 tickers instantly
Stage 2: TradingView deep dive — VWAP + technical on top 15 candidates

Usage:
    python scripts/scanner.py                    # full scan (default watchlist)
    python scripts/scanner.py NVDA TSLA AAPL     # specific tickers
    python scripts/scanner.py --top 10           # show top N after TV dive
    python scripts/scanner.py --stage1           # stage 1 only (no TV)
"""

import sys
import json
import logging
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# DEFAULT WATCHLIST
# ─────────────────────────────────────────────
DEFAULT_WATCHLIST = [
    # Momentum / Day trade
    "TSLA", "NVDA", "AMD", "MRVL", "PLTR", "COIN", "APP", "HIMS", "CRWV", "ARM",
    "RKLB", "HOOD", "SOFI", "SOUN", "RGTI", "SMCI",
    # Growth / Swing
    "AAPL", "MSFT", "META", "AMZN", "GOOGL", "AVGO", "MU", "CRWD", "PANW", "NFLX",
    "ORCL", "TSM", "NU", "AFRM", "SNOW", "TEAM", "DOCU", "WDAY", "DOCN", "UNH",
    "OKTA", "PYPL", "NVO",
    # Macro / Crypto proxies
    "GLD", "SLV", "IBIT", "BABA",
    # Speculative
    "QBTS", "APLD", "IREN", "SMR", "ALAB", "MDB",
    # Swing
    "AXON", "TTD", "ZS", "ADBE",
]


# ─────────────────────────────────────────────
# STAGE 1 — yfinance bulk screen
# ─────────────────────────────────────────────

def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def stage1_screen(tickers: list) -> list:
    """
    Bulk yfinance download — compute RSI, bias, momentum score.
    Returns list of dicts sorted by score (best first).
    """
    print(f"\n📊 Stage 1: Screening {len(tickers)} tickers via yfinance...", flush=True)

    try:
        raw = yf.download(
            tickers,
            period="60d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"❌ yfinance bulk download failed: {e}")
        return []

    results = []

    for t in tickers:
        try:
            # Handle single vs multi ticker column structure
            if len(tickers) == 1:
                close = raw["Close"]
                volume = raw["Volume"]
            else:
                close = raw["Close"][t].dropna()
                volume = raw["Volume"][t].dropna()

            if len(close) < 20:
                continue

            price = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])
            change_pct = (price - prev_close) / prev_close * 100

            # RSI
            rsi = _calc_rsi(close)

            # EMAs
            ema9  = float(close.ewm(span=9,  adjust=False).mean().iloc[-1])
            ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1])

            # Bias
            bull_signals = sum([
                price > ema9,
                ema9 > ema21,
                price > sma50,
                rsi > 50,
                change_pct > 0,
            ])
            if bull_signals >= 4:
                bias = "BULLISH"
            elif bull_signals <= 1:
                bias = "BEARISH"
            else:
                bias = "NEUTRAL"

            # Momentum score (higher = better candidate for TV dive)
            # Prioritize: bullish bias + RSI not overbought + above EMAs
            score = bull_signals * 10
            if 40 <= rsi <= 70:
                score += 10  # sweet spot RSI
            if bias == "BULLISH":
                score += 15
            elif bias == "BEARISH":
                score -= 10

            results.append({
                "ticker": t,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "rsi": round(rsi, 1),
                "bias": bias,
                "ema9_vs_ema21": "above" if ema9 > ema21 else "below",
                "price_vs_sma50": "above" if price > sma50 else "below",
                "bull_signals": bull_signals,
                "score": score,
            })

        except Exception as e:
            logger.debug(f"Stage1 skip {t}: {e}")
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ─────────────────────────────────────────────
# STAGE 2 — TradingView deep dive
# ─────────────────────────────────────────────

def stage2_tv_dive(ticker: str) -> dict:
    """Run VWAP + technical analyst on a single ticker via TV."""
    from scripts.vwap_watcher import analyze as vwap_analyze
    from scripts.technical_analyst import analyze as tech_analyze

    result = {"ticker": ticker}
    try:
        result["vwap"] = vwap_analyze(ticker)
    except Exception as e:
        result["vwap"] = {"error": str(e)}
    try:
        result["technical"] = tech_analyze(ticker, timeframe="1D")
    except Exception as e:
        result["technical"] = {"error": str(e)}
    return result


def stage2_batch(candidates: list, top_n: int = 15) -> list:
    """
    Run TV deep dive on top N candidates sequentially.
    Sequential to avoid WebSocket throttle.
    """
    from scripts.data_fetcher import reset_tv_client

    top = candidates[:top_n]
    print(f"\n🔬 Stage 2: TV deep dive on top {len(top)} candidates...\n", flush=True)

    results = []
    for i, c in enumerate(top):
        t = c["ticker"]
        if i > 0 and i % 5 == 0:
            # Reset TV client every 5 tickers
            reset_tv_client()
            time.sleep(3)

        r = stage2_tv_dive(t)
        r["stage1"] = c  # carry stage1 data

        # Format and print live
        print(format_row(r), flush=True)
        results.append(r)
        time.sleep(1.5)

    return results


# ─────────────────────────────────────────────
# FORMATTING
# ─────────────────────────────────────────────

def format_row(r: dict) -> str:
    t = r["ticker"]
    s1 = r.get("stage1", {})
    vw = r.get("vwap", {})
    ta = r.get("technical", {})

    # Price — prefer TV technical, fallback to yfinance stage1
    price = ta.get("price") or s1.get("price", "—")
    bias  = ta.get("bias") or s1.get("bias", "—")
    rsi   = ta.get("indicators", {}).get("rsi") or s1.get("rsi", 0)
    setup = vw.get("setup", "—") if not vw.get("error") else "TV error"
    rr    = vw.get("risk_reward", "—")
    chg   = s1.get("change_pct", 0)

    icon = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "🟡"
    chg_str = f"{chg:+.1f}%" if chg else ""

    return f"{icon} {t:<6} ${price:>8.2f} {chg_str:>6} | {bias:<8} | RSI {rsi:>4.0f} | {setup:<24} | R:R {rr}"


def format_stage1_row(c: dict) -> str:
    icon = "🟢" if c["bias"] == "BULLISH" else "🔴" if c["bias"] == "BEARISH" else "🟡"
    return (f"{icon} {c['ticker']:<6} ${c['price']:>8.2f} {c['change_pct']:>+6.1f}% "
            f"| {c['bias']:<8} | RSI {c['rsi']:>4.0f} | signals {c['bull_signals']}/5")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", help="Tickers to scan")
    parser.add_argument("--top", type=int, default=15, help="Top N for TV deep dive")
    parser.add_argument("--stage1", action="store_true", help="Stage 1 only (no TV)")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else DEFAULT_WATCHLIST

    # ── Stage 1 ──
    stage1 = stage1_screen(tickers)

    if not stage1:
        print("❌ No data from Stage 1")
        sys.exit(1)

    if args.stage1:
        print(f"\n{'─'*70}")
        print(f"{'📊 STAGE 1 RESULTS — ALL TICKERS':^70}")
        print(f"{'─'*70}\n")
        for c in stage1:
            print(format_stage1_row(c))
        bullish = sum(1 for c in stage1 if c["bias"] == "BULLISH")
        bearish = sum(1 for c in stage1 if c["bias"] == "BEARISH")
        print(f"\n📊 {len(stage1)} tickers | 🟢 {bullish} bullish | 🔴 {bearish} bearish")
        sys.exit(0)

    # ── Stage 2 ──
    stage2 = stage2_batch(stage1, top_n=args.top)

    # ── Final summary ──
    print(f"\n{'─'*70}")
    print(f"{'📈 FINAL — TOP SETUPS':^70}")
    print(f"{'─'*70}\n")

    # Sort final by TV bias + R:R
    def sort_key(r):
        bias = r.get("technical", {}).get("bias", r.get("stage1", {}).get("bias", "NEUTRAL"))
        rr = r.get("vwap", {}).get("risk_reward") or 0
        has_setup = 0 if r.get("vwap", {}).get("setup") in ("No Setup", None) else 1
        bias_score = 2 if bias == "BULLISH" else 1 if bias == "NEUTRAL" else 0
        return (-bias_score, -has_setup, -rr)

    stage2.sort(key=sort_key)
    for r in stage2:
        print(format_row(r))

    bullish = sum(1 for r in stage2 if (r.get("technical", {}).get("bias") or r.get("stage1", {}).get("bias")) == "BULLISH")
    bearish = sum(1 for r in stage2 if (r.get("technical", {}).get("bias") or r.get("stage1", {}).get("bias")) == "BEARISH")
    with_setup = sum(1 for r in stage2 if r.get("vwap", {}).get("setup") not in ("No Setup", None, "") and not r.get("vwap", {}).get("error"))

    print(f"\n📊 Screened {len(stage1)} | TV deep dive {len(stage2)} | 🟢 {bullish} bullish | 🔴 {bearish} bearish | {with_setup} with setup")

    # Also print full stage1 at bottom
    print(f"\n{'─'*70}")
    print(f"{'📋 FULL WATCHLIST SCREEN (Stage 1)':^70}")
    print(f"{'─'*70}\n")
    for c in stage1:
        print(format_stage1_row(c))
