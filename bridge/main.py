"""
TradeDesk FastAPI Bridge
Wraps existing Python analysis scripts so Go watcher can call them via HTTP.
Run: uvicorn bridge.main:app --port 8000
"""
import subprocess
import json
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
PYTHON = ROOT / ".venv" / "bin" / "python"

app = FastAPI(title="TradeDesk Bridge", version="1.0")

# Allow CORS from kairobm UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kairobm.duckdns.org", "http://localhost:18182"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def run_script(script: str, *args) -> dict:
    """Run a Python script and return its JSON stdout output."""
    cmd = [str(PYTHON), str(SCRIPTS / script), *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ROOT),
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or f"{script} failed"}
        output = result.stdout.strip()
        if not output:
            return {"error": "no output"}
        return json.loads(output)
    except subprocess.TimeoutExpired:
        return {"error": f"{script} timed out"}
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON: {e}", "raw": result.stdout[:500]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok", "bridge": "tradedesk"}


@app.get("/news/{ticker}")
def news(ticker: str):
    """Fetch latest news for a ticker."""
    data = run_script("feeds/news.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    """Full technical analysis for a ticker."""
    data = run_script("analysis/technical.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/vwap/{ticker}")
def vwap(ticker: str):
    """VWAP analysis for a ticker."""
    data = run_script("feeds/vwap.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/pattern/{ticker}")
def pattern(ticker: str):
    """Chart pattern detection for a ticker."""
    data = run_script("analysis/patterns.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/earnings/{ticker}")
def earnings(ticker: str):
    """Earnings info for a ticker."""
    data = run_script("earnings_expert.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/fundamental/{ticker}")
def fundamental(ticker: str):
    """Fundamental analysis for a ticker."""
    data = run_script("analysis/fundamental.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/calendar")
def calendar():
    """Today's economic calendar events."""
    data = run_script("feeds/econ_calendar.py")
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


import sqlite3 as _sqlite3
from datetime import date as _date

ALERTS_DB = "/home/bala/dev/apps/agent-trader/data/alerts.db"

def _query_alerts(query: str, params: tuple = ()):
    try:
        conn = _sqlite3.connect(f"file:{ALERTS_DB}?mode=ro", uri=True)
        conn.row_factory = _sqlite3.Row
        cur = conn.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        return []


@app.get("/alerts/{ticker}")
def get_alerts(ticker: str, date: str = None, limit: int = 100):
    """Alerts for a ticker. date=YYYY-MM-DD (default today), limit=N."""
    d = date or str(_date.today())
    rows = _query_alerts(
        "SELECT * FROM alerts WHERE ticker=? AND date(ts)=? ORDER BY ts DESC LIMIT ?",
        (ticker.upper(), d, limit)
    )
    return {"ticker": ticker.upper(), "date": d, "count": len(rows), "alerts": rows}


@app.get("/alerts")
def get_alerts_summary(date: str = None):
    """Summary of all alerts today grouped by ticker + type."""
    d = date or str(_date.today())
    rows = _query_alerts(
        "SELECT ticker, alert_type, COUNT(*) as count FROM alerts WHERE date(ts)=? GROUP BY ticker, alert_type ORDER BY count DESC",
        (d,)
    )
    return {"date": d, "summary": rows}


@app.get("/premarket/{ticker}")
def premarket(ticker: str):
    """Pre-market gap analysis for a single ticker."""
    data = run_script("session/premarket.py", ticker.upper())
    if "error" in data:
        # Return partial data (e.g. no premarket hours yet) rather than 500
        return data
    return data


@app.get("/premarket/scan")
def premarket_scan():
    """Run premarket analysis on all open positions (with per-ticker timeout)."""
    positions = _watcher_get("/status")
    if not isinstance(positions, list):
        return {"results": [], "error": "Watcher unavailable"}
    results = []
    errors = []
    for p in positions:
        t = p.get("ticker")
        if not t:
            continue
        data = run_script("session/premarket.py", t.upper())
        data["avg_price"] = p.get("avg_price", 0)
        data["shares"] = p.get("shares", 0)
        data["pnl_dollars"] = p.get("pnl_dollars", 0)
        if "error" in data and data.get("prior_close") is None:
            errors.append(f"{t}: {data.get('error','unknown')}")
        else:
            results.append(data)
    return {"results": results, "errors": errors, "count": len(results)}


@app.get("/postmarket/{ticker}")
def postmarket(ticker: str):
    """Post-market daily summary for a single ticker."""
    data = run_script("session/postmarket.py", ticker.upper())
    if "error" in data:
        return data
    return data


@app.get("/postmarket/scan")
def postmarket_scan():
    """Run postmarket summary on all open positions using fast mode (no extended hours fetch)."""
    positions = _watcher_get("/status")
    if not isinstance(positions, list):
        return {"results": [], "error": "Watcher unavailable"}

    # Use --fast flag to skip slow TV extended hours fetch
    import concurrent.futures
    tickers = [(p.get("ticker"), p) for p in positions if p.get("ticker")]
    results = []
    errors = []

    def analyze_one(item):
        t, p = item
        data = run_script("session/postmarket.py", t.upper(), "--fast")
        data["avg_price"] = p.get("avg_price", 0)
        data["shares"] = p.get("shares", 0)
        data["pnl_dollars"] = p.get("pnl_dollars", 0)
        return data

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(analyze_one, item): item[0] for item in tickers}
        for future in concurrent.futures.as_completed(futures, timeout=60):
            ticker = futures[future]
            try:
                data = future.result(timeout=20)
                if "error" in data:
                    errors.append(f"{ticker}: {data.get('error','')}")
                else:
                    results.append(data)
            except Exception as e:
                errors.append(f"{ticker}: {str(e)}")

    return {"results": results, "errors": errors, "count": len(results)}


@app.get("/timeframes/{ticker}")
def timeframes(ticker: str):
    """Multi-timeframe confluence analysis (1m, 5m, 15m, 1D)."""
    data = run_script("analysis/timeframes.py", ticker.upper())
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/vcp/scan")
def vcp_scan_all():
    """Scan all watchlist tickers for VCP patterns using DuckDB."""
    # Use the scanner's watchlist
    import sys
    sys.path.insert(0, str(SCRIPTS))
    try:
        from session.scanner import WATCHLIST
        results = []
        for t in WATCHLIST:
            data = run_script("vcp_scanner.py", t, "1D", "200")
            if "error" not in data and data.get("vcp_detected") or data.get("setup") not in (None, "none", ""):
                data["ticker"] = t
                results.append(data)
        return {"results": results, "scanned": len(WATCHLIST), "vcp_found": len(results)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/watchlist")
def get_watchlist():
    """Get full watchlist with DuckDB coverage per ticker."""
    import duckdb as _ddb
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS))
    from session.scanner import _load_watchlist, SECTORS, TICKER_TO_SECTOR
    # Reload from file each time (not the cached WATCHLIST constant)
    WATCHLIST = _load_watchlist()

    db_read = str(ROOT / "data" / "market-read.duckdb")
    db_main = str(ROOT / "data" / "market.duckdb")
    import os
    db_path = db_read if os.path.exists(db_read) else db_main

    try:
        con = _ddb.connect(db_path, read_only=True)
        rows = con.execute("""
            SELECT ticker,
                   COUNT(*) AS total_bars,
                   COUNT(DISTINCT timeframe) AS timeframes,
                   MAX(ts)::VARCHAR AS last_bar,
                   MIN(ts)::VARCHAR AS first_bar
            FROM bars
            GROUP BY ticker
            ORDER BY ticker
        """).fetchall()
        con.close()
    except Exception:
        rows = []

    coverage = {r[0]: {"total_bars": r[1], "timeframes": r[2], "last_bar": r[3], "first_bar": r[4]} for r in rows}

    tickers = []
    for t in WATCHLIST:
        cov = coverage.get(t, {})
        tickers.append({
            "ticker": t,
            "sector": TICKER_TO_SECTOR.get(t, "Other"),
            "in_duckdb": t in coverage,
            "total_bars": cov.get("total_bars", 0),
            "timeframes": cov.get("timeframes", 0),
            "last_bar": cov.get("last_bar"),
            "first_bar": cov.get("first_bar"),
        })

    # Also include tickers in DuckDB but not in watchlist
    extra = [t for t in coverage if t not in WATCHLIST]
    for t in sorted(extra):
        cov = coverage[t]
        tickers.append({
            "ticker": t,
            "sector": "Extra",
            "in_duckdb": True,
            "total_bars": cov["total_bars"],
            "timeframes": cov["timeframes"],
            "last_bar": cov["last_bar"],
            "first_bar": cov["first_bar"],
        })

    return {"tickers": tickers, "watchlist_count": len(WATCHLIST), "duckdb_count": len(coverage)}


@app.post("/watchlist/add/{ticker}")
def add_to_watchlist(ticker: str):
    """Add a ticker to the persistent watchlist."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS))
    from session.scanner import _load_watchlist, _save_watchlist
    t = ticker.upper()
    wl = _load_watchlist()
    if t in wl:
        return {"ok": True, "message": f"{t} already in watchlist", "count": len(wl)}
    wl.append(t)
    _save_watchlist(wl)
    return {"ok": True, "message": f"Added {t} to watchlist", "count": len(wl)}


@app.delete("/watchlist/remove/{ticker}")
def remove_from_watchlist(ticker: str):
    """Remove a ticker from the persistent watchlist."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS))
    from session.scanner import _load_watchlist, _save_watchlist
    t = ticker.upper()
    wl = _load_watchlist()
    if t not in wl:
        return {"ok": True, "message": f"{t} not in watchlist", "count": len(wl)}
    wl.remove(t)
    _save_watchlist(wl)
    return {"ok": True, "message": f"Removed {t} from watchlist", "count": len(wl)}


@app.get("/dataops/logs")
def get_logs(lines: int = 100):
    """Get recent cron/data operation logs."""
    import os
    log_dir = os.path.expanduser("~/.kairobm/logs")
    logs = {}
    for name in ["ticker-loads", "bars-refresh", "tv-token-refresh", "daily-brief"]:
        path = os.path.join(log_dir, f"{name}.log")
        if os.path.exists(path):
            with open(path, "r") as f:
                content = f.readlines()
                logs[name] = [l.rstrip() for l in content[-lines:]]
        else:
            logs[name] = []
    return {"logs": logs}


@app.get("/dataops/crons")
def get_crons():
    """Get current crontab entries."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        entries = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                if line.startswith("#"):
                    entries.append({"type": "comment", "text": line})
                continue
            parts = line.split(None, 5)
            if len(parts) >= 6:
                entries.append({
                    "type": "job",
                    "schedule": " ".join(parts[:5]),
                    "command": parts[5],
                    "raw": line,
                })
        return {"entries": entries}
    except Exception as e:
        return {"entries": [], "error": str(e)}


@app.post("/dataops/load/{ticker}")
def trigger_load(ticker: str):
    """Trigger background data load for a ticker, then update read snapshot."""
    t = ticker.upper()
    script_path = str(ROOT)
    python_path = str(PYTHON)

    # Wrapper script: load data then copy snapshot
    import tempfile, os
    wrapper = f"""
import subprocess, shutil
subprocess.run(["{python_path}", "scripts/data/load_full.py", "{t}"],
               cwd="{script_path}",
               env={{**dict(__import__('os').environ), "PYTHONPATH": "{script_path}/scripts"}})
# Update read snapshot so UI sees the data immediately
src = "{script_path}/data/market.duckdb"
dst = "{script_path}/data/market-read.duckdb"
if __import__('os').path.exists(src):
    shutil.copy2(src, dst)
"""
    child = subprocess.Popen(
        [python_path, "-c", wrapper],
        cwd=script_path,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    return {"ok": True, "ticker": t, "pid": child.pid, "message": f"Loading {t} in background"}


@app.get("/position-size")
def position_size(ticker: str, entry: float, stop: float, account: float = 100000, risk_pct: float = 1.0, target: float = None):
    """Calculate optimal position size based on risk management."""
    args = [ticker.upper(), str(entry), str(stop), "--account", str(account), "--risk-pct", str(risk_pct)]
    if target:
        args.extend(["--target", str(target)])
    data = run_script("tools/position_sizer.py", *args)
    if "error" in data:
        raise HTTPException(400, data["error"])
    return data


@app.get("/scanner/today")
def scanner_today():
    """Scan full watchlist for today's trade ideas (DuckDB-based, fast)."""
    data = run_script("session/scanner.py")
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/sr/{ticker}")
def support_resistance(ticker: str, timeframe: str = "1D", bars: int = 200):
    """Single-timeframe support & resistance levels."""
    data = run_script("analysis/levels.py", ticker.upper(), timeframe, str(bars))
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/vcp/{ticker}")
def vcp_scan(ticker: str, timeframe: str = "1D", bars: int = 200):
    """VCP pattern + SEPA template scan."""
    data = run_script("vcp_scanner.py", ticker.upper(), timeframe, str(bars))
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/sr-multi/{ticker}")
def support_resistance_multi(ticker: str, timeframes: str = "1D,1h", bars: int = 200):
    """Multi-timeframe confluent S/R levels."""
    data = run_script("analysis/levels.py", ticker.upper(), "multi", timeframes, str(bars))
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


@app.get("/technical/{ticker}")
def technical(ticker: str, timeframe: str = "1D"):
    """Technical analysis (alias for /analyze with timeframe param)."""
    data = run_script("analysis/technical.py", ticker.upper(), timeframe)
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


import duckdb as _duckdb

MARKET_DB = str(ROOT / "data" / "market.duckdb")


@app.get("/history/{ticker}")
def get_history(ticker: str, timeframe: str = "1d", bars: int = 200):
    """Get historical OHLCV bars from DuckDB."""
    try:
        con = _duckdb.connect(MARKET_DB, read_only=True)
        rows = con.execute("""
            SELECT ts::VARCHAR as timestamp, open, high, low, close, volume
            FROM bars
            WHERE ticker=? AND timeframe=?
            ORDER BY ts DESC
            LIMIT ?
        """, [ticker.upper(), timeframe, bars]).fetchall()
        con.close()

        if not rows:
            raise HTTPException(404, f"No data for {ticker.upper()} {timeframe}")

        return {
            "ticker": ticker.upper(),
            "timeframe": timeframe,
            "count": len(rows),
            "bars": [
                {"ts": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4], "v": r[5]}
                for r in reversed(rows)
            ],
        }
    except _duckdb.IOException:
        raise HTTPException(503, "Market database not available — run load_history.py first")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


WATCHER_SOCK = "/tmp/tradedesk-manager.sock"

def _watcher_get(path: str):
    """GET request to Go watcher via Unix socket using curl."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--unix-socket", WATCHER_SOCK, f"http://localhost{path}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except Exception as e:
        return None


@app.get("/positions")
def get_positions():
    """Live positions from Go watcher (price, VWAP, RSI, PnL)."""
    data = _watcher_get("/status")
    if data is None:
        raise HTTPException(503, "watcher not running")
    return data or []


@app.get("/status")
def get_status():
    """Watcher health + all active positions."""
    data = _watcher_get("/status")
    if data is None:
        raise HTTPException(503, "watcher not running")
    return {"watchers": data or [], "count": len(data) if data else 0}
