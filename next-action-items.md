# Next Action Items — Updated April 14, 2026

## Completed (April 12-14)

- [x] Go watcher `/analyze` endpoint — instant technical analysis (4ms vs 1.3s Python)
- [x] DuckDB integration — 2.3M+ bars, 49 tickers, 11 timeframes loaded
- [x] Go watcher startup seeding from DuckDB — indicators accurate immediately
- [x] Go watcher live bar persistence to DuckDB — async writes
- [x] Three data sync scripts: `load_full.py`, `load_delta.py`, `sync_watchlist.py`
- [x] Expanded to 20K bars, 11 timeframes (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M)
- [x] 52-ticker watchlist with exchange mappings
- [x] TradingView token refresh via kairobm browser profile (Chrome CDP)
- [x] Old duplicate scripts cleaned up
- [x] kairobm specialist agents: trader + data-ops
- [x] kairobm trading workspace with live widgets, tabs, TradingView charts
- [x] ARCHITECTURE.md documented

## Completed (March 30)

- [x] Services running: `tradedesk-watcher` + `tradedesk-bridge`
- [x] S/R levels loading on startup
- [x] Module paths reorganized (`scripts/analysis/`, `scripts/data/`, `scripts/feeds/`)
- [x] Exchange map fix — AMEX ETFs/GLD
- [x] SQLite alert log with AlertType string
- [x] Pattern detection working

---

## Minor Fixes Needed

- [ ] `scripts/session/overnight.py` — `bias` key missing from output
- [ ] `scripts/vcp_scanner.py` — `vcp_detected` key missing from output
- [ ] `/stop/TICKER` bug — goroutine doesn't die, must restart watcher
- [ ] DuckDB single-writer lock — need WAL mode or connection pooling for concurrent access
- [ ] 4 tickers not yet loaded in DuckDB: DOCN, HIMS, QBTS, SMR (TV token expired during load)

---

## Build Queue (priority order)

### 1. Position Sizing & Risk Calculator
```
Shares = (Account × Risk%) / (Entry - Stop)
Max risk per trade: 1-2%, Max daily loss: 5%, Min R/R: 2:1
```
Trigger: `"size GLD 415 stop 410"` → instant calculation

### 2. Break Alerts
S/R proximity exists but no break detection. Add `broke_above` / `broke_below` to Go watcher `conditions.go`.

### 3. Pre-Market Brief Automation
Daily 5 PM Abu Dhabi cron → fetch TraderTV note + run premarket.py → Telegram summary.

### 4. `/watch` Persistence
`/watch` API adds ticker but doesn't write to `positions.json` → lost on restart.

### 5. S/R Levels Mid-Day Refresh
Currently loaded once on startup. Add 2-hour refresh during market hours.

### 6. Bar Aggregation in Go Watcher
Live 1m bars → aggregate into 5m, 15m, 1h, 1d and write to DuckDB. Currently only writes 1m bars.

### 7. Pattern Scanner on DuckDB
Run pattern recognition (double bottom, H&S, VCP) directly against DuckDB historical data instead of fetching from TradingView each time.

---

## Phase 2 (after above)

- [ ] Backtest signals (VWAP, S/R, VCP) on historical DuckDB data
- [ ] Measure win rate, expectancy, Sharpe ratio
- [ ] AutoResearch system (`misc/autoresearch-trading/`)
- [ ] Move remaining Python bridge analysis to Go (patterns, S/R)
- [ ] Workspace chart annotations → agent vision analysis

---

## If something breaks

```bash
# Logs
journalctl --user -u tradedesk-watcher -f
journalctl --user -u tradedesk-bridge -f

# Restart
cd ~/dev/apps/agent-trader/watcher && make deploy
systemctl --user restart tradedesk-bridge

# Socket check
curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost/health

# DuckDB lock issue — pause watcher
kill -STOP $(pgrep -x tradedesk-watch)
# ... run data load ...
kill -CONT $(pgrep -x tradedesk-watch)

# Token refresh
.venv/bin/python scripts/refresh_tv_token.py
```
