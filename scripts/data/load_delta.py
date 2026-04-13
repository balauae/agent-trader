#!/usr/bin/env python3
"""
Incremental delta loader — fetches only new bars since last stored timestamp.

Delta detection:
  For each (ticker, timeframe) in the DB:
    1. Query MAX(ts) — the last bar we have
    2. Calculate gap: now - max_ts
    3. Fetch only enough bars to cover the gap
    4. Upsert — primary key (ticker, timeframe, ts) prevents duplicates

Usage:
  python scripts/data/load_delta.py                # all tickers in DB
  python scripts/data/load_delta.py PLTR AAPL      # specific tickers
"""
import sys
import time
import logging
from datetime import datetime, timezone

import duckdb
import pandas as pd
from tvDatafeed import Interval

from data.load_history import (
    get_tv_client, load_exchange_map, init_db, get_last_ts,
    upsert_bars, DB_PATH, TIMEFRAMES, API_DELAY,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("load_delta")

# Approximate bar durations in seconds for gap calculation
BAR_DURATIONS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400,
    "1d": 86400, "1w": 604800, "1M": 2592000,
}


def estimate_bars_needed(last_ts, tf_label: str) -> int:
    """Estimate how many bars we need to fetch to cover the gap."""
    if last_ts is None:
        return 10000  # no data — fetch everything
    now = datetime.now(timezone.utc)
    ts = pd.Timestamp(last_ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize('UTC')
    gap_seconds = (now - ts).total_seconds()
    bar_seconds = BAR_DURATIONS.get(tf_label, 86400)
    bars_needed = int(gap_seconds / bar_seconds) + 10  # +10 buffer
    return max(bars_needed, 20)  # minimum 20 bars


def load_delta_ticker(tv, con, ticker: str, exchange: str):
    """Load only new bars for a ticker across all timeframes."""
    total_new = 0

    for tf_label, tf_interval, max_bars in TIMEFRAMES:
        try:
            last = get_last_ts(con, ticker, tf_label)
            if last is None:
                log.info(f"  {ticker} {tf_label:>4s}: no existing data — skipping (use load_full.py)")
                continue

            bars_needed = estimate_bars_needed(last, tf_label)
            bars_to_fetch = min(bars_needed, max_bars)

            if bars_needed <= 1:
                log.info(f"  {ticker} {tf_label:>4s}: up to date (last: {last})")
                continue

            df = tv.get_hist(
                symbol=ticker,
                exchange=exchange,
                interval=tf_interval,
                n_bars=bars_to_fetch,
            )

            if df is None or df.empty:
                log.warning(f"  {ticker} {tf_label:>4s}: no data returned")
                time.sleep(API_DELAY)
                continue

            # Filter to only bars newer than what we have
            df = df[df.index > pd.Timestamp(last)]
            if df.empty:
                log.info(f"  {ticker} {tf_label:>4s}: already current")
                time.sleep(API_DELAY)
                continue

            count = upsert_bars(con, ticker, tf_label, df)
            total_new += count
            log.info(f"  {ticker} {tf_label:>4s}: +{count} new bars ({df.index.min()} → {df.index.max()})")

        except Exception as e:
            log.error(f"  {ticker} {tf_label:>4s}: ERROR — {e}")

        time.sleep(API_DELAY)

    return total_new


def main():
    args = [a.upper() for a in sys.argv[1:] if not a.startswith("--")]

    con = duckdb.connect(str(DB_PATH))
    init_db(con)

    # Get tickers: from args, or all tickers in DB
    if args:
        tickers = args
    else:
        rows = con.execute("SELECT DISTINCT ticker FROM bars ORDER BY ticker").fetchall()
        tickers = [r[0] for r in rows]

    if not tickers:
        log.warning("No tickers to update. Run load_full.py first.")
        con.close()
        return

    exch_map = load_exchange_map()
    tv = get_tv_client()

    log.info(f"Delta update: {', '.join(tickers)}")
    total = 0
    for ticker in tickers:
        exchange = exch_map.get(ticker, "NASDAQ")
        try:
            total += load_delta_ticker(tv, con, ticker, exchange)
        except Exception as e:
            log.error(f"Failed {ticker}: {e}")

    log.info(f"Delta complete: +{total:,d} new bars")
    con.close()


if __name__ == "__main__":
    main()
