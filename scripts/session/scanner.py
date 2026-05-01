"""
scanner.py — Daily Trade Idea Scanner
======================================
Fast watchlist-wide scan using DuckDB (no per-ticker API calls).
Computes gap %, ATR%, RVOL, key levels, and ranks by actionability.

Usage:
    python scripts/session/scanner.py              # all watchlist tickers
    python scripts/session/scanner.py PLTR NVDA    # specific tickers
"""

import sys
import json
import logging
from pathlib import Path

import duckdb
import numpy as np

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
DB_PATH = str(REPO_ROOT / "data" / "market-read.duckdb")
DB_FALLBACK = str(REPO_ROOT / "data" / "market.duckdb")
TICKERS_FILE = REPO_ROOT / "data" / "tickers.json"

# Default watchlist (used if tickers.json has no watchlist key)
_DEFAULT_WATCHLIST = [
    "TSLA", "NVDA", "AMD", "MRVL", "PLTR", "COIN", "APP", "HIMS", "CRWV", "ARM",
    "RKLB", "HOOD", "SOFI", "SOUN", "RGTI", "SMCI",
    "AAPL", "MSFT", "META", "AMZN", "GOOGL", "AVGO", "MU", "CRWD", "PANW", "NFLX",
    "ORCL", "TSM", "NU", "AFRM", "SNOW", "TEAM", "DOCU", "WDAY", "DOCN", "UNH",
    "OKTA", "PYPL", "NVO",
    "GLD", "SLV", "IBIT", "BABA",
    "QBTS", "APLD", "IREN", "SMR", "ALAB", "MDB",
    "AXON", "TTD", "ZS", "ADBE",
    "SPY", "QQQ",
]


def _load_watchlist() -> list[str]:
    """Load watchlist from tickers.json, fall back to default."""
    import json
    try:
        data = json.loads(TICKERS_FILE.read_text())
        wl = data.get("watchlist")
        if isinstance(wl, list) and len(wl) > 0:
            return wl
    except Exception:
        pass
    return list(_DEFAULT_WATCHLIST)


def _save_watchlist(tickers: list[str]):
    """Save watchlist back to tickers.json."""
    import json
    try:
        data = json.loads(TICKERS_FILE.read_text())
    except Exception:
        data = {}
    data["watchlist"] = tickers
    TICKERS_FILE.write_text(json.dumps(data, indent=2))


# Load at import time for backward compat (other modules import WATCHLIST)
WATCHLIST = _load_watchlist()

# Sector classification for rotation analysis
SECTORS = {
    "Tech/Semis": ["NVDA", "AMD", "MRVL", "AVGO", "MU", "TSM", "ARM", "SMCI", "ALAB"],
    "Software": ["MSFT", "CRWD", "PANW", "SNOW", "TEAM", "DOCU", "WDAY", "DOCN", "OKTA", "ZS", "ADBE", "MDB", "ORCL"],
    "Internet/Social": ["META", "GOOGL", "AMZN", "NFLX", "BABA", "TTD"],
    "Fintech": ["COIN", "HOOD", "SOFI", "PYPL", "AFRM", "NU"],
    "Momentum/Speculative": ["TSLA", "PLTR", "APP", "HIMS", "CRWV", "RKLB", "SOUN", "RGTI", "QBTS", "APLD", "IREN", "SMR"],
    "Healthcare": ["UNH", "NVO"],
    "Consumer/Defense": ["AAPL", "AXON"],
    "Macro/Commodities": ["GLD", "SLV", "IBIT", "SPY", "QQQ"],
}

TICKER_TO_SECTOR = {}
for sec, tickers in SECTORS.items():
    for t in tickers:
        TICKER_TO_SECTOR[t] = sec


def scan(tickers: list[str] | None = None) -> dict:
    """Run the scanner on the given tickers (or full watchlist)."""
    tickers = tickers or WATCHLIST

    # Connect to DuckDB (read-only snapshot)
    import os
    db_path = DB_PATH if os.path.exists(DB_PATH) else DB_FALLBACK
    try:
        con = duckdb.connect(db_path, read_only=True)
    except Exception:
        con = duckdb.connect(DB_FALLBACK, read_only=True)

    in_clause = ",".join(f"'{t}'" for t in tickers)

    # ── Pull last 2 daily bars per ticker (today + yesterday) ──
    rows = con.execute(f"""
        WITH ranked AS (
            SELECT ticker, ts, open, high, low, close, volume,
                   row_number() OVER (PARTITION BY ticker ORDER BY ts DESC) AS rn
            FROM bars
            WHERE timeframe = '1d' AND ticker IN ({in_clause})
        )
        SELECT ticker, ts, open, high, low, close, volume, rn
        FROM ranked WHERE rn <= 2
        ORDER BY ticker, rn
    """).fetchall()

    # ── Pull ATR (14-day) per ticker ──
    atr_rows = con.execute(f"""
        WITH daily AS (
            SELECT ticker, high, low, close,
                   LAG(close) OVER (PARTITION BY ticker ORDER BY ts) AS prev_close
            FROM bars
            WHERE timeframe = '1d' AND ticker IN ({in_clause})
        ),
        tr AS (
            SELECT ticker,
                   GREATEST(high - low, ABS(high - prev_close), ABS(low - prev_close)) AS true_range
            FROM daily WHERE prev_close IS NOT NULL
        ),
        numbered AS (
            SELECT ticker, true_range,
                   row_number() OVER (PARTITION BY ticker ORDER BY ticker) AS rn,
                   count(*) OVER (PARTITION BY ticker) AS cnt
            FROM tr
        ),
        atr AS (
            SELECT ticker,
                   AVG(true_range) AS atr_14
            FROM numbered WHERE rn > cnt - 14
            GROUP BY ticker
        )
        SELECT ticker, atr_14 FROM atr
    """).fetchall()

    # ── Pull 20-day avg volume per ticker ──
    vol_rows = con.execute(f"""
        SELECT ticker, AVG(volume) AS avg_vol
        FROM (
            SELECT ticker, volume,
                   row_number() OVER (PARTITION BY ticker ORDER BY ts DESC) AS rn
            FROM bars WHERE timeframe = '1d' AND ticker IN ({in_clause})
        ) WHERE rn <= 20
        GROUP BY ticker
    """).fetchall()

    # ── 52-week high per ticker ──
    high52_rows = con.execute(f"""
        SELECT ticker, MAX(high) AS high_52w, MIN(low) AS low_52w
        FROM (
            SELECT ticker, high, low,
                   row_number() OVER (PARTITION BY ticker ORDER BY ts DESC) AS rn
            FROM bars WHERE timeframe = '1d' AND ticker IN ({in_clause})
        ) WHERE rn <= 252
        GROUP BY ticker
    """).fetchall()

    # ── SMA 50 / 200 ──
    sma_rows = con.execute(f"""
        WITH recent AS (
            SELECT ticker, close,
                   row_number() OVER (PARTITION BY ticker ORDER BY ts DESC) AS rn
            FROM bars WHERE timeframe = '1d' AND ticker IN ({in_clause})
        )
        SELECT ticker,
               AVG(CASE WHEN rn <= 50 THEN close END) AS sma50,
               AVG(CASE WHEN rn <= 200 THEN close END) AS sma200
        FROM recent WHERE rn <= 200
        GROUP BY ticker
    """).fetchall()

    con.close()

    # Build lookup maps
    atr_map = {r[0]: float(r[1]) for r in atr_rows if r[1]}
    vol_map = {r[0]: float(r[1]) for r in vol_rows if r[1]}
    high52_map = {r[0]: (float(r[1]), float(r[2])) for r in high52_rows}
    sma_map = {r[0]: (float(r[1]) if r[1] else None, float(r[2]) if r[2] else None) for r in sma_rows}

    # Group daily bars by ticker
    ticker_bars = {}
    for r in rows:
        t = r[0]
        if t not in ticker_bars:
            ticker_bars[t] = {}
        ticker_bars[t][r[7]] = {
            "ts": str(r[1]), "open": float(r[2]), "high": float(r[3]),
            "low": float(r[4]), "close": float(r[5]), "volume": float(r[6]),
        }

    # ── Build results ──
    results = []
    for t in tickers:
        bars = ticker_bars.get(t)
        if not bars or 1 not in bars:
            continue

        latest = bars[1]  # most recent bar
        prev = bars.get(2)  # prior bar

        price = latest["close"]
        prev_close = prev["close"] if prev else latest["open"]

        gap_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
        gap_dir = "UP" if gap_pct > 0.3 else "DOWN" if gap_pct < -0.3 else "FLAT"

        atr = atr_map.get(t)
        atr_pct = round(atr / price * 100, 2) if atr and price else None
        avg_vol = vol_map.get(t, 0)
        vol_ratio = round(latest["volume"] / avg_vol, 2) if avg_vol > 0 else 0

        h52, l52 = high52_map.get(t, (None, None))
        sma50, sma200 = sma_map.get(t, (None, None))

        dist_52w_high = round((price - h52) / h52 * 100, 2) if h52 else None

        # Above key MAs?
        above_sma50 = price > sma50 if sma50 else None
        above_sma200 = price > sma200 if sma200 else None

        # Setup classification
        abs_gap = abs(gap_pct)
        if abs_gap >= 3 and vol_ratio >= 1.5:
            setup = "gap-and-go"
        elif abs_gap >= 3 and vol_ratio < 0.8:
            setup = "gap-fade"
        elif abs_gap >= 1.5 and vol_ratio >= 1.2:
            setup = "gap-and-go"
        elif abs_gap >= 1.5 and vol_ratio < 0.8:
            setup = "gap-fill"
        elif abs_gap < 0.5:
            setup = "flat"
        else:
            setup = "watch"

        # Actionability score (for ranking): |gap| * rvol * (near 52w high bonus)
        near_high_bonus = 1.3 if dist_52w_high and dist_52w_high > -5 else 1.0
        score = round(abs_gap * max(vol_ratio, 0.1) * near_high_bonus, 2)

        sector = TICKER_TO_SECTOR.get(t, "Other")

        results.append({
            "ticker": t,
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "gap_pct": gap_pct,
            "gap_direction": gap_dir,
            "volume": int(latest["volume"]),
            "avg_volume": int(avg_vol),
            "vol_ratio": vol_ratio,
            "atr": atr,
            "atr_pct": atr_pct,
            "sma50": round(sma50, 2) if sma50 else None,
            "sma200": round(sma200, 2) if sma200 else None,
            "above_sma50": above_sma50,
            "above_sma200": above_sma200,
            "high_52w": h52,
            "low_52w": l52,
            "dist_52w_high_pct": dist_52w_high,
            "day_high": round(latest["high"], 2),
            "day_low": round(latest["low"], 2),
            "setup": setup,
            "score": score,
            "sector": sector,
            "bar_date": latest["ts"][:10],
        })

    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)

    # Sector summary
    sector_agg = {}
    for r in results:
        sec = r["sector"]
        if sec not in sector_agg:
            sector_agg[sec] = {"count": 0, "avg_gap": 0, "gappers_up": 0, "gappers_down": 0}
        sector_agg[sec]["count"] += 1
        sector_agg[sec]["avg_gap"] += r["gap_pct"]
        if r["gap_pct"] > 0.3:
            sector_agg[sec]["gappers_up"] += 1
        elif r["gap_pct"] < -0.3:
            sector_agg[sec]["gappers_down"] += 1
    for sec in sector_agg:
        c = sector_agg[sec]["count"]
        sector_agg[sec]["avg_gap"] = round(sector_agg[sec]["avg_gap"] / c, 2) if c else 0

    # Top trade ideas (gap-and-go setups)
    ideas = [r for r in results if r["setup"] in ("gap-and-go", "gap-fade")]

    return {
        "scanned": len(results),
        "results": results,
        "top_ideas": ideas[:10],
        "sectors": sector_agg,
        "gappers_up": len([r for r in results if r["gap_pct"] > 0.3]),
        "gappers_down": len([r for r in results if r["gap_pct"] < -0.3]),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    tickers = [t.upper() for t in sys.argv[1:]] if len(sys.argv) > 1 else None
    print(json.dumps(scan(tickers), indent=2, default=str))
