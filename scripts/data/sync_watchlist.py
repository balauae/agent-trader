#!/usr/bin/env python3
"""
Watchlist sync — checks all tickers for data freshness and fills gaps.

For each ticker in positions + watchlist:
  - If not in DB → full load (all timeframes)
  - If in DB → delta load (only new bars)
  - Reports a health table showing staleness per ticker/timeframe

Usage:
  python scripts/data/sync_watchlist.py              # sync all
  python scripts/data/sync_watchlist.py --report      # report only, no fetch
"""
import sys
import time
import logging
from datetime import datetime, timezone

import duckdb
import pandas as pd

from data.load_history import (
    get_tv_client, load_exchange_map, init_db, load_ticker,
    get_last_ts, get_tickers, DB_PATH, TIMEFRAMES, API_DELAY,
)
from data.load_delta import load_delta_ticker

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("sync")

# Staleness thresholds (seconds) — when to flag as stale
STALE_THRESHOLDS = {
    "1m": 3 * 3600,       # 3 hours
    "3m": 6 * 3600,       # 6 hours
    "5m": 12 * 3600,      # 12 hours
    "15m": 2 * 86400,     # 2 days
    "30m": 2 * 86400,     # 2 days
    "1h": 3 * 86400,      # 3 days
    "2h": 5 * 86400,      # 5 days
    "4h": 7 * 86400,      # 1 week
    "1d": 3 * 86400,      # 3 days
    "1w": 10 * 86400,     # 10 days
    "1M": 35 * 86400,     # 35 days
}


def generate_report(con, tickers: list[str]) -> list[dict]:
    """Generate health report for all tickers."""
    report = []
    now = datetime.now(timezone.utc)

    for ticker in tickers:
        for tf_label, _, _ in TIMEFRAMES:
            last = get_last_ts(con, ticker, tf_label)
            if last is None:
                report.append({
                    "ticker": ticker, "tf": tf_label,
                    "last_bar": None, "behind": None,
                    "status": "MISSING",
                })
                continue

            ts = pd.Timestamp(last)
            if ts.tzinfo is None:
                ts = ts.tz_localize('UTC')
            gap = (now - ts).total_seconds()
            threshold = STALE_THRESHOLDS.get(tf_label, 86400)

            behind_str = format_duration(gap)
            if gap > threshold:
                status = "STALE"
            else:
                status = "OK"

            report.append({
                "ticker": ticker, "tf": tf_label,
                "last_bar": str(last)[:19], "behind": behind_str,
                "status": status,
            })

    return report


def format_duration(seconds: float) -> str:
    if seconds < 3600:
        return f"{seconds/60:.0f}m"
    if seconds < 86400:
        return f"{seconds/3600:.1f}h"
    return f"{seconds/86400:.1f}d"


def print_report(report: list[dict]):
    print(f"\n{'Ticker':<8} {'TF':>4}  {'Last Bar':<20} {'Behind':>8}  {'Status'}")
    print("-" * 65)
    for r in report:
        last = r["last_bar"] or "—"
        behind = r["behind"] or "—"
        status = r["status"]
        status_mark = {"OK": "  ", "STALE": "!!", "MISSING": "**"}
        print(f"{r['ticker']:<8} {r['tf']:>4}  {last:<20} {behind:>8}  {status_mark.get(status, '  ')} {status}")
    print()

    # Summary
    total = len(report)
    ok = sum(1 for r in report if r["status"] == "OK")
    stale = sum(1 for r in report if r["status"] == "STALE")
    missing = sum(1 for r in report if r["status"] == "MISSING")
    print(f"Summary: {ok}/{total} OK, {stale} stale, {missing} missing")


def main():
    report_only = "--report" in sys.argv

    con = duckdb.connect(str(DB_PATH))
    init_db(con)

    tickers = get_tickers([])
    exch_map = load_exchange_map()

    log.info(f"Watchlist: {', '.join(tickers)}")

    # Check which tickers exist in DB
    existing = set()
    rows = con.execute("SELECT DISTINCT ticker FROM bars").fetchall()
    existing = {r[0] for r in rows}

    # Generate report first
    report = generate_report(con, tickers)
    print_report(report)

    if report_only:
        con.close()
        return

    # Sync
    tv = get_tv_client()
    new_tickers = [t for t in tickers if t not in existing]
    delta_tickers = [t for t in tickers if t in existing]

    total = 0

    # Full load for new tickers
    if new_tickers:
        log.info(f"New tickers (full load): {', '.join(new_tickers)}")
        for ticker in new_tickers:
            exchange = exch_map.get(ticker, "NASDAQ")
            try:
                total += load_ticker(tv, con, ticker, exchange, refresh=False)
            except Exception as e:
                log.error(f"Failed full load {ticker}: {e}")

    # Delta load for existing tickers
    if delta_tickers:
        log.info(f"Existing tickers (delta): {', '.join(delta_tickers)}")
        for ticker in delta_tickers:
            exchange = exch_map.get(ticker, "NASDAQ")
            try:
                total += load_delta_ticker(tv, con, ticker, exchange)
            except Exception as e:
                log.error(f"Failed delta {ticker}: {e}")

    # Final report
    report = generate_report(con, tickers)
    print_report(report)
    log.info(f"Sync complete: +{total:,d} bars")
    con.close()


if __name__ == "__main__":
    main()
