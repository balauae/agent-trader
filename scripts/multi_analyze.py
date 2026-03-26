"""
multi_analyze.py — Run orchestrator on multiple tickers in parallel
====================================================================
Usage:
    python scripts/multi_analyze.py NVDA AAPL INTC PLTR
    python scripts/multi_analyze.py NVDA AAPL --mode full
"""

import sys
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.vwap_watcher import analyze as vwap_analyze
from scripts.technical_analyst import analyze as tech_analyze
from scripts.fundamental_analyst import analyze as fund_analyze
from scripts.earnings_expert import analyze as earn_analyze
from scripts.overnight_expert import analyze as overnight_analyze
from scripts.timeframe_analyzer import analyze as tf_analyze


def analyze_ticker(ticker: str, mode: str = "quick") -> dict:
    t = ticker.upper()
    out = {"ticker": t}
    try:
        v = vwap_analyze(t)
        ta = tech_analyze(t, timeframe="1D")
        out["price"] = v.get("price")
        out["bias"] = ta.get("bias")
        out["rsi"] = round(ta.get("indicators", {}).get("rsi", 0), 1)
        out["setup"] = v.get("setup")
        out["rr"] = v.get("risk_reward")
        out["entry"] = v.get("entry")
        out["stop"] = v.get("stop")
        out["target"] = v.get("target")
        out["signals"] = ta.get("signals", [])[:3]

        if mode == "full":
            f = fund_analyze(t)
            e = earn_analyze(t)
            o = overnight_analyze(t)
            tf = tf_analyze(t)
            out["tf_confluence"] = tf.get("confluence")
            out["tf_score"] = tf.get("confluence_score")
            out["tf_recommendation"] = tf.get("recommendation")
            out["pe"] = f.get("pe_ratio")
            out["analyst_rating"] = f.get("analyst_rating")
            out["analyst_target"] = f.get("analyst_target")
            out["earnings_date"] = e.get("next_earnings_date")
            out["days_to_earnings"] = e.get("days_to_earnings")
            out["expected_move"] = e.get("expected_move_pct")
            out["ah_price"] = o.get("ah_price")
            out["ah_change"] = o.get("ah_change_pct")
            out["overnight_risk"] = o.get("risk_level")
    except Exception as ex:
        out["error"] = str(ex)
    return out


def format_result(r: dict, mode: str = "quick") -> str:
    if r.get("error"):
        return f"❌ {r['ticker']}: {r['error'][:50]}"

    bias = r.get("bias", "NEUTRAL")
    icon = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "🟡"
    setup = r.get("setup", "No Setup")
    has_setup = setup != "No Setup"

    lines = []
    lines.append(f"{icon} {r['ticker']} ${r.get('price', '—')} | {bias} | RSI {r.get('rsi', '—')}")

    if has_setup:
        lines.append(f"   📐 {setup} | Entry ${r.get('entry')} | Stop ${r.get('stop')} | Target ${r.get('target')} | R:R {r.get('rr')}")
    else:
        lines.append(f"   📐 No active setup — watch for VWAP approach")

    for sig in r.get("signals", []):
        lines.append(f"   • {sig}")

    if mode == "full":
        if r.get("tf_confluence"):
            lines.append(f"   ⏱️  TF Confluence: {r.get('tf_confluence')} ({r.get('tf_score')}) — {r.get('tf_recommendation')}")
        lines.append(f"   📊 PE {r.get('pe')} | {r.get('analyst_rating')} → ${r.get('analyst_target')}")
        lines.append(f"   📅 Earnings {r.get('earnings_date')} ({r.get('days_to_earnings')}d) | Exp ±{r.get('expected_move')}%")
        lines.append(f"   🌙 AH ${r.get('ah_price')} ({r.get('ah_change'):+.2f}%) | Risk: {r.get('overnight_risk')}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    print(f"\n⚡ Analyzing {len(tickers)} tickers in parallel...\n")

    with ThreadPoolExecutor(max_workers=len(tickers)) as ex:
        futures = {ex.submit(analyze_ticker, t, args.mode): t for t in tickers}
        results = []
        for future in as_completed(futures):
            results.append(future.result())

    # Sort: bullish first
    results.sort(key=lambda x: (
        0 if x.get("bias") == "BULLISH" else 1 if x.get("bias") == "NEUTRAL" else 2
    ))

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        for r in results:
            print(format_result(r, args.mode))
            print()
