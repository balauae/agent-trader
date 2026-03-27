# TradeDesk — Reflection & Capability Map

> Last updated: 2026-03-28

---

## What Is This Repo?

A personal AI trading assistant for Bala, built on top of OpenClaw.
Two distinct layers:

1. **AI Layer** — OpenClaw skills + Python scripts for on-demand analysis (ask questions, get answers)
2. **Watcher Layer** — Go binary that connects to TradingView WebSocket 24/7 and sends real-time alerts to Telegram

---

## Architecture Overview

```
Telegram (Bala)
     │
     ▼
OpenClaw (agent-trader)
     │
     ├── Skills (SKILL.md files) — AI analysis on demand
     │       ├── orchestrator     ← routes all messages
     │       ├── technical-analyst
     │       ├── vwap-watcher
     │       ├── pattern-finder
     │       ├── news-fetcher
     │       ├── earnings-expert
     │       ├── fundamental-analyst
     │       ├── economic-calendar
     │       ├── scanner
     │       ├── premarket-specialist
     │       ├── market-open-scalper
     │       ├── postmarket-summarizer
     │       ├── overnight-expert
     │       ├── timeframe-analyzer
     │       └── watcher-control  ← controls Go watcher via API
     │
     ├── Python Scripts (scripts/) — called by skills + bridge
     │
     └── FastAPI Bridge (bridge/main.py) ← HTTP on port 8000
              │
              ▼
         Go Watcher (bin/tradedesk-watcher) — systemd service
              │
              ├── Supervisor (goroutine manager)
              ├── Per-ticker goroutines (GLD, MU, etc.)
              ├── TradingView WebSocket (real-time prices)
              ├── Metrics (VWAP, RSI, EMA, MACD, ATR)
              ├── Alert Engine → Telegram
              └── HTTP API (/tmp/tradedesk-manager.sock)
```

---

## Layer 1: AI Skills (On-Demand Analysis)

Talk to TradeDesk in Telegram — it routes to the right skill.

| Skill | How to trigger | What it does |
|-------|---------------|-------------|
| `orchestrator` | All messages | Routes to right specialist |
| `technical-analyst` | "analyze MU", "what's TSLA doing" | Price, RSI, EMA, MACD, bias, support/resistance |
| `vwap-watcher` | "vwap MU", "is GLD above vwap" | VWAP analysis, bands, setup detection |
| `pattern-finder` | "patterns on NVDA" | Chart patterns (double top, H&S, flags, etc.) |
| `news-fetcher` | "news MU", "what's happening with TSLA" | Latest headlines, impact scoring |
| `earnings-expert` | "earnings MU", "when does NVDA report" | Dates, expected move, historical reactions, IV crush |
| `fundamental-analyst` | "fundamentals AAPL" | P/E, revenue, debt, valuation |
| `economic-calendar` | "calendar", "what's this week" | Fed, CPI, NFP, earnings dates |
| `scanner` | "scan momentum", "what's moving" | Two-stage scanner: RSI/bias across watchlists |
| `premarket-specialist` | Pre-market hours (12–5:30 PM AbuDhabi) | Gap analysis, pre-market movers |
| `market-open-scalper` | Open window (5:30–6 PM AbuDhabi) | Opening range, first 30 min setups |
| `postmarket-summarizer` | After hours (midnight–4 AM AbuDhabi) | Day recap, after-hours moves |
| `overnight-expert` | Overnight (4 AM–12 PM AbuDhabi) | Futures, overnight gaps, Asia/EU session |
| `timeframe-analyzer` | "MU on 5min", "TSLA 1hour" | Multi-timeframe analysis |
| `watcher-control` | "status", "watch NVDA", "silence" | Controls Go watcher |

### Python Scripts (backing the skills)

| Script | Output |
|--------|--------|
| `technical_analyst.py TICKER` | JSON: bias, indicators, levels, signals |
| `vwap_watcher.py TICKER` | JSON: VWAP, bands, distance, setup |
| `pattern_finder.py TICKER` | JSON: patterns, confidence, entry/stop/target |
| `news_fetcher.py TICKER` | JSON: headlines, publisher, impact |
| `earnings_expert.py TICKER` | JSON: dates, expected move, historical |
| `fundamental_analyst.py TICKER` | JSON: financials, valuation |
| `economic_calendar.py` | JSON: events, impact level |
| `scanner.py` | JSON: screened tickers, RSI, bias |
| `multi_analyze.py TICKER1 TICKER2...` | JSON: batch analysis |
| `premarket_specialist.py` | JSON: pre-market gaps, movers |
| `timeframe_analyzer.py TICKER TF` | JSON: multi-TF analysis |

All scripts:
- Take ticker as first arg
- Print JSON to stdout
- Use `.venv/bin/python` (uv managed)
- No ta-lib, no pandas-ta — pure pandas

---

## Layer 2: Go Watcher (Real-Time)

### Run / Control

```bash
# Start/stop via systemd
systemctl --user start tradedesk-watcher
systemctl --user stop tradedesk-watcher
systemctl --user restart tradedesk-watcher

# Rebuild after code changes
cd ~/dev/apps/agent-trader/watcher
make deploy

# Logs
journalctl --user -u tradedesk-watcher -f
```

### Positions File

Edit `watcher/data/positions.json` to set what's watched on startup:
```json
[
  {
    "ticker": "GLD",
    "shares": 250,
    "avg_price": 381.80,
    "stop": 395.00,
    "target": 420.00,
    "direction": "long",
    "exchange": "AMEX"
  }
]
```

### HTTP API (Unix Socket)

Socket: `/tmp/tradedesk-manager.sock`

```bash
BASE="curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost"

# Health
$BASE/health

# All positions status (live price, VWAP, RSI, P&L, distances)
$BASE/status

# Start watching a ticker
curl -s -X POST --unix-socket /tmp/tradedesk-manager.sock http://localhost/watch \
  -H "Content-Type: application/json" \
  -d '{"ticker":"NVDA","exchange":"NASDAQ","stop":105,"target":130}'

# Stop watching
$BASE/stop/NVDA

# Update levels
curl -s -X POST --unix-socket /tmp/tradedesk-manager.sock http://localhost/update/MU \
  -d '{"stop":350,"target":385}'

# Silence all alerts (persists across restarts)
curl -s -X POST --unix-socket /tmp/tradedesk-manager.sock http://localhost/silence

# Resume alerts
curl -s -X POST --unix-socket /tmp/tradedesk-manager.sock http://localhost/unsilence
```

### Alerts Sent to Telegram

| Alert | Trigger | Severity |
|-------|---------|---------|
| 🚨 Stop hit | Price crosses stop level | Critical |
| 🎯 Target hit | Price crosses target level | Critical |
| ⚡ Flash move | Price moves >1.5% in 1 bar | Critical |
| ⚠️ Near stop | Price within 1.5% of stop | Warning |
| 📉 VWAP break | Price crosses below VWAP | Warning |
| 📈 VWAP reclaim | Price crosses above VWAP | Warning |
| 📊 High volume | Sell candle with >2x avg volume | Warning |
| 📉 RSI oversold | RSI ≤ 30 | Warning |
| 📈 RSI overbought | RSI ≥ 70 | Warning |

Cooldown: 15 min per alert type per ticker.
Rate limit: 5 alerts/min globally. Critical alerts bypass rate limit.

### Metrics Computed Per Tick

- VWAP (cumulative, resets at market open)
- RSI (14-period)
- EMA 9
- EMA 20
- MACD (12/26/9)
- ATR (14-period)
- Volume tracker (spike detection)

---

## Layer 3: FastAPI Bridge

Wraps Python scripts over HTTP for Go watcher to call.

```bash
# Start
systemctl --user start tradedesk-bridge

# Endpoints
GET  http://localhost:8000/health
GET  http://localhost:8000/news/{ticker}
GET  http://localhost:8000/analyze/{ticker}
GET  http://localhost:8000/vwap/{ticker}
GET  http://localhost:8000/pattern/{ticker}
GET  http://localhost:8000/earnings/{ticker}
GET  http://localhost:8000/fundamental/{ticker}
GET  http://localhost:8000/calendar
```

---

## Data & Secrets

| File | Contents |
|------|---------|
| `.secrets/tradingview.json` | TV auth token, user_id, plan |
| `.secrets/telegram.json` | Bot token, chat_id |
| `data/tickers.json` | ~1500 ticker → exchange mappings |
| `data/positions.json` | Root-level positions (for Python scripts) |
| `watcher/data/positions.json` | Watcher positions (Go binary reads this) |
| `watcher/data/watcher-state.json` | Persisted silence state |
| `watcher/data/registry.json` | Active watcher registry |

---

## Market Hours (Abu Dhabi GMT+4)

| Session | Abu Dhabi | ET |
|---------|-----------|-----|
| Pre-market | 12:00 PM → 5:30 PM | 4 AM → 9:30 AM |
| Market open | 5:30 PM → midnight | 9:30 AM → 4 PM |
| After-hours | midnight → 4 AM | 4 PM → 8 PM |
| Overnight | 4 AM → 12 PM | closed |

---

## Known Gaps / Improvement Opportunities

### High Priority
- [ ] **`watch TICKER` from Telegram doesn't auto-save** — adding via API is lost on restart unless positions.json is updated manually
- [ ] **TV token auto-refresh fails overnight** — requires browser running; needs headless solution
- [ ] **GLD (AMEX) slow to connect** — TV sometimes takes 30-60s to resolve AMEX symbols

### Medium Priority
- [ ] **Periodic P&L snapshot** — cron to send status every 30 mins during market hours
- [ ] **Pre-market brief automation** — daily 5 PM AbuDhabi briefing on held positions
- [ ] **Volume spike alert not fully wired** — condition exists in alerts/conditions.go but not tested
- [ ] **Consecutive red bars alert** — not built yet
- [ ] **P&L threshold alert** — "down $500 from open" type alert

### Low Priority / Nice to Have
- [ ] **Sentiment monitor** — no free API found yet (StockTwits closed, Reddit PRAW deferred)
- [ ] **Twitter/X monitor** — no free API
- [ ] **Scanner Stage 2** — TV WebSocket throttles after ~25 tickers
- [ ] **`poc/` directory** — stale proof-of-concept, can be deleted
- [ ] **`agents/` directory** — original markdown agent specs, superseded by `skills/`; can be archived

### Refactor Opportunities
- [ ] **Two `positions.json` files** — root `data/positions.json` and `watcher/data/positions.json` are separate; should be one source of truth
- [ ] **`watcher/config/settings.json` vs `watcher/config.json`** — two config files, confusing; consolidate
- [ ] **`state/state.go`** — created but not used; dead code
- [ ] **`watcher/poc/`** — delete, no longer needed

---

## Quick Reference

```bash
# Ask anything
"analyze MU"
"news GLD"
"scan momentum"
"what's the calendar this week"

# Watcher commands
"status"          → live P&L all positions
"silence"         → mute alerts
"unsilence"       → resume alerts
"watch NVDA"      → add to watcher
"stop MU"         → remove from watcher

# Manual API
curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost/status
curl -s http://localhost:8000/analyze/GLD
```
