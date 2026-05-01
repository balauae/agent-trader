#!/usr/bin/env python3
"""
load_queue.py — Unified DuckDB Writer (Single Process, No Lock Contention)
===========================================================================
ONE process handles ALL DuckDB writes:
  1. Checks for pending full loads (data/pending_loads.json)
  2. Runs full loads for any pending tickers
  3. Runs delta refresh for all watchlist tickers
  4. Copies snapshot to market-read.duckdb

Usage:
  python scripts/data/load_queue.py                    # process queue + delta
  python scripts/data/load_queue.py --queue-only       # only pending loads, no delta
  python scripts/data/load_queue.py --delta-only       # only delta, skip queue

Queue a ticker for loading:
  echo '["IBM","SHOP"]' > data/pending_loads.json
  # Or via the API: POST /api/v1/workspaces/ticker/load/IBM
"""

import json
import sys
import os
import shutil
import time
import logging
import fcntl
from pathlib import Path
from datetime import datetime

# Setup
REPO_ROOT = Path(__file__).parent.parent.parent
PENDING_FILE = REPO_ROOT / "data" / "pending_loads.json"
LOCK_FILE = REPO_ROOT / "data" / ".loader.lock"
DB_SRC = REPO_ROOT / "data" / "market.duckdb"
DB_DST = REPO_ROOT / "data" / "market-read.duckdb"
LOG_DIR = Path.home() / ".kairobm" / "logs"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("loader")


def acquire_lock():
    """Ensure only one instance runs at a time using a file lock."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except BlockingIOError:
        # Another instance is running
        try:
            other_pid = open(LOCK_FILE).read().strip()
        except Exception:
            other_pid = "unknown"
        log.warning(f"Another loader is running (PID {other_pid}). Exiting.")
        return None


def release_lock(lock_fd):
    if lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass


def read_pending() -> list[str]:
    """Read and clear the pending loads queue."""
    if not PENDING_FILE.exists():
        return []
    try:
        tickers = json.loads(PENDING_FILE.read_text())
        if isinstance(tickers, list) and len(tickers) > 0:
            # Clear the file immediately (atomic: other processes see empty)
            PENDING_FILE.write_text("[]")
            return [t.upper() for t in tickers if isinstance(t, str)]
    except Exception as e:
        log.warning(f"Failed to read pending loads: {e}")
    return []


def add_to_pending(ticker: str):
    """Add a ticker to the pending queue (called by the API)."""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = []
    if PENDING_FILE.exists():
        try:
            current = json.loads(PENDING_FILE.read_text())
        except Exception:
            current = []
    t = ticker.upper()
    if t not in current:
        current.append(t)
    PENDING_FILE.write_text(json.dumps(current))
    return current


def copy_snapshot():
    """Copy main DB to read-only snapshot."""
    if DB_SRC.exists():
        shutil.copy2(str(DB_SRC), str(DB_DST))
        log.info("Snapshot updated")


def run_full_loads(tickers: list[str]):
    """Run full load for each pending ticker, sequentially."""
    if not tickers:
        return

    from data.load_history import get_tv_client, load_exchange_map, init_db, load_ticker, DB_PATH
    import duckdb

    log.info(f"Full loading {len(tickers)} tickers: {', '.join(tickers)}")
    con = duckdb.connect(str(DB_PATH))
    init_db(con)
    tv = get_tv_client()
    exch_map = load_exchange_map()

    for ticker in tickers:
        exchange = exch_map.get(ticker, "NASDAQ")
        try:
            count = load_ticker(tv, con, ticker, exchange, refresh=False)
            log.info(f"Loaded {ticker}: {count:,d} bars")
        except Exception as e:
            log.error(f"Failed to load {ticker}: {e}")
        # Copy snapshot after each ticker so UI sees progress
        con.close()
        copy_snapshot()
        con = duckdb.connect(str(DB_PATH))

    con.close()


def run_delta():
    """Run incremental delta refresh for all watchlist tickers."""
    from data.load_delta import main as delta_main
    log.info("Starting delta refresh...")
    # load_delta.main() handles everything internally
    delta_main()


def main():
    args = sys.argv[1:]
    queue_only = "--queue-only" in args
    delta_only = "--delta-only" in args

    # Acquire exclusive lock
    lock_fd = acquire_lock()
    if lock_fd is None:
        sys.exit(0)  # Another instance running, exit cleanly

    try:
        start = datetime.now()
        log.info(f"{'='*50}")
        log.info(f"Unified loader started at {start.isoformat()}")
        log.info(f"{'='*50}")

        if not delta_only:
            # 1. Process pending full loads
            pending = read_pending()
            if pending:
                log.info(f"Pending full loads: {pending}")
                run_full_loads(pending)
            else:
                log.info("No pending full loads")

        if not queue_only:
            # 2. Delta refresh
            try:
                run_delta()
            except Exception as e:
                log.error(f"Delta refresh failed: {e}")

        # 3. Final snapshot copy
        copy_snapshot()

        elapsed = (datetime.now() - start).total_seconds()
        log.info(f"Loader finished in {elapsed:.0f}s")

    finally:
        release_lock(lock_fd)


if __name__ == "__main__":
    main()
