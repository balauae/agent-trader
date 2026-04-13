#!/usr/bin/env python3
"""
Full historical data loader for new tickers.
Fetches ALL available bars across ALL 7 timeframes from TradingView.

Usage:
  python scripts/data/load_full.py NVDA TSLA AMD     # specific tickers
  python scripts/data/load_full.py --all              # reload ALL tickers (positions + watchlist)
"""
import sys
from data.load_history import get_tv_client, load_exchange_map, init_db, load_ticker, print_stats, get_tickers, DB_PATH
import duckdb
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("load_full")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    load_all = "--all" in sys.argv

    if not args and not load_all:
        print("Usage: python scripts/data/load_full.py TICKER1 TICKER2 ...")
        print("       python scripts/data/load_full.py --all")
        sys.exit(1)

    tickers = get_tickers([]) if load_all else [t.upper() for t in args]
    exch_map = load_exchange_map()

    log.info(f"Full load: {', '.join(tickers)}")
    con = duckdb.connect(str(DB_PATH))
    init_db(con)
    tv = get_tv_client()

    total = 0
    for ticker in tickers:
        exchange = exch_map.get(ticker, "NASDAQ")
        try:
            total += load_ticker(tv, con, ticker, exchange, refresh=False)
        except Exception as e:
            log.error(f"Failed {ticker}: {e}")

    print_stats(con)
    log.info(f"Total: {total:,d} bars loaded")
    con.close()

if __name__ == "__main__":
    main()
