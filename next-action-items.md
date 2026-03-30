# Next Action Items — Updated March 30, 2026

## ✅ Completed (March 30)

- [x] Services running: `tradedesk-watcher` + `tradedesk-bridge`
- [x] S/R levels loading on startup
- [x] All new module paths tested and working (`scripts/analysis/`, `scripts/data/`, `scripts/feeds/`, `scripts/session/`)
- [x] Exchange map fix — AMEX ETFs/GLD now use correct exchange (commit `b2e3ea1`)
- [x] Bridge routes added: `/technical/{ticker}`, `/positions`, `/status`
- [x] Strategy fields verified: Weinstein, Williams %R, Raschke fade, Livermore pivot, CANSLIM
- [x] SQLite alert log working — AlertType string fix (commit `0a95be6`)
- [x] Stale flat scripts cleaned up — `data_fetcher.py` is intentional re-export shim (stays)
- [x] GLD hit target $420.00 — watcher alert fired correctly 🎯
- [x] TraderTV Mar 30 note processed and sent to Telegram
- [x] Pattern detection working — AAPL/NVDA/CRWV all show Double Top (90% conf)

---

## 🔧 Minor Fixes Needed

- [ ] `scripts/session/overnight.py` — `bias` key missing from output
- [ ] `scripts/vcp_scanner.py` — `vcp_detected` key missing from output

---

## 🔨 Build Queue (priority order)

### 1. Position Sizing & Risk Calculator
The missing risk management layer.

**Trigger:** `"size GLD 415 stop 410"` → instant calculation

**Formula (ATR-based):**
```
Shares = (Account × Risk%) / (Entry - Stop)

Example:
Account    = $50,000
Risk       = 1% = $500
Entry      = $415
Stop       = $410
Risk/share = $5
Shares     = 100
Dollar risk = $500
Target (2:1) = $425
```

**System rules:**
- Max risk per trade: 1–2% of account
- Max daily loss: 5% → stop trading
- Max drawdown: 15% → review system
- Min R/R: 2:1 before entering
- Correlation limit: max 3 correlated positions

**Integration:**
- Telegram: `"size GLD 415 stop 410"` → response
- Bridge: `POST /size` with entry/stop/account
- Watcher: include size suggestion in P&L snapshot

---

### 2. Break Alerts
`🔼 GLD broke above $420.59` — proximity detection exists, break detection missing.

Go watcher `conditions.go` — add break detection logic:
- Track last price vs level
- Fire `broke_above` / `broke_below` when price crosses

---

### 3. Pre-Market Brief Automation
Daily at 5:00 PM AbuDhabi (1 hr before open):
- Fetch TraderTV note
- Run premarket.py on watchlist top movers
- Send Telegram summary

Cron job: agentTurn payload, 5 PM AbuDhabi daily.

---

### 4. `watch TICKER` Persistence
`/watch` API adds ticker to watcher but **not** to `data/positions.json` → lost on restart.

Fix in `watcher/internal/api/server.go`:
- On `/watch` POST → also write to `positions.json`

---

### 5. S/R Levels Mid-Day Refresh
Currently loaded once on startup. Add refresh every 2 hours during market hours.

Fix in `watcher/internal/engine/supervisor.go`.

---

### 6. `/stop/TICKER` Bug Fix
Go watcher responds OK but goroutine doesn't actually die.
Must use `systemctl --user stop tradedesk-watcher` to kill all watchers.

Fix in `watcher/internal/api/server.go` — cancel goroutine context on stop.

---

## Phase 2 (after above done)

- [ ] Backtest existing signals (VWAP, S/R, VCP) on historical data
- [ ] Measure win rate, expectancy, Sharpe ratio
- [ ] Wire `tradertv` skill into orchestrator routing table
- [ ] Build trading AutoResearch system (`misc/autoresearch-trading/`)
- [ ] TV token auto-refresh when browser not running overnight

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
curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost/status
```
