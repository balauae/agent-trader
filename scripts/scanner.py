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
    "NVDA", "AMD", "ARM", "AVGO", "MU", "AAPL", "MSFT", "META", "AMZN", "GOOGL",
    "TSLA", "PLTR", "APP", "CRWV", "COIN", "HOOD", "SOFI", "AFRM", "NU",
    "RKLB", "SMR", "IREN", "HIMS", "SOUN", "RGTI", "QBTS", "LAC",
    "NFLX", "ADBE", "CRWD", "PANW", "ZS", "SNOW", "TEAM", "ORCL"
]


def scan_ticker(ticker: str, mode: str = "vwap") -> dict:
    """Run all relevant agents on a single ticker."""
    t = ticker.upper()
    result = {"ticker": t, "error": None}

    try:
        # Always run VWAP + Technical (retry once on failure)
        try:
            result["vwap"] = vwap_analyze(t)
        except Exception as e1:
            result["vwap"] = vwap_analyze(t)  # retry once
        try:
            result["technical"] = tech_analyze(t, timeframe="1D")
        except Exception as e2:
            result["technical"] = tech_analyze(t, timeframe="1D")

        if mode == "full":
            result["fundamental"] = fund_analyze(t)
            result["earnings"] = earn_analyze(t)

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


def scan(tickers: list, mode: str = "vwap", max_workers: int = 8) -> list:
    """Parallel scan of all tickers."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(scan_ticker, t, mode): t for t in tickers}
        for future in as_completed(futures):
            results.append(future.result())

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
        for r in results:
            print(format_row(r))

        # Summary
        bullish = sum(1 for r in results if r.get("technical", {}).get("bias") == "BULLISH")
        bearish = sum(1 for r in results if r.get("technical", {}).get("bias") == "BEARISH")
        with_setup = sum(1 for r in results if r.get("vwap", {}).get("setup") != "No Setup" and not r.get("error"))
        print(f"\n📊 {len(tickers)} tickers | 🟢 {bullish} bullish | 🔴 {bearish} bearish | {with_setup} with active setup")
