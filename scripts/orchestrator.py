"""
orchestrator.py — TradeDesk Orchestrator
=========================================
Routes user queries to specialist agents, runs them in parallel,
and synthesizes results into a single JSON response.

Usage:
    python scripts/orchestrator.py "analyze NVDA"
    python scripts/orchestrator.py "news on TSLA"
    python scripts/orchestrator.py "market summary"
"""

import sys
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.technical_analyst import analyze as technical_analyze
from scripts.vwap_watcher import analyze as vwap_analyze
from scripts.news_fetcher import fetch_all_news
from scripts.economic_calendar import build_calendar

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
AGENT_TIMEOUT = 15

# Common tickers to detect in queries
TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")
NOISE_WORDS = {
    "I", "A", "AN", "THE", "ON", "IN", "AT", "TO", "FOR", "OF", "IS", "IT",
    "MY", "ME", "DO", "UP", "IF", "OR", "SO", "AM", "PM", "ET", "US", "BY",
    "ANY", "ALL", "HAS", "HAD", "ARE", "WAS", "AND", "BUT", "NOT", "CAN",
    "HOW", "WHY", "SET", "GET", "PUT", "RUN", "OUT", "OFF", "BIG", "NEW",
    "OLD", "TOP", "LOW", "HIGH", "GOOD", "BAD", "LONG", "SHORT",
    "WHAT", "WHEN", "THIS", "THAT", "WITH", "FROM", "JUST",
    "NEXT", "LAST", "WEEK", "TODAY", "SHOW", "GIVE", "TELL", "LOOK",
    "ABOUT", "CHECK", "SETUP", "ENTRY", "CHART", "BROAD",
    "MACRO", "NEWS", "MARKET", "STOCK", "TRADE",
    "ANALYZE", "SUMMARY", "OVERVIEW", "SECTOR",
    "EARNINGS", "CALENDAR", "EVENTS", "TECHNICAL", "INDICATORS",
    "LEVELS", "HAPPENED", "CATALYST",
    "FOMC", "OPEX", "FED", "VWAP",
}

# Intent keywords
INTENT_MAP = {
    "news": ["news", "headlines", "what happened", "catalyst", "why is", "why did"],
    "chart": ["chart", "setup", "technical", "indicators", "levels", "entry", "exit"],
    "calendar": ["calendar", "events", "fomc", "fed", "opex", "macro", "economic"],
    "earnings": ["earnings", "iv crush", "expected move", "earnings play", "options"],
    "fundamental": ["fundamentals", "valuation", "pe ratio", "revenue", "analyst target", "balance sheet"],
    "premarket": ["pre-market", "premarket", "gap", "before open", "overnight gap"],
    "open": ["opening range", "orb", "first candle", "market open", "9:30"],
    "postmarket": ["how did", "eod", "end of day", "recap", "after close", "today's performance"],
    "overnight": ["overnight", "after hours", "ah price", "hold overnight", "tomorrow setup"],
    "timeframe": ["timeframe", "multi timeframe", "mtf", "all timeframes", "1m 5m 15m", "confluence"],
    "pattern": ["pattern", "chart pattern", "flag", "wedge", "double top", "double bottom", "head and shoulders", "triangle"],
    "scan": ["scan", "find setups", "best setups", "watchlist", "what's moving", "scan all"],
    "market": ["market summary", "market overview", "broad market", "sector", "overview"],
}

# Agents per intent
INTENT_AGENTS = {
    "analyze": ["technical_analyst", "vwap_watcher", "news_fetcher", "economic_calendar", "timeframe_analyzer", "pattern_finder"],
    "news": ["news_fetcher"],
    "chart": ["technical_analyst", "vwap_watcher"],
    "calendar": ["economic_calendar"],
    "earnings": ["earnings_expert", "economic_calendar"],
    "fundamental": ["fundamental_analyst", "earnings_expert"],
    "premarket": ["premarket_specialist", "vwap_watcher"],
    "open": ["market_open_scalper", "vwap_watcher"],
    "postmarket": ["postmarket_summarizer", "technical_analyst"],
    "overnight": ["overnight_expert", "fundamental_analyst"],
    "timeframe": ["timeframe_analyzer"],
    "pattern": ["pattern_finder"],
    "scan": ["technical_analyst", "vwap_watcher"],
    "market": ["technical_analyst", "news_fetcher", "economic_calendar"],
}


def get_session() -> str:
    """Detect current market session from ET time."""
    now = datetime.now(ET)
    hour, minute = now.hour, now.minute
    t = hour * 60 + minute

    if t < 240:        # 00:00 - 03:59
        return "Overnight"
    if t < 570:        # 04:00 - 09:29
        return "Pre-Market"
    if t < 600:        # 09:30 - 09:59
        return "Open"
    if t < 930:        # 10:00 - 15:29
        return "Regular"
    if t < 960:        # 15:30 - 15:59
        return "Close"
    if t < 1200:       # 16:00 - 19:59
        return "Post-Market"
    return "Overnight"  # 20:00 - 23:59


def _load_ticker_db() -> dict:
    """Load ticker database from data/tickers.json."""
    try:
        db_path = Path(__file__).parent.parent / "data" / "tickers.json"
        return json.loads(db_path.read_text())
    except Exception:
        return {"ticker_to_name": {}, "name_to_ticker": {}}

_TICKER_DB = _load_ticker_db()
_KNOWN_TICKERS = set(_TICKER_DB.get("ticker_to_name", {}).keys())
_NAME_TO_TICKER = _TICKER_DB.get("name_to_ticker", {})

def parse_ticker(query: str) -> str | None:
    """
    Smart ticker extraction:
    1. Check query words against known ticker list (exact match)
    2. Check query words against company name map (e.g. 'apple' → AAPL)
    3. Fallback: regex for 2-5 uppercase letters not in noise words
    """
    q_lower = query.lower()
    words_upper = query.upper().split()
    words_lower = query.lower().split()

    # 1. Exact ticker match against known list
    for word in words_upper:
        cleaned = re.sub(r"[^A-Z]", "", word)
        if cleaned in _KNOWN_TICKERS:
            return cleaned

    # 2. Company name match (e.g. "apple", "nvidia", "tesla")
    for word in words_lower:
        cleaned = re.sub(r"[^a-z]", "", word)
        if cleaned in _NAME_TO_TICKER:
            return _NAME_TO_TICKER[cleaned]

    # 3. Fallback: regex (2-5 uppercase letters, not noise)
    for word in words_upper:
        cleaned = re.sub(r"[^A-Z]", "", word)
        if cleaned and 2 <= len(cleaned) <= 5 and cleaned not in NOISE_WORDS:
            return cleaned

    return None


def parse_intent(query: str) -> str:
    """Determine user intent from query text."""
    q = query.lower()

    # Check market intent first (it's a phrase match)
    for keyword in INTENT_MAP["market"]:
        if keyword in q:
            return "market"

    for intent, keywords in INTENT_MAP.items():
        if intent == "market":
            continue
        for keyword in keywords:
            if keyword in q:
                return intent

    return "analyze"


def run_agent(name: str, ticker: str | None) -> dict:
    """Run a single agent and return its result."""
    if name == "technical_analyst":
        return technical_analyze(ticker or "SPY")
    elif name == "vwap_watcher":
        return vwap_analyze(ticker or "SPY")
    elif name == "news_fetcher":
        t = ticker or "SPY"
        items = fetch_all_news(t, limit=10)
        return {"ticker": t, "count": len(items), "items": items}
    elif name == "economic_calendar":
        return build_calendar(ticker=ticker, days=7)
    elif name == "fundamental_analyst":
        from scripts.fundamental_analyst import analyze as fund_analyze
        return fund_analyze(ticker or "SPY")
    elif name == "earnings_expert":
        from scripts.earnings_expert import analyze as earn_analyze
        return earn_analyze(ticker or "SPY")
    elif name == "premarket_specialist":
        from scripts.premarket_specialist import analyze as pm_analyze
        return pm_analyze(ticker or "SPY")
    elif name == "market_open_scalper":
        from scripts.market_open_scalper import analyze as open_analyze
        return open_analyze(ticker or "SPY")
    elif name == "postmarket_summarizer":
        from scripts.postmarket_summarizer import summarize as post_analyze
        return post_analyze(ticker or "SPY")
    elif name == "overnight_expert":
        from scripts.overnight_expert import analyze as overnight_analyze
        return overnight_analyze(ticker or "SPY")
    elif name == "timeframe_analyzer":
        from scripts.timeframe_analyzer import analyze as tf_analyze
        return tf_analyze(ticker or "SPY")
    elif name == "pattern_finder":
        from scripts.pattern_finder import analyze as pattern_analyze
        return pattern_analyze(ticker or "SPY")
    else:
        return {"error": f"Unknown agent: {name}"}


def build_summary(intent: str, ticker: str | None, results: dict, errors: dict) -> str:
    """Build a plain-text summary from agent results."""
    parts = []
    t = ticker or "SPY"

    # Technical bias
    ta = results.get("technical_analyst", {})
    if ta and not ta.get("error"):
        bias = ta.get("bias", "UNKNOWN")
        confluence = ta.get("confluence_score", "?/?")
        price = ta.get("price", "?")
        parts.append(f"{t} is showing a {bias} bias with {confluence} confluence at ${price}.")

    # VWAP setup
    vw = results.get("vwap_watcher", {})
    if vw and not vw.get("error"):
        setup = vw.get("setup", "No Setup")
        vwap_bias = vw.get("bias", "NEUTRAL")
        if setup != "No Setup":
            rr = vw.get("risk_reward", "N/A")
            parts.append(f"VWAP setup: {setup} ({vwap_bias}), R:R {rr}.")
        else:
            parts.append(f"No active VWAP setup. Price {vw.get('price_vs_vwap', '?')} VWAP.")

    # News
    nf = results.get("news_fetcher", {})
    if nf and not nf.get("error"):
        count = nf.get("count", 0)
        items = nf.get("items", [])
        high_impact = [i for i in items if i.get("impact") == "High"]
        if high_impact:
            parts.append(
                f"{len(high_impact)} high-impact headline(s): "
                f"\"{high_impact[0]['title']}\""
            )
        elif count > 0:
            parts.append(f"{count} news items, none high-impact.")
        else:
            parts.append("No recent news found.")

    # Calendar warnings
    ec = results.get("economic_calendar", {})
    if ec and not ec.get("error"):
        warnings = ec.get("warnings", [])
        if warnings:
            parts.append(f"Calendar alert: {warnings[0]}")
        else:
            parts.append("No high-impact events in the next 7 days.")

    # Fundamental
    fa = results.get("fundamental_analyst", {})
    if fa and not fa.get("error"):
        pe = fa.get("pe_ratio", "N/A")
        rating = fa.get("analyst_rating", "N/A")
        target = fa.get("analyst_target", "N/A")
        growth = fa.get("growth_grade", "N/A")
        parts.append(f"Fundamentals: PE {pe}, {growth}, analyst {rating} → ${target}.")

    # Earnings
    ee = results.get("earnings_expert", {})
    if ee and not ee.get("error"):
        days = ee.get("days_to_earnings", 999)
        date = ee.get("next_earnings_date", "N/A")
        exp = ee.get("expected_move_pct", "N/A")
        iv_risk = ee.get("iv_crush_risk", "N/A")
        parts.append(f"Earnings {date} ({days}d away), expected move ±{exp}%, IV risk {iv_risk}.")

    # Timeframe confluence
    tf = results.get("timeframe_analyzer", {})
    if tf and not tf.get("error"):
        confluence = tf.get("confluence", "N/A")
        score = tf.get("confluence_score", "N/A")
        rec = tf.get("recommendation", "")
        parts.append(f"Timeframe confluence: {confluence} ({score}). {rec}")

    # Pattern finder
    pt = results.get("pattern_finder", {})
    if pt and not pt.get("error"):
        best = pt.get("best_pattern")
        if best:
            parts.append(f"Pattern: {best['pattern']} ({best['confidence']}% confidence). {best['description']}")
        else:
            parts.append("No chart patterns detected.")

    # Overnight / AH
    ov = results.get("overnight_expert", {})
    if ov and not ov.get("error"):
        ah = ov.get("ah_change_pct", 0)
        risk = ov.get("risk_level", "N/A")
        ah_price = ov.get("ah_price", "N/A")
        parts.append(f"After hours: ${ah_price} ({ah:+.2f}%), overnight risk {risk}.")

    # Premarket
    pm = results.get("premarket_specialist", {})
    if pm and not pm.get("error"):
        gap = pm.get("gap_pct", 0)
        direction = pm.get("gap_direction", "")
        setup = pm.get("setup", "")
        parts.append(f"Pre-market gap: {gap:+.2f}% {direction} — {setup}.")

    # Errors
    for agent, err in errors.items():
        parts.append(f"{agent} unavailable: {err}")

    return " ".join(parts) if parts else "No data available."


def orchestrate(query: str) -> dict:
    """Main orchestration: parse, route, run agents, synthesize."""
    ticker = parse_ticker(query)
    intent = parse_intent(query)
    session = get_session()
    now = datetime.now(ET)

    agent_names = INTENT_AGENTS.get(intent, INTENT_AGENTS["analyze"])

    # For market intent without ticker, use SPY
    effective_ticker = ticker if ticker else ("SPY" if intent == "market" else ticker)

    results = {}
    errors = {}

    def _run(name):
        return name, run_agent(name, effective_ticker)

    with ThreadPoolExecutor(max_workers=len(agent_names)) as executor:
        futures = {executor.submit(_run, name): name for name in agent_names}
        for future in futures:
            name = futures[future]
            try:
                _, result = future.result(timeout=AGENT_TIMEOUT)
                results[name] = result
            except TimeoutError:
                errors[name] = "Timed out (15s limit)"
            except Exception as e:
                errors[name] = str(e)

    summary = build_summary(intent, effective_ticker, results, errors)

    return {
        "query": query,
        "ticker": effective_ticker,
        "intent": intent,
        "session": session,
        "timestamp": now.isoformat(),
        "agents_used": list(results.keys()),
        "results": results,
        "errors": errors,
        "summary": summary,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    if len(sys.argv) < 2:
        print("Usage: python scripts/orchestrator.py \"analyze NVDA\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    output = orchestrate(query)
    print(json.dumps(output, indent=2, default=str))
