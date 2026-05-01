#!/usr/bin/env python3
"""
load_fast.py — Fast Bulk Loader for New Tickers
=================================================
Loads ONLY the essential timeframes first (1d, 1h, 5m, 15m) with reduced
API delay. This gets ~80% of the value in ~30% of the time.

After the fast pass, queue a full pass (all 11 timeframes) for background.

Speed tricks:
  - 4 timeframes instead of 11 (3x fewer API calls)
  - 0.5s API delay instead of 1.5s (3x faster between calls)
  - Snapshot copy after every 5 tickers (not every ticker)
  - Skip tickers that already have data

Usage:
  python scripts/data/load_fast.py                     # load all missing
  python scripts/data/load_fast.py NVDA TSLA           # specific tickers
  python scripts/data/load_fast.py --full-after         # queue full load after fast pass
"""

import sys
import json
import time
import logging
import shutil
import os
import fcntl
from pathlib import Path
from datetime import datetime

import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from data.load_history import (
    get_tv_client, load_exchange_map, init_db,
    upsert_bars, DB_PATH, API_DELAY,
)
from tvDatafeed import Interval

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fast_loader")

REPO_ROOT = Path(__file__).parent.parent.parent
LOCK_FILE = REPO_ROOT / "data" / ".loader.lock"
DB_DST = REPO_ROOT / "data" / "market-read.duckdb"

# Essential timeframes only (4 instead of 11)
FAST_TIMEFRAMES = [
    ("1d",  Interval.in_daily,     20000),
    ("1h",  Interval.in_1_hour,    5000),
    ("5m",  Interval.in_5_minute,  5000),
    ("15m", Interval.in_15_minute, 5000),
]

FAST_DELAY = 0.2  # seconds between API calls (vs 1.5s normal)


def get_missing_tickers(con, tickers: list[str]) -> list[str]:
    """Return tickers that have zero bars in DuckDB."""
    if not tickers:
        return []
    in_clause = ",".join(f"'{t}'" for t in tickers)
    loaded = set(
        r[0] for r in con.execute(
            f"SELECT DISTINCT ticker FROM bars WHERE ticker IN ({in_clause})"
        ).fetchall()
    )
    return [t for t in tickers if t not in loaded]


def get_all_universe() -> list[str]:
    """Get all tickers from themes + watchlist."""
    tickers = set()
    themes_file = REPO_ROOT / "data" / "themes.json"
    if themes_file.exists():
        data = json.loads(themes_file.read_text())
        for theme in data.get("themes", []):
            for sub in theme.get("sub_themes", []):
                tickers.update(sub.get("tickers", []))
    wl_file = REPO_ROOT / "data" / "tickers.json"
    if wl_file.exists():
        data = json.loads(wl_file.read_text())
        tickers.update(data.get("watchlist", []))
    return sorted(tickers)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full_after = "--full-after" in sys.argv

    # Acquire lock
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
    except BlockingIOError:
        log.warning("Another loader is running. Waiting for lock...")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)  # Blocking wait
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()

    try:
        con = duckdb.connect(str(DB_PATH))
        init_db(con)

        # Determine tickers to load
        if args:
            tickers = [t.upper() for t in args]
        else:
            all_tickers = get_all_universe()
            tickers = get_missing_tickers(con, all_tickers)

        if not tickers:
            log.info("All tickers already loaded!")
            con.close()
            return

        log.info(f"Fast loading {len(tickers)} tickers (4 essential timeframes)")
        log.info(f"Tickers: {', '.join(tickers)}")

        tv = get_tv_client()
        exch_map = load_exchange_map()

        total_bars = 0
        loaded_count = 0
        start = time.time()

        for i, ticker in enumerate(tickers):
            exchange = exch_map.get(ticker, "NASDAQ")
            ticker_bars = 0

            log.info(f"[{i+1}/{len(tickers)}] {ticker} ({exchange})")

            for tf_label, tf_interval, n_bars in FAST_TIMEFRAMES:
                try:
                    df = tv.get_hist(
                        symbol=ticker, exchange=exchange,
                        interval=tf_interval, n_bars=n_bars,
                    )
                    # Auto-retry with alternate exchanges
                    if (df is None or df.empty) and exchange == "NASDAQ":
                        for alt in ["NYSE", "AMEX"]:
                            df = tv.get_hist(symbol=ticker, exchange=alt, interval=tf_interval, n_bars=n_bars)
                            if df is not None and not df.empty:
                                log.info(f"  {tf_label}: found on {alt}")
                                break
                            time.sleep(FAST_DELAY)

                    if df is None or df.empty:
                        log.warning(f"  {tf_label}: no data")
                        time.sleep(FAST_DELAY)
                        continue

                    count = upsert_bars(con, ticker, tf_label, df)
                    ticker_bars += count
                    log.info(f"  {tf_label}: {count:,d} bars")

                except Exception as e:
                    log.error(f"  {tf_label}: ERROR — {e}")

                time.sleep(FAST_DELAY)

            total_bars += ticker_bars
            loaded_count += 1

            # Snapshot every 5 tickers
            if loaded_count % 5 == 0:
                con.close()
                if DB_PATH.exists():
                    shutil.copy2(str(DB_PATH), str(DB_DST))
                    log.info(f"  Snapshot updated ({loaded_count}/{len(tickers)} done)")
                con = duckdb.connect(str(DB_PATH))

        con.close()

        # Final snapshot
        if DB_PATH.exists():
            shutil.copy2(str(DB_PATH), str(DB_DST))

        elapsed = time.time() - start
        log.info(f"{'='*50}")
        log.info(f"Fast load complete: {loaded_count} tickers, {total_bars:,d} bars in {elapsed:.0f}s")
        log.info(f"Speed: {elapsed/max(loaded_count,1):.1f}s per ticker")
        log.info(f"{'='*50}")

        # Queue full load for remaining timeframes
        if full_after and loaded_count > 0:
            pending_file = REPO_ROOT / "data" / "pending_loads.json"
            pending = list(tickers)
            pending_file.write_text(json.dumps(pending))
            log.info(f"Queued {len(pending)} tickers for full 11-timeframe load")

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
