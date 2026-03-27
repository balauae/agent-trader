# TradeDesk Watcher Service — Spec

**Status:** Design phase — decisions locked  
**Priority:** High  
**Estimated build time:** 2-3 hours  
**Language:** Go (real-time watcher) + Python (analysis agents)  
**Last updated:** 2026-03-27

---

## Overview

A persistent background service that monitors live positions in real-time using TradingView data and sends intelligent alerts to Telegram. Zero manual intervention needed — it watches so you don't have to.

---

## Core Problem

Right now Bala has to:
1. Manually ask "check my positions"
2. Wait for orchestrator to run
3. Parse the output himself

**With Watcher:** Alerts come to you automatically the moment something important happens.

---

## Data Source

- **Primary:** TradingView WebSocket (existing `auth_token`)
- **Method:** Poll `get_ohlcv(ticker, "1m", bars=5)` every 30 seconds
- **Latency:** ~30 second delay — acceptable for position trading
- **Upgrade path:** True WebSocket streaming via `wss://data.tradingview.com` (Phase 2)

---

## Position Config (`data/positions.json`)

User editable file — update whenever positions change:

```json
{
  "positions": [
    {
      "ticker": "GLD",
      "shares": 250,
      "avg_price": 381.80,
      "stop": 390.00,
      "target": 420.00,
      "notes": "Gold long — hold through tariff uncertainty"
    },
    {
      "ticker": "MU",
      "shares": 159,
      "avg_price": 358.45,
      "stop": 348.00,
      "target": 382.00,
      "notes": "Bounce play — pattern target $378"
    }
  ],
  "settings": {
    "poll_interval_seconds": 30,
    "alert_cooldown_minutes": 15,
    "active_only_market_hours": true
  }
}
```

---

## Alert Types

### 🚨 Critical (instant alert)
| Trigger | Condition | Message |
|---------|-----------|---------|
| Stop hit | price ≤ stop | "🚨 GLD STOP HIT $390 — consider cutting" |
| Target hit | price ≥ target | "🎯 MU TARGET HIT $382 — consider trimming" |
| Flash crash | price drops >3% in 5 mins | "⚡ MU flash crash -3.2% in 5 mins" |

### ⚠️ Warning (alert once per condition)
| Trigger | Condition | Message |
|---------|-----------|---------|
| Near stop | price within 1% of stop | "⚠️ MU approaching stop — $352 (stop $348)" |
| VWAP break | price crosses below VWAP | "📉 MU broke below VWAP $356 — weakening" |
| VWAP reclaim | price crosses above VWAP | "📈 MU reclaimed VWAP $356 — strengthening" |
| High volume | volume >2x avg on down candle | "📊 MU unusual volume on sell candle" |

### 📊 Periodic Updates
| Frequency | Content |
|-----------|---------|
| Every 30 mins (market hours) | Mini P&L snapshot |
| Market open (5:30 PM Abu Dhabi) | Opening prices + gap direction |
| Market close (midnight Abu Dhabi) | EOD recap + overnight plan |
| On demand | "check positions" → instant update |

---

## Alert Format (Telegram)

```
🔔 TradeDesk Alert — 6:45 PM (Abu Dhabi)

📊 Position Update:
🟢 GLD  $408.20 (+$26.40) | P&L +$6,600
🟢 MU   $365.50 (+$7.05)  | P&L +$1,121
─────────────────────────
💰 Total: +$7,721

⚠️ MU approaching stop — $352 (stop $348)
📈 GLD VWAP reclaim — bullish intraday
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│         watcher_service.py              │
│                                         │
│  ┌─────────────┐    ┌────────────────┐  │
│  │ Poll Engine │    │  Alert Engine  │  │
│  │ (30s loop)  │───▶│ (condition     │  │
│  │             │    │  checker)      │  │
│  └─────────────┘    └───────┬────────┘  │
│                             │           │
│  ┌──────────────────────────▼────────┐  │
│  │        Notifier                   │  │
│  │  (OpenClaw message tool →         │  │
│  │   Telegram:8523037700)            │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         ↑
  data/positions.json
  (user editable)
```

---

## State Management

- `data/watcher_state.json` — tracks last alert times, last prices
- Cooldown per alert type (default 15 mins) — no spam
- Persists across restarts

```json
{
  "last_alerts": {
    "GLD_stop_warning": "2026-03-27T14:30:00",
    "MU_vwap_break": "2026-03-27T15:15:00"
  },
  "last_prices": {
    "GLD": 408.20,
    "MU": 365.50
  }
}
```

---

## Market Hours Awareness

| Abu Dhabi Time | Behavior |
|----------------|----------|
| 12:00 PM – 5:30 PM | Pre-market mode — poll every 60s, only critical alerts |
| 5:30 PM – midnight | Market hours — poll every 30s, all alerts active |
| Midnight – 4:00 AM | After hours — poll every 60s, only critical alerts |
| 4:00 AM – 12:00 PM | Overnight — paused (no TV data) |

---

## Deployment

### Run manually
```bash
python scripts/watcher_service.py
```

### Run as cron (every 5 mins as keepalive)
```bash
# OpenClaw cron job — restarts if crashed
every 5 mins → check if watcher is running → start if not
```

### Or systemd service
```bash
systemctl enable tradedesk-watcher
systemctl start tradedesk-watcher
```

---

## Phase 2 — True WebSocket Streaming

Upgrade poll engine to connect directly to TradingView WebSocket:
- `wss://data.tradingview.com/socket.io/websocket`
- Subscribe to real-time quote stream
- Sub-second latency
- Better for scalping setups

---

## Folder Structure

```
agent-trader/
├── scripts/                  # analysis agents (existing)
├── watcher/                  # watcher service — self-contained
│   ├── config/
│   │   └── settings.json     # all watcher config
│   ├── service.py            # main asyncio loop
│   ├── alerts.py             # alert conditions + cooldown logic
│   ├── notifier.py           # Telegram sender
│   ├── trailing_stop.py      # trailing stop engine
│   └── market_hours.py       # Abu Dhabi session detection
├── data/                     # shared runtime data
│   ├── positions.json        # YOUR positions (user editable)
│   └── watcher_state.json    # alert history (auto-managed)
└── skills/watcher/SKILL.md   # documentation
```

## Files to Build

| File | Purpose |
|------|---------|
| `watcher/service.py` | Main asyncio loop |
| `watcher/alerts.py` | Alert conditions + cooldown |
| `watcher/notifier.py` | Telegram alert sender |
| `watcher/trailing_stop.py` | Trailing stop engine |
| `watcher/market_hours.py` | Abu Dhabi session detection |
| `watcher/config/settings.json` | All config |
| `data/positions.json` | Position config (user editable) |
| `data/watcher_state.json` | Alert state (auto-managed) |
| `skills/watcher/SKILL.md` | Documentation |

---

## Decisions Locked ✅

| Decision | Choice |
|----------|--------|
| Language | Python + asyncio |
| Periodic updates | Every 30 mins during market hours |
| Watchlist alerts | Positions + watchlist breakouts |
| Auto scan at open | Yes — 5:30 PM Abu Dhabi daily |
| Trailing stops | Yes — trail by % |
| Portfolio loss alert | $1,000 threshold |
| Config location | Inside `watcher/config/` |
| Runtime data | `data/` (shared with other scripts) |

---

## Nice to Have (Future)

- Trailing stop support
- Price target ladder (alert at 50%, 75%, 100% of target)
- Watchlist scanner alert (e.g. "MRVL just broke above $100")
- Pre-market gap alert (e.g. any watchlist stock gapping >3%)
- Earnings countdown alert (e.g. "MU earnings in 3 days")

---

## Point 2 — Bidirectional Communication

### Overview
Each watcher is independently addressable. The main agent can query or command any watcher by ticker name at any time — without interrupting the price watching loop.

### Watcher → Agent (push events)
Watcher proactively notifies the main agent:
- Stop hit / target hit → instant alert
- Setup detected (VWAP cross, breakout, etc.)
- Periodic update every 30 mins during market hours
- Any significant price move

### Agent → Watcher (on-demand commands)

| Command | Action |
|---------|--------|
| `status` | Return current price, P&L, VWAP, stop distance |
| `stop` | Shut down this watcher cleanly |
| `update stop=X target=Y` | Update levels without restarting |
| `pause 30` | Silence alerts for 30 mins |
| `resume` | Re-enable alerts |
| `history` | Return last 10 price ticks |

### Status Response Format
When agent asks "how is MU watcher doing?":
```
👁️ MU Watcher — Active
Price: $363.44 | Avg: $358.45
P&L: +$791 (+1.4%)
VWAP: $361.20 | Status: ABOVE ✅
Stop: $348 (4.3% away — safe)
Target: $382 (5.1% away)
Running: 47 mins | Last alert: none
```

### Key Requirement
> Each watcher runs independently. Main agent knows which watcher handles which ticker. Commands are non-blocking — watcher handles the command and immediately resumes watching.

### Watcher Registry
Main agent maintains a registry of active watchers:
```json
{
  "watchers": {
    "GLD": { "pid": 12345, "started": "2026-03-27T17:30:00", "status": "active" },
    "MU":  { "pid": 12346, "started": "2026-03-27T17:36:00", "status": "active" }
  }
}
```

---

## Point 3 — Intelligence Layer

### Overview
Each watcher is not just a price ticker — it's a mini-analyst running 24/7 on one stock. It sees what you'd see staring at the chart and alerts you at the important moments.

### 3.1 Real-time Setup Detection
As each new 1m bar closes, watcher analyzes:
- VWAP position + distance
- RSI zone (oversold/overbought/neutral)
- MACD crossover on 1m/5m
- Volume vs average

Alerts when a setup forms:
```
📐 MU — VWAP Bounce Setup
Price: $363.44 | VWAP: $361.20
RSI: 38 (oversold zone)
Entry: $361.50 | Stop: $359.80 | Target: $366.00
R:R: 2.4 | Volume: 1.8x avg ✅
```

### 3.2 Position Context Awareness
Watcher knows your trade:
- Live P&L calculated every tick
- Distance to stop (% and $)
- Distance to target (% and $)
- Time in trade

Alerts on key thresholds:
- Stop within 1% → warning
- Profit hits 50% of target → notify
- Profit hits 100% of target → celebrate + suggest trim

### 3.3 Pattern Recognition (Live Bars)
As bars form, watcher detects:
- Bull/bear flag forming on 5m
- Consolidation near VWAP
- Higher highs / lower lows trend
- Inside bar (coiling)

```
🚩 MU — Bull Flag Forming (5m)
Flagpole: +2.1% | Consolidation: 4 bars
Breakout level: $365.50
Watch for volume confirmation
```

### 3.4 Risk Alerts
Unusual activity detection:
- Volume spike >3x avg → "something happening, check news"
- Flash drop >1% in 1 min → "flash move — check catalyst"
- Price gap between bars → "gap detected"
- Consecutive red bars (5+) → "sustained selling pressure"

### 3.5 Intelligence Source
Watcher calls back to Python agents for deep analysis when needed:
- On setup detection → call `vwap_watcher.py` for confirmation
- On unusual volume → call `news_fetcher.py` for catalyst
- On pattern → call `pattern_finder.py` for full analysis

### Key Requirement
> The watcher runs lightweight Go logic for real-time checks every tick. For deeper analysis it delegates to Python agents. Intelligence is layered — fast checks in Go, deep analysis in Python.

---

## Point 4 — Lifecycle Management

### Overview
Defines how a watcher lives from start to finish — including crashes, reboots, token expiry, and end of day.

### 4.1 Starting a Watcher
Via Telegram:
```
"watch MU avg=358.45 stop=348 target=382"
```
Watcher starts and confirms:
```
👁️ Watching MU $363.44 | Avg $358.45 | P&L +$791
Stop: $348 | Target: $382
```
Registered in watcher registry immediately.

### 4.2 Watcher Persistence
- **Crash** → auto-restart, resume watching
- **Machine reboot** → auto-restart on boot
- **TV token expiry** → refresh token and reconnect automatically
- State preserved across restarts (stop/target/avg price)

### 4.3 Stopping a Watcher
Via Telegram:
```
"stop watching MU"
```
- Graceful shutdown
- Sends final summary before closing:
```
👋 MU Watcher stopped
Final P&L: +$791 (+1.4%) | Time watched: 1h 23m
```
- Removed from registry

### 4.4 End of Day (Midnight Abu Dhabi)
- Market closes → watcher pauses automatically
- Sends EOD summary:
```
📊 EOD Summary — MU
Close: $363.44 | P&L today: +$791
Key levels: VWAP $361.20 | Support $358 | Resistance $366
Overnight plan: Hold. Watch $358 support at open.
```
- Resumes at pre-market (12 PM Abu Dhabi) next day

### 4.5 List All Watchers
Via Telegram: `"show watchers"`
```
👁️ Active Watchers (2)
• GLD | $408.20 | P&L +$6,600 | 2h 10m
• MU  | $363.44 | P&L +$791  | 1h 23m
```

---

## Architecture Decision — Go vs Python

### Go owns (real-time, live market)
- TradingView WebSocket connection
- Live VWAP calculation on ticks
- Live RSI on forming bars
- Volume analysis (avg, spikes)
- Pattern detection on live bars
- Price alerts (stop/target/VWAP cross)
- Watcher process management

### Python owns (on-demand, analysis)
- News fetching (yfinance, BeautifulSoup)
- Fundamentals / earnings (EDGAR)
- Scanner (yfinance bulk download)
- Orchestrator / intent routing
- Deep pattern analysis
- Economic calendar

### Communication
- Go → Python: subprocess call, JSON response
- Python → Go: command via watcher registry (status, stop, update)

### Rationale
- tvdatafeed, yfinance, pandas = Python-only libraries, no Go equivalent
- Real-time tick processing = Go's strength
- No full rewrite — Python scripts stay as-is
- Go watcher is self-contained; delegates deep analysis to Python when needed

---

## Architecture — Technical Decisions

### System Diagram
```
Telegram → Main Agent (Python/OpenClaw)
               │
               │ "watch MU avg=358.45 stop=348 target=382"
               ▼
       Watcher Manager (Go)          ← always running
       ├── Owns registry.json
       ├── Spawns/kills watchers
       ├── Health checks (restart on crash)
       └── Unix socket: /tmp/watcher_manager.sock
               │
       ┌───────┼────────┐
  GLD Watcher  MU Watcher  MRVL Watcher
  (Go process) (Go process) (Go process)
  /tmp/watcher_GLD.sock
  /tmp/watcher_MU.sock
               │
               ▼
         FastAPI (Python) — localhost:8000
         (deep analysis on demand)
               │
               ▼
         Telegram → You
```

### Decision Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| IPC | Unix sockets | Fast, no deps, same machine |
| Registry | JSON file | Simple, human readable |
| Python calls | FastAPI | Persistent, reuses existing scripts |
| Lifecycle owner | Watcher Manager (Go) | Single control point, health checks |
| Real-time metrics | Go (native) | VWAP, RSI, MACD, ATR — sub-second |
| Deep analysis | Python/FastAPI | News, fundamentals, patterns |

### IPC — Unix Sockets
```
/tmp/watcher_manager.sock   ← agent talks here (start/stop/list)
/tmp/watcher_GLD.sock       ← per-ticker commands (status/pause/update)
/tmp/watcher_MU.sock
```

### Registry — JSON file
```json
// watcher/data/registry.json
{
  "watchers": {
    "GLD": {
      "pid": 12345,
      "socket": "/tmp/watcher_GLD.sock",
      "started": "2026-03-27T17:30:00",
      "avg": 381.80, "stop": 390.00, "target": 420.00
    },
    "MU": {
      "pid": 12346,
      "socket": "/tmp/watcher_MU.sock",
      "started": "2026-03-27T17:36:00",
      "avg": 358.45, "stop": 348.00, "target": 382.00
    }
  }
}
```

### FastAPI — Python Analysis Server
```
GET /analyze/{ticker}   → technical_analyst.py
GET /news/{ticker}      → news_fetcher.py
GET /vwap/{ticker}      → vwap_watcher.py
GET /pattern/{ticker}   → pattern_finder.py
GET /earnings/{ticker}  → earnings_expert.py
```

### Watcher Manager — Responsibilities
- Start/stop individual watcher processes
- Health check every 30s → auto-restart on crash
- Single Unix socket for all agent commands
- Owns and updates registry.json
- Token refresh coordination

### Go Metrics (native, every tick)
- VWAP + bands (1σ, 2σ)
- RSI (14)
- EMA (9, 20)
- MACD
- Volume average + spike detection
- ATR (14)
- Stop/target distance
- Live P&L

---

## Architecture — Revision 2 (post Claude Code review)

### Key Change: Process-per-ticker → Goroutines-per-ticker

Single Go binary with goroutine-per-ticker. Simpler, same isolation, no PID/socket/registry complexity.

```
tradedesk-watcher (single Go binary)
├── goroutine: GLD watcher  (TV WebSocket + metrics + alerts)
├── goroutine: MU watcher
├── goroutine: MRVL watcher
├── goroutine: supervisor   (health checks, restart on panic)
└── HTTP server over Unix socket: /run/tradedesk/manager.sock
```

### IPC Protocol — HTTP over Unix Socket
Single socket, standard HTTP JSON protocol. Debuggable with curl:
```bash
curl --unix-socket /run/tradedesk/manager.sock http://localhost/status
curl --unix-socket /run/tradedesk/manager.sock http://localhost/watch -d '{"ticker":"MU","avg":358.45,"stop":348,"target":382}'
curl --unix-socket /run/tradedesk/manager.sock http://localhost/stop/MU
```

Python agent uses `requests_unixsocket` — talks to ONE endpoint only.

### Manager Endpoints
| Method | Path | Action |
|--------|------|--------|
| POST | `/watch` | Start watching a ticker |
| DELETE | `/watch/{ticker}` | Stop watching |
| GET | `/status` | All watchers status |
| GET | `/status/{ticker}` | Single ticker status |
| GET | `/health` | Uptime, watcher count, last poll time |
| POST | `/update/{ticker}` | Update stop/target levels |
| POST | `/pause/{ticker}` | Pause alerts N minutes |

### Socket Location
```
/run/tradedesk/manager.sock   ← not /tmp/ (safe from OS cleanup)
```

### VWAP Calculation
- On watcher startup: fetch full day bars since market open
- Compute VWAP from all bars (typical_price × volume / total_volume)
- Maintain running VWAP in memory, update each new bar
- Persist running VWAP sum every 5 mins (survive short crashes)

### Crash Recovery
- Goroutine panics caught with `recover()` — supervisor restarts goroutine
- On binary restart: read state file, reconcile, resume watching
- Socket cleanup on startup: unlink stale socket files before binding

### File Writes — Atomic
All JSON state files use write-to-temp + rename:
```go
os.WriteFile("registry.tmp", data, 0600)
os.Rename("registry.tmp", "registry.json")
```

### Short Position Support
```json
{
  "ticker": "MU",
  "direction": "long",   // or "short" — inverts stop/target logic
  "avg": 358.45,
  "stop": 348.00,
  "target": 382.00
}
```

### Dead Man's Switch
Cron job every 5 mins during market hours:
- Ping `/health` on manager socket
- If no response → send Telegram alert: "⚠️ Watcher may be down"
- Don't rely on watcher to report its own death

### Alert Storm Protection
- Per-type cooldown: 15 mins per alert type per ticker
- Global rate limit: max 5 alerts per minute across all tickers
- Market open grace period: 2 min silence after 5:30 PM Abu Dhabi

### Changes from Revision 1
| Item | Before | After |
|------|--------|-------|
| Architecture | Process-per-ticker | Goroutine-per-ticker |
| IPC protocol | Unspecified Unix socket | HTTP over Unix socket |
| Socket location | /tmp/ | /run/tradedesk/ |
| VWAP source | 5 bars | Full day bars + running sum |
| File writes | Direct | Atomic (tmp + rename) |
| Short positions | Not supported | `direction` field |
| Dead man's switch | Not specified | Cron health check |
| Language header | Python + asyncio | Go + Python |
