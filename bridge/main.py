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

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
PYTHON = ROOT / ".venv" / "bin" / "python"

app = FastAPI(title="TradeDesk Bridge", version="1.0")


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
