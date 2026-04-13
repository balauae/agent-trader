# Agent Trader

Personal AI-powered trading infrastructure — real-time position monitoring, technical analysis, and historical data management.

## What it does

- **Go Watcher** — monitors live positions via TradingView WebSocket, calculates real-time indicators (VWAP, RSI, EMA, MACD, ATR, BB), fires alerts to Telegram
- **DuckDB** — 2.3M+ historical bars across 49 tickers, 11 timeframes, daily data back to 1972
- **Python Bridge** — FastAPI wrapper for analysis scripts (news, earnings, fundamentals, patterns)
- **kairobm Integration** — trader + data-ops specialist agents, trading workspace with live charts

## Quick Start

```bash
# Start services
systemctl --user start tradedesk-watcher
systemctl --user start tradedesk-bridge

# Check health
curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost/health
curl -s http://localhost:8000/health

# Instant analysis (4ms)
curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost/analyze/PLTR

# Sync market data
PYTHONPATH=scripts .venv/bin/python scripts/data/sync_watchlist.py
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system map including:
- Service endpoints and response times
- Data flow diagrams
- DuckDB schema and data management
- kairobm specialist integration
- File structure and operations guide

## Active Positions

Tracked in `data/positions.json`: GLD, MU, ARM, CRWV, AAPL, PLTR

## Watchlist (52 tickers)

Momentum, growth, macro/crypto, speculative, and swing categories. See [ARCHITECTURE.md](ARCHITECTURE.md#watchlist-52-tickers) for the full list.

## Key Directories

| Directory | What |
|---|---|
| `watcher/` | Go watcher source (~3,500 LOC) |
| `bridge/` | Python FastAPI bridge |
| `scripts/analysis/` | Technical, pattern, fundamental analysis |
| `scripts/data/` | DuckDB loaders and sync tools |
| `scripts/feeds/` | News, VWAP, economic calendar |
| `skills/` | AI agent persona definitions (18 specs) |
| `data/` | Runtime data (DuckDB, positions, alerts) |
