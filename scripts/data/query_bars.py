#!/usr/bin/env python3
"""
Query historical bars from DuckDB.

Usage:
  python scripts/data/query_bars.py PLTR 1d             # show last 20 daily bars
  python scripts/data/query_bars.py PLTR 1h --count 50  # last 50 hourly bars
  python scripts/data/query_bars.py --stats              # show DB stats (rows per ticker/tf)
"""

import sys
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent.parent / "data" / "market.duckdb"


def show_stats(con):
    """Show row counts per ticker and timeframe."""
    result = con.execute("""
        SELECT ticker, timeframe,
               COUNT(*) as bars,
               MIN(ts)::VARCHAR as first_bar,
               MAX(ts)::VARCHAR as last_bar
        FROM bars
        GROUP BY ticker, timeframe
        ORDER BY ticker, timeframe
    """).fetchall()

    total = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    tickers = con.execute("SELECT COUNT(DISTINCT ticker) FROM bars").fetchone()[0]

    print(f"\nDuckDB: {DB_PATH}")
    print(f"Total: {total:,d} bars across {tickers} tickers\n")
    print(f"{'Ticker':<8} {'TF':>4}  {'Bars':>7}  {'From':<20} {'To':<20}")
    print(f"{'-'*65}")

    cur_ticker = None
    for ticker, tf, bars, first, last in result:
        if ticker != cur_ticker:
            if cur_ticker is not None:
                print()
            cur_ticker = ticker
        print(f"{ticker:<8} {tf:>4}  {bars:>7,d}  {first:<20} {last:<20}")
    print()


def show_bars(con, ticker: str, tf: str, count: int):
    """Show the last N bars for a ticker+timeframe."""
    rows = con.execute("""
        SELECT ts::VARCHAR, open, high, low, close, volume
        FROM bars
        WHERE ticker=? AND timeframe=?
        ORDER BY ts DESC
        LIMIT ?
    """, [ticker.upper(), tf, count]).fetchall()

    if not rows:
        print(f"No data for {ticker.upper()} {tf}")
        return

    total = con.execute(
        "SELECT COUNT(*) FROM bars WHERE ticker=? AND timeframe=?",
        [ticker.upper(), tf]
    ).fetchone()[0]

    print(f"\n{ticker.upper()} {tf} — last {len(rows)} of {total:,d} bars\n")
    print(f"{'Timestamp':<20} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print(f"{'-'*78}")

    for ts, o, h, l, c, v in reversed(rows):
        vol_str = f"{v:>12,.0f}" if v else f"{'N/A':>12}"
        print(f"{ts:<20} {o:>10.2f} {h:>10.2f} {l:>10.2f} {c:>10.2f} {vol_str}")
    print()


def main():
    args = sys.argv[1:]

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Run load_history.py first to populate it.")
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    if "--stats" in args:
        show_stats(con)
        con.close()
        return

    if len(args) < 2:
        print(__doc__)
        con.close()
        sys.exit(1)

    ticker = args[0]
    tf = args[1]
    count = 20

    if "--count" in args:
        idx = args.index("--count")
        if idx + 1 < len(args):
            count = int(args[idx + 1])

    show_bars(con, ticker, tf, count)
    con.close()


if __name__ == "__main__":
    main()
