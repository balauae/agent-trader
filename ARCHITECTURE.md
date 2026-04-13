# Agent Trader — Architecture

**Last updated:** 2026-04-14

## Overview

Agent Trader is a personal trading infrastructure consisting of three runtime services, a historical data store, and integration with kairobm (AI agent gateway). It monitors live positions, runs technical analysis, delivers alerts, and provides data for AI-driven trading decisions.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   Go Watcher ◄──── TradingView WebSocket (live bars)         │
│   (Unix socket)                                              │
│   • Real-time price monitoring (6 positions)                 │
│   • VWAP, RSI, EMA, MACD, ATR, BB calculations              │
│   • Alert engine (stop hit, target, VWAP break, flash moves) │
│   • /analyze endpoint (4ms response)                         │
│   • Writes live bars to DuckDB                               │
│   • Seeded from DuckDB on startup (300 daily bars)           │
│                                                              │
│   Python Bridge (FastAPI, port 8000)                         │
│   • Wraps Python analysis scripts as HTTP endpoints          │
│   • News (yfinance + Finviz), earnings, fundamentals         │
│   • Pattern recognition, S/R levels, VCP scanner             │
│   • /history endpoint reads from DuckDB                      │
│                                                              │
│   DuckDB (data/market.duckdb)                                │
│   • 2.3M+ historical bars across 49+ tickers                │
│   • 11 timeframes (1m to monthly)                            │
│   • Daily data back to 1972 for some tickers                 │
│   • Fed by: TV bulk loader + Go watcher live writes          │
│                                                              │
│   kairobm Specialists                                        │
│   • trader — analysis, positions, code maintenance           │
│   • data-ops — data loading, syncing, DuckDB management     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Services

### 1. Go Watcher (`tradedesk-watcher`)

**Binary:** `bin/tradedesk-watcher`
**Source:** `watcher/` (~3,500 LOC Go)
**API:** Unix socket at `/tmp/tradedesk-manager.sock`
**Systemd:** `~/.config/systemd/user/tradedesk-watcher.service`

Connects to TradingView via WebSocket, monitors all active positions in real-time.

| Endpoint | What it returns |
|---|---|
| `GET /health` | Uptime, watcher count, silence status |
| `GET /status` | All positions: price, VWAP, RSI, P&L |
| `GET /status/{ticker}` | Single position status |
| `GET /analyze/{ticker}` | Full technical analysis (indicators, signals, bias) — **4ms** |
| `GET /analyze` | Analysis for all watched tickers |
| `POST /watch` | Start watching a ticker |
| `POST /update/{ticker}` | Update stop/target levels |
| `POST /silence` | Mute alerts |
| `POST /unsilence` | Resume alerts |
| `DELETE /stop/{ticker}` | Stop watching |

**Metrics calculated in real-time:**
- VWAP with 1σ/2σ bands
- RSI (14-period, Wilder's smoothing)
- EMA 9 / EMA 21
- SMA 50 (from bar buffer)
- MACD (12, 26, 9)
- ATR (14-period)
- Bollinger Bands (20-period, 2σ)
- Volume tracker with spike detection
- Support/Resistance from swing pivots

**Alert types:**
- Stop hit / Target hit (critical)
- VWAP break / reclaim (warning)
- Flash move >1.5% (critical)
- Near stop <1.5% (warning)
- RSI overbought >70 / oversold <30
- High volume sell candle
- S/R proximity

**DuckDB integration:**
- On startup: loads 300 daily bars from DuckDB → indicators accurate immediately
- On every bar: writes to DuckDB async (live persistence)

### 2. Python Bridge (`tradedesk-bridge`)

**Entry:** `bridge/main.py`
**Port:** `localhost:8000`
**Systemd:** `~/.config/systemd/user/tradedesk-bridge.service`

FastAPI server that wraps Python analysis scripts. Each endpoint spawns a subprocess.

| Endpoint | Script | Speed | Data source |
|---|---|---|---|
| `/analyze/{ticker}` | `analysis/technical.py` | ~1.3s | tvdatafeed |
| `/technical/{ticker}` | `analysis/technical.py` | ~1s | tvdatafeed |
| `/vwap/{ticker}` | `feeds/vwap.py` | ~1.9s | tvdatafeed |
| `/pattern/{ticker}` | `analysis/patterns.py` | ~1.4s | tvdatafeed |
| `/news/{ticker}` | `feeds/news.py` | ~1.4s | yfinance + Finviz |
| `/earnings/{ticker}` | `earnings_expert.py` | ~12s | yfinance |
| `/fundamental/{ticker}` | `analysis/fundamental.py` | ~2s | yfinance |
| `/sr-multi/{ticker}` | `analysis/levels.py` | ~2s | tvdatafeed |
| `/calendar` | `feeds/econ_calendar.py` | ~2.5s | scraping |
| `/history/{ticker}` | — (direct DuckDB query) | ~10ms | DuckDB |
| `/positions` | — (proxy to Go watcher) | ~50ms | Go watcher |
| `/alerts` | — (SQLite query) | ~100ms | alerts.db |

### 3. DuckDB (`data/market.duckdb`)

Historical bar storage for analysis, pattern recognition, and backtesting.

**Schema:**
```sql
CREATE TABLE bars (
    ticker    VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,  -- 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M
    ts        TIMESTAMP NOT NULL,
    open      DOUBLE,
    high      DOUBLE,
    low       DOUBLE,
    close     DOUBLE,
    volume    DOUBLE,
    PRIMARY KEY (ticker, timeframe, ts)
);
```

**Current stats:** 2.3M+ bars, 49 tickers, 11 timeframes, 174 MB

**Data management scripts:**
| Script | Purpose |
|---|---|
| `scripts/data/load_full.py TICKER` | Full load for new tickers (~25s each) |
| `scripts/data/load_delta.py` | Incremental update (only new bars) |
| `scripts/data/sync_watchlist.py` | Health check + auto-sync all tickers |
| `scripts/data/query_bars.py --stats` | Diagnostic: show bar counts |
| `scripts/refresh_tv_token.py` | Refresh TradingView JWT token |

**Data sources per timeframe:**
| Timeframe | Bars per ticker | History depth |
|---|---|---|
| 1m | ~5,800 | 3 weeks |
| 3m | ~5,000 | 2 months |
| 5m | ~5,300 | 3 months |
| 15m | ~5,000 | 9 months |
| 30m | ~7,400 | 1.3 years |
| 1h | ~5,700 | 3.3 years |
| 2h | ~5,300 | 5 years |
| 4h | ~5,100 | 10 years |
| 1d | ~3,000-10,000 | 5-40 years |
| 1w | ~300-2,800 | 5-50 years |
| 1M | ~60-540 | 5-50 years |

---

## Data Flow

```
TradingView
    │
    ├── WebSocket (live) ──► Go Watcher ──► Alerts (Telegram)
    │                              │
    │                              ├──► /analyze API (4ms)
    │                              └──► DuckDB (async write)
    │
    ├── tvdatafeed (historical) ──► Python loader ──► DuckDB
    │
    └── tvdatafeed (on-demand) ──► Python Bridge scripts
                                       │
yfinance ──────────────────────────────┤
Finviz ────────────────────────────────┘

DuckDB
    │
    ├──► Go Watcher (startup seeding)
    ├──► Bridge /history endpoint
    ├──► kairobm agents (via exec + query_bars.py)
    └──► Future: pattern scanner, backtester
```

---

## kairobm Integration

Two specialist agents in kairobm own this project:

**trader** (`~/.kairobm/workspace/agents/trader/agent.md`)
- Runs analysis via Go watcher or bridge API
- Monitors positions, manages alerts
- Maintains codebase (Go + Python)
- Uses `batch_exec` for parallel multi-ticker operations

**data-ops** (`~/.kairobm/workspace/agents/data-ops/agent.md`)
- Loads historical data into DuckDB
- Runs delta syncs and health checks
- Refreshes TradingView token

**Trading workspace** at `/admin/workspaces/trading`:
- Live positions widget (auto-refresh from Go watcher)
- Per-ticker tabs with TradingView chart + technical indicators + news
- Agent chat panel for ad-hoc analysis
- Both trader and data-ops agents available

---

## File Structure

```
agent-trader/
├── bin/                          # Compiled Go binary
│   └── tradedesk-watcher
├── bridge/                       # Python FastAPI bridge
│   └── main.py                   # HTTP wrapper for scripts
├── data/                         # Runtime data
│   ├── market.duckdb             # Historical bars (2.3M+)
│   ├── positions.json            # Active positions
│   ├── alerts.db                 # SQLite alert log
│   └── tickers.json              # Exchange mappings
├── scripts/
│   ├── analysis/                 # Technical analysis scripts
│   │   ├── technical.py          # Full indicator sweep
│   │   ├── patterns.py           # Chart pattern recognition
│   │   ├── fundamental.py        # P/E, revenue, valuation
│   │   └── levels.py             # S/R level detection
│   ├── data/                     # Data management
│   │   ├── load_full.py          # Full historical load
│   │   ├── load_delta.py         # Incremental update
│   │   ├── sync_watchlist.py     # Health check + auto-sync
│   │   ├── query_bars.py         # Diagnostic tool
│   │   ├── load_history.py       # Core loader (shared logic)
│   │   └── fetcher.py            # tvdatafeed wrapper
│   ├── feeds/                    # Data acquisition
│   │   ├── vwap.py               # VWAP analysis
│   │   ├── news.py               # Headlines (yfinance + Finviz)
│   │   └── econ_calendar.py      # Economic events
│   ├── refresh_tv_token.py       # TradingView JWT refresh
│   └── orchestrator.py           # Intent router (14K+ LOC)
├── skills/                       # AI agent persona definitions
│   └── (18 specialist specs)
├── watcher/                      # Go watcher source
│   ├── cmd/watcher/main.go       # Entry point
│   ├── internal/
│   │   ├── api/server.go         # Unix socket HTTP API
│   │   ├── engine/
│   │   │   ├── supervisor.go     # Manages per-ticker goroutines
│   │   │   ├── watcher.go        # Per-ticker monitoring loop
│   │   │   ├── registry.go       # Thread-safe metrics store
│   │   │   └── barbuffer.go      # Circular bar buffer
│   │   ├── metrics/              # VWAP, RSI, EMA, MACD, ATR, Volume
│   │   ├── alerts/conditions.go  # Alert trigger logic
│   │   ├── notifier/notifier.go  # Telegram delivery
│   │   ├── store/duckdb.go       # DuckDB read/write
│   │   └── tvconn/               # TradingView WebSocket
│   ├── config.json
│   ├── Makefile
│   └── go.mod
├── .secrets/                     # Git-ignored
│   ├── tradingview.json          # TV auth token
│   └── telegram.json             # Bot token + chat ID
└── .venv/                        # Python virtual environment
```

---

## Operations

### Start/stop services
```bash
systemctl --user start|stop|restart tradedesk-watcher
systemctl --user start|stop|restart tradedesk-bridge
```

### Build Go watcher
```bash
cd watcher && make build    # compile
cd watcher && make deploy   # compile + restart service
```

### Refresh TradingView token
```bash
.venv/bin/python scripts/refresh_tv_token.py
```
Opens Chrome with kairobm browser profile (`~/.kairobm/browser/tradingview`), extracts JWT from TradingView page, saves to `.secrets/tradingview.json`. Token expires every ~4 hours.

### Data sync
```bash
PYTHONPATH=scripts .venv/bin/python scripts/data/sync_watchlist.py --report  # health check
PYTHONPATH=scripts .venv/bin/python scripts/data/sync_watchlist.py           # auto-sync
PYTHONPATH=scripts .venv/bin/python scripts/data/load_full.py TICKER        # new ticker
PYTHONPATH=scripts .venv/bin/python scripts/data/load_delta.py              # incremental
```

**Important:** DuckDB has single-writer lock. Pause the Go watcher before large data loads:
```bash
kill -STOP $(pgrep -x tradedesk-watch)   # pause
# ... run data load ...
kill -CONT $(pgrep -x tradedesk-watch)   # resume
```

---

## Watchlist (52 tickers)

| Category | Tickers |
|---|---|
| Momentum | TSLA, NVDA, AMD, MRVL, PLTR, COIN, APP, HIMS, CRWV, ARM, RKLB, HOOD, SOFI, SOUN, RGTI, SMCI |
| Growth | AAPL, MSFT, META, AMZN, GOOGL, AVGO, MU, CRWD, PANW, NFLX, ORCL, TSM, NU, AFRM, SNOW, TEAM, DOCU, WDAY, DOCN, UNH, OKTA, PYPL, NVO |
| Macro/Crypto | GLD, SLV, IBIT, BABA |
| Speculative | QBTS, APLD, IREN, SMR, ALAB, MDB |
| Swing | AXON, TTD, ZS, ADBE |
| Index ETFs | SPY, QQQ |

Active positions: GLD, MU, ARM, CRWV, AAPL, PLTR (see `data/positions.json`)
