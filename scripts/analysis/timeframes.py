"""
timeframe_analyzer.py — Multi-timeframe confluence analysis for TradeDesk
=========================================================================
Usage:
    python scripts/timeframe_analyzer.py TICKER
    python scripts/timeframe_analyzer.py NVDA
    python scripts/timeframe_analyzer.py AAPL

Analyzes a ticker across 1m, 5m, 15m, and 1D timeframes.
Scores confluence (how many timeframes agree on direction) and
outputs a single JSON with overall bias, entry/stop/target, and recommendation.
"""

import sys
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.analysis.technical import analyze as tech_analyze
from scripts.feeds.vwap import analyze as vwap_analyze

logger = logging.getLogger(__name__)

TIMEFRAMES = ["1m", "5m", "15m", "1D"]


# ─────────────────────────────────────────────
# TIMEFRAME BIAS EXTRACTION
# ─────────────────────────────────────────────

def extract_bias(result: dict) -> str:
    """Normalize bias from tech_analyze result to BULLISH / BEARISH / NEUTRAL."""
    bias = result.get("bias", "NEUTRAL").upper()
    if bias in ("BULLISH", "BEARISH", "NEUTRAL"):
        return bias
    return "NEUTRAL"


def build_tf_summary(tech: dict, vwap: dict | None = None) -> dict:
    """Build a compact summary dict for one timeframe."""
    indicators = tech.get("indicators", {})
    summary = {
        "bias": extract_bias(tech),
        "rsi": indicators.get("rsi"),
        "macd": indicators.get("macd_line"),
    }

    if vwap and not vwap.get("error"):
        summary["setup"] = vwap.get("setup")
        summary["rr"] = vwap.get("risk_reward")

    return summary


# ─────────────────────────────────────────────
# CONFLUENCE SCORING
# ─────────────────────────────────────────────

def score_confluence(tf_summaries: dict) -> tuple[str, str, str]:
    """
    Count how many timeframes agree on BULLISH vs BEARISH.
    Returns (overall_bias, confluence_label, confluence_score).
    """
    bullish = sum(1 for s in tf_summaries.values() if s["bias"] == "BULLISH")
    bearish = sum(1 for s in tf_summaries.values() if s["bias"] == "BEARISH")
    total = len(tf_summaries)

    if bullish >= bearish:
        agreeing = bullish
        direction = "BULLISH"
    else:
        agreeing = bearish
        direction = "BEARISH"

    if agreeing >= 3:
        label = "HIGH"
    elif agreeing == 2:
        label = "MEDIUM"
    else:
        label = "LOW"

    # Overall bias
    if agreeing >= 3:
        overall = direction
    elif agreeing == 2 and bullish != bearish:
        overall = direction
    else:
        overall = "MIXED"

    score = f"{agreeing}/{total}"
    return overall, label, score


# ─────────────────────────────────────────────
# RECOMMENDATION
# ─────────────────────────────────────────────

def build_recommendation(overall_bias: str, confluence_label: str,
                         confluence_score: str, tf_summaries: dict) -> str:
    """Generate a human-readable recommendation string."""
    agreeing = int(confluence_score.split("/")[0])
    total = int(confluence_score.split("/")[1])

    if agreeing == total:
        direction = "LONG" if overall_bias == "BULLISH" else "SHORT"
        return f"Perfect alignment — high conviction {direction}"

    if agreeing == 3:
        direction = "LONG" if overall_bias == "BULLISH" else "SHORT"
        # Find the dissenting timeframe
        dissenting = [tf for tf, s in tf_summaries.items() if s["bias"] != overall_bias]
        suffix = f". Wait for {dissenting[0]} to confirm." if dissenting else ""
        return f"Strong {direction.lower()} — {agreeing}/{total} TFs aligned{suffix}"

    if agreeing == 2:
        return "Mixed signals — wait for clarity"

    return "No trade — conflicting signals across all timeframes"


# ─────────────────────────────────────────────
# ENTRY / STOP / TARGET
# ─────────────────────────────────────────────

def pick_levels(tech_results: dict, vwap_result: dict | None) -> dict:
    """
    Pick entry/stop/target from the best available source.
    Prefer 5m tech levels, then 1m VWAP setup levels, then 1m tech levels.
    """
    # Try 5m tech levels first
    tech_5m = tech_results.get("5m")
    if tech_5m and not tech_5m.get("error"):
        price = tech_5m.get("price")
        stop = tech_5m.get("stop_loss")
        target = tech_5m.get("take_profit")
        if price and stop and target:
            return {
                "best_entry": f"${price}",
                "stop": f"${stop}",
                "target": f"${target}",
            }

    # Try 1m VWAP setup levels
    if vwap_result and not vwap_result.get("error"):
        entry = vwap_result.get("entry")
        stop = vwap_result.get("stop")
        target = vwap_result.get("target")
        if entry and stop and target:
            return {
                "best_entry": f"${entry}",
                "stop": f"${stop}",
                "target": f"${target}",
            }

    # Fallback to 1m tech levels
    tech_1m = tech_results.get("1m")
    if tech_1m and not tech_1m.get("error"):
        price = tech_1m.get("price")
        stop = tech_1m.get("stop_loss")
        target = tech_1m.get("take_profit")
        if price and stop and target:
            return {
                "best_entry": f"${price}",
                "stop": f"${stop}",
                "target": f"${target}",
            }

    return {"best_entry": None, "stop": None, "target": None}


# ─────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────

def analyze(ticker: str) -> dict:
    """Run multi-timeframe confluence analysis on a ticker."""
    tech_results = {}
    vwap_result = None

    # Fetch all timeframes + VWAP in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for tf in TIMEFRAMES:
            futures[executor.submit(tech_analyze, ticker, tf)] = ("tech", tf)
        futures[executor.submit(vwap_analyze, ticker)] = ("vwap", "1m")

        for future in as_completed(futures):
            kind, tf = futures[future]
            try:
                result = future.result()
                if kind == "tech":
                    tech_results[tf] = result
                else:
                    vwap_result = result
            except Exception as e:
                logger.warning("Failed to fetch %s/%s: %s", kind, tf, e)
                if kind == "tech":
                    tech_results[tf] = {"error": str(e)}

    # Build per-timeframe summaries
    tf_summaries = {}
    for tf in TIMEFRAMES:
        tech = tech_results.get(tf, {})
        vwap = vwap_result if tf == "1m" else None
        if tech.get("error"):
            tf_summaries[tf] = {"bias": "NEUTRAL", "rsi": None, "macd": None, "error": tech["error"]}
        else:
            tf_summaries[tf] = build_tf_summary(tech, vwap)

    # Confluence
    overall_bias, confluence_label, confluence_score = score_confluence(tf_summaries)

    # Recommendation
    recommendation = build_recommendation(overall_bias, confluence_label,
                                          confluence_score, tf_summaries)

    # Entry / stop / target
    levels = pick_levels(tech_results, vwap_result)

    return {
        "ticker": ticker.upper(),
        "overall_bias": overall_bias,
        "confluence": confluence_label,
        "confluence_score": confluence_score,
        "timeframes": tf_summaries,
        "recommendation": recommendation,
        **levels,
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    if len(sys.argv) < 2:
        print("Usage: python scripts/timeframe_analyzer.py TICKER")
        print("  Example: python scripts/timeframe_analyzer.py NVDA")
        sys.exit(1)

    ticker = sys.argv[1]
    result = analyze(ticker)
    print(json.dumps(result, indent=2, default=str))
