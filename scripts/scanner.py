"""
scanner.py — Fast parallel watchlist scanner for TradeDesk
===========================================================
Usage:
    python scripts/scanner.py                    # scan full watchlist
    python scripts/scanner.py NVDA TSLA AAPL     # scan specific tickers
    python scripts/scanner.py --mode vwap        # vwap only (fastest)
    python scripts/scanner.py --mode full        # all agents

Modes:
    vwap   — VWAP + Technical only (fastest, ~10s for 30 tickers)
    full   — VWAP + Technical + Fundamental + Earnings (~30s)
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.vwap_watcher import analyze as vwap_analyze
from scripts.technical_analyst import analyze as tech_analyze
from scripts.fundamental_analyst import analyze as fund_analyze
from scripts.earnings_expert import analyze as earn_analyze

logger = logging.getLogger(__name__)

# Default watchlist
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


def scan_ticker(ticker: str, mode: str = "vwap") -> dict:
    """Run all relevant agents on a single ticker with retry + timeout guard."""
    import time
    t = ticker.upper()
    result = {"ticker": t, "error": None}

    def safe_run(fn, *args, retries=2):
        last_err = None
        for attempt in range(retries):
            try:
                return fn(*args)
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(1.0 + attempt)
        raise last_err

    try:
        result["vwap"] = safe_run(vwap_analyze, t)
        result["technical"] = safe_run(tech_analyze, t, "1D")
        if mode == "full":
            result["fundamental"] = safe_run(fund_analyze, t)
            result["earnings"] = safe_run(earn_analyze, t)
    except Exception as e:
        result["error"] = str(e)

    return result


def format_row(r: dict) -> str:
    """Format a single ticker result as a clean one-liner."""
    if r.get("error"):
        return f"❌ {r['ticker']:<6} ERROR: {r['error'][:40]}"

    v = r.get("vwap", {})
    ta = r.get("technical", {})

    price = v.get("price", "—")
    bias = ta.get("bias", "—")
    rsi = ta.get("indicators", {}).get("rsi", 0)
    setup = v.get("setup", "—")
    rr = v.get("risk_reward", "—")

    icon = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "🟡"

    line = f"{icon} {r['ticker']:<6} ${price:>8.2f} | {bias:<8} | RSI {rsi:>4.0f} | {setup:<24} | R:R {rr}"

    if r.get("fundamental"):
        f = r["fundamental"]
        rating = f.get("analyst_rating", "—")
        target = f.get("analyst_target", "—")
        line += f" | {rating} → ${target}"

    if r.get("earnings"):
        e = r["earnings"]
        line += f" | Earn {e.get('next_earnings_date','—')} ({e.get('days_to_earnings','?')}d)"

    return line


def scan(tickers: list, mode: str = "vwap", max_workers: int = 5) -> list:
    """Sequential scan with progress — avoids yfinance rate limits."""
    import time
    results = []

    for i, t in enumerate(tickers):
        try:
            result = scan_ticker(t, mode)
            results.append(result)
            # Print progress live
            row = format_row(result)
            print(row, flush=True)
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})
        time.sleep(1.0)  # steady rate — avoid TV throttle

    # Sort: BULLISH above VWAP first, then by setup quality
    def sort_key(r):
        v = r.get("vwap", {})
        ta = r.get("technical", {})
        bias = ta.get("bias", "NEUTRAL")
        rr = v.get("risk_reward") or 0
        has_setup = 0 if v.get("setup") == "No Setup" else 1
        bias_score = 2 if bias == "BULLISH" else 1 if bias == "NEUTRAL" else 0
        return (-bias_score, -has_setup, -rr)

    results.sort(key=sort_key)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", help="Tickers to scan (default: full watchlist)")
    parser.add_argument("--mode", choices=["vwap", "full"], default="vwap")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else DEFAULT_WATCHLIST

    print(f"\n🔍 Scanning {len(tickers)} tickers (mode={args.mode})...\n")

    results = scan(tickers, mode=args.mode)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        # Summary
        bullish = sum(1 for r in results if r.get("technical", {}).get("bias") == "BULLISH")
        bearish = sum(1 for r in results if r.get("technical", {}).get("bias") == "BEARISH")
        with_setup = sum(1 for r in results if r.get("vwap", {}).get("setup") != "No Setup" and not r.get("error"))
        print(f"\n📊 {len(tickers)} tickers | 🟢 {bullish} bullish | 🔴 {bearish} bearish | {with_setup} with active setup")
