#!/usr/bin/env python3
"""
Historical Data Bulk Loader
============================
Fetches all available historical bars from TradingView across all timeframes
and stores them in DuckDB for instant analysis and backtesting.

Usage:
  python scripts/data/load_history.py                    # load all positions + watchlist
  python scripts/data/load_history.py PLTR NVDA TSLA     # specific tickers
  python scripts/data/load_history.py --refresh           # update existing data with latest bars
"""

import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd
from tvDatafeed import TvDatafeed, Interval

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("loader")

# --- Paths ---
REPO_ROOT  = Path(__file__).parent.parent.parent
SECRETS    = REPO_ROOT / ".secrets" / "tradingview.json"
DB_PATH    = REPO_ROOT / "data" / "market.duckdb"
POS_FILE   = REPO_ROOT / "data" / "positions.json"
TICK_FILE  = REPO_ROOT / "data" / "tickers.json"

# --- Watchlist (full 50-ticker universe) ---
WATCHLIST = [
    # Momentum / Day trade
    "TSLA", "NVDA", "AMD", "MRVL", "PLTR", "COIN", "APP", "HIMS", "CRWV", "ARM",
    "RKLB", "HOOD", "SOFI", "SOUN", "RGTI", "SMCI",
    # Growth / Swing
    "AAPL", "MSFT", "META", "AMZN", "GOOGL", "AVGO", "MU", "CRWD", "PANW", "NFLX",
    "ORCL", "TSM", "NU", "AFRM", "SNOW", "TEAM", "DOCU", "WDAY", "DOCN", "UNH",
    "OKTA", "PYPL", "NVO",
    # Macro / Crypto proxies
    "GLD", "SLV", "IBIT", "BABA",
    # Speculative
    "QBTS", "APLD", "IREN", "SMR", "ALAB", "MDB",
    # Swing
    "AXON", "TTD", "ZS", "ADBE",
    # Index ETFs
    "SPY", "QQQ",
]

# --- Timeframe config ---
# (label, Interval enum, n_bars to request)
# Pro Premium: up to 20K bars, custom timeframes available
TIMEFRAMES = [
    ("1m",  Interval.in_1_minute,  20000),
    ("3m",  Interval.in_3_minute,  20000),
    ("5m",  Interval.in_5_minute,  20000),
    ("15m", Interval.in_15_minute, 20000),
    ("30m", Interval.in_30_minute, 20000),
    ("1h",  Interval.in_1_hour,    20000),
    ("2h",  Interval.in_2_hour,    10000),
    ("4h",  Interval.in_4_hour,    10000),
    ("1d",  Interval.in_daily,     20000),
    ("1w",  Interval.in_weekly,    10000),
    ("1M",  Interval.in_monthly,   5000),
]

# --- Exchange map (from tickers.json or defaults) ---
DEFAULT_EXCHANGE = {
    # ETFs (AMEX)
    "SPY": "AMEX", "QQQ": "NASDAQ", "GLD": "AMEX", "SLV": "AMEX",
    "IWM": "AMEX", "DIA": "AMEX", "IBIT": "NASDAQ",
    "ARKK": "AMEX", "XLF": "AMEX", "XLE": "AMEX",
    # NYSE
    "TSM": "NYSE", "NVO": "NYSE", "BABA": "NYSE", "UNH": "NYSE",
    "ORCL": "NYSE", "AXON": "NYSE", "JNJ": "NYSE", "JPM": "NYSE",
    "BAC": "NYSE", "WMT": "NYSE", "V": "NYSE", "MA": "NYSE",
    "PG": "NYSE", "KO": "NYSE", "DIS": "NYSE", "CVX": "NYSE",
    "XOM": "NYSE", "PFE": "NYSE", "ABBV": "NYSE", "MRK": "NYSE",
    "LLY": "NYSE", "ABT": "NYSE", "DHR": "NYSE", "BMY": "NYSE",
    "CRM": "NYSE", "IBM": "NYSE", "CAT": "NYSE", "GS": "NYSE",
    "HD": "NYSE", "LOW": "NYSE", "TGT": "NYSE", "NKE": "NYSE",
}

API_DELAY = 0.3  # seconds between TV API calls (0.2s tested OK, 0.3s for safety)


def load_exchange_map() -> dict:
    """Build ticker->exchange map from tickers.json + positions.json + defaults."""
    exch = dict(DEFAULT_EXCHANGE)

    # From positions.json
    if POS_FILE.exists():
        for p in json.loads(POS_FILE.read_text()):
            exch[p["ticker"]] = p.get("exchange", "NASDAQ")

    # From tickers.json (exchange_map field if present)
    if TICK_FILE.exists():
        data = json.loads(TICK_FILE.read_text())
        if "exchange_map" in data:
            exch.update(data["exchange_map"])

    return exch


def get_tv_client() -> TvDatafeed:
    """Create TvDatafeed client with token injection."""
    token = None
    if SECRETS.exists():
        creds = json.loads(SECRETS.read_text())
        token = creds.get("auth_token")
        expires = creds.get("token_expires")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires)
                remaining = (exp_dt - datetime.now(exp_dt.tzinfo)).total_seconds()
                if remaining < 0:
                    log.warning("TV token has EXPIRED — data may be limited")
                elif remaining < 1800:
                    log.warning(f"TV token expires in {remaining/60:.0f} min")
            except Exception:
                pass

    tv = TvDatafeed()
    if token:
        tv.token = token
        log.info(f"TV token loaded ({len(token)} chars)")
    else:
        log.warning("No TV token — using anonymous (limited data)")
    return tv


def init_db(con: duckdb.DuckDBPyConnection):
    """Create the bars table if it doesn't exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS bars (
            ticker  VARCHAR NOT NULL,
            timeframe VARCHAR NOT NULL,
            ts      TIMESTAMP NOT NULL,
            open    DOUBLE,
            high    DOUBLE,
            low     DOUBLE,
            close   DOUBLE,
            volume  DOUBLE,
            PRIMARY KEY (ticker, timeframe, ts)
        );
    """)


def get_last_ts(con: duckdb.DuckDBPyConnection, ticker: str, tf: str):
    """Get the latest timestamp stored for a ticker+timeframe."""
    row = con.execute(
        "SELECT MAX(ts) FROM bars WHERE ticker=? AND timeframe=?",
        [ticker, tf]
    ).fetchone()
    return row[0] if row and row[0] else None


def upsert_bars(con: duckdb.DuckDBPyConnection, ticker: str, tf: str, df: pd.DataFrame) -> int:
    """Insert bars into DuckDB with upsert semantics. Returns rows inserted."""
    if df is None or df.empty:
        return 0

    # Prepare DataFrame
    rows = df[["open", "high", "low", "close", "volume"]].copy()
    rows["ticker"] = ticker
    rows["timeframe"] = tf
    rows["ts"] = pd.to_datetime(rows.index)
    rows = rows[["ticker", "timeframe", "ts", "open", "high", "low", "close", "volume"]]

    # Use INSERT OR REPLACE
    con.execute("DELETE FROM bars WHERE ticker=? AND timeframe=? AND ts IN (SELECT ts FROM rows)", [ticker, tf])
    con.execute("INSERT INTO bars SELECT * FROM rows")
    return len(rows)


def load_ticker(tv: TvDatafeed, con: duckdb.DuckDBPyConnection,
                ticker: str, exchange: str, refresh: bool = False):
    """Load all timeframes for a single ticker."""
    log.info(f"{'='*60}")
    log.info(f"  {ticker} ({exchange})")
    log.info(f"{'='*60}")

    total = 0
    for tf_label, tf_interval, n_bars in TIMEFRAMES:
        try:
            if refresh:
                last = get_last_ts(con, ticker, tf_label)
                if last:
                    log.info(f"  {tf_label:>4s}: refreshing since {last}")

            df = tv.get_hist(
                symbol=ticker,
                exchange=exchange,
                interval=tf_interval,
                n_bars=n_bars,
            )

            # Auto-retry with alternate exchanges if primary fails
            if (df is None or df.empty) and exchange == 'NASDAQ':
                for alt in ['NYSE', 'AMEX']:
                    df = tv.get_hist(symbol=ticker, exchange=alt, interval=tf_interval, n_bars=n_bars)
                    if df is not None and not df.empty:
                        log.info(f"  {tf_label:>4s}: found on {alt} (not {exchange})")
                        break
                    time.sleep(API_DELAY)

            if df is None or df.empty:
                log.warning(f"  {tf_label:>4s}: no data returned")
                time.sleep(API_DELAY)
                continue

            # Filter to only new bars if refreshing
            if refresh:
                last = get_last_ts(con, ticker, tf_label)
                if last:
                    df = df[df.index > pd.Timestamp(last)]
                    if df.empty:
                        log.info(f"  {tf_label:>4s}: already up to date")
                        time.sleep(API_DELAY)
                        continue

            count = upsert_bars(con, ticker, tf_label, df)
            total += count

            ts_min = df.index.min()
            ts_max = df.index.max()
            log.info(f"  {tf_label:>4s}: {count:>6,d} bars  |  {ts_min} -> {ts_max}")

        except Exception as e:
            log.error(f"  {tf_label:>4s}: ERROR — {e}")

        time.sleep(API_DELAY)

    log.info(f"  TOTAL: {total:,d} bars loaded for {ticker}")
    return total


def get_tickers(args: list[str]) -> list[str]:
    """Determine which tickers to load."""
    if args:
        return [t.upper() for t in args if not t.startswith("--")]

    tickers = set()

    # From positions
    if POS_FILE.exists():
        for p in json.loads(POS_FILE.read_text()):
            tickers.add(p["ticker"])

    # Add watchlist
    tickers.update(WATCHLIST)

    return sorted(tickers)


def print_stats(con: duckdb.DuckDBPyConnection):
    """Print DB summary stats."""
    result = con.execute("""
        SELECT ticker, timeframe,
               COUNT(*) as bars,
               MIN(ts) as first_bar,
               MAX(ts) as last_bar
        FROM bars
        GROUP BY ticker, timeframe
        ORDER BY ticker, timeframe
    """).fetchall()

    total = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    tickers = con.execute("SELECT COUNT(DISTINCT ticker) FROM bars").fetchone()[0]

    print(f"\n{'='*70}")
    print(f"  DuckDB Stats: {total:,d} total bars across {tickers} tickers")
    print(f"{'='*70}")
    print(f"  {'Ticker':<8} {'TF':>4}  {'Bars':>7}  {'From':<20} {'To':<20}")
    print(f"  {'-'*65}")
    for ticker, tf, bars, first, last in result:
        print(f"  {ticker:<8} {tf:>4}  {bars:>7,d}  {str(first):<20} {str(last):<20}")
    print()


def main():
    args = sys.argv[1:]
    refresh = "--refresh" in args
    if refresh:
        args.remove("--refresh")

    tickers = get_tickers(args)
    exch_map = load_exchange_map()

    log.info(f"Tickers to load: {', '.join(tickers)}")
    log.info(f"Mode: {'refresh (incremental)' if refresh else 'full load'}")
    log.info(f"Database: {DB_PATH}")

    # Ensure data dir exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connect to DuckDB
    con = duckdb.connect(str(DB_PATH))
    init_db(con)

    # Get TV client
    tv = get_tv_client()

    grand_total = 0
    failed = []

    for ticker in tickers:
        exchange = exch_map.get(ticker, "NASDAQ")
        try:
            count = load_ticker(tv, con, ticker, exchange, refresh=refresh)
            grand_total += count
        except Exception as e:
            log.error(f"Failed to load {ticker}: {e}")
            failed.append(ticker)

    print_stats(con)

    log.info(f"Grand total: {grand_total:,d} bars loaded")
    if failed:
        log.warning(f"Failed tickers: {', '.join(failed)}")

    con.close()


if __name__ == "__main__":
    main()
