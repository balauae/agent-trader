# TradeDesk Watcher — Implementation Plan

**Based on:** `watcher/SPEC.md` (Revision 2 — goroutine-per-ticker architecture)
**Starting point:** `watcher/poc/main.go` (working TV WebSocket POC)
**Created:** 2026-03-27

---

## Build Order Summary

```
Phase 1: Core Go binary — connects to TV, watches one ticker, prints alerts to stdout
Phase 2: Multi-ticker — goroutine-per-ticker, supervisor, shared state
Phase 3: Alert engine — all alert types, cooldown, storm protection
Phase 4: Notifier — Telegram integration via OpenClaw message tool
Phase 5: Manager API — HTTP-over-Unix-socket, full command set
Phase 6: Python bridge — FastAPI analysis server, Go→Python delegation
Phase 7: Lifecycle — systemd, dead man's switch, crash recovery
Phase 8: Intelligence — setup detection, pattern recognition, risk alerts
```

---

## Phase 1: Core Single-Ticker Watcher

**Goal:** Single Go binary that connects to TradingView WebSocket, receives real-time quotes + OHLCV bars for one ticker, computes VWAP/RSI, and evaluates stop/target conditions. Output to stdout only.

**Duration:** ~45 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/go.mod` | Go module definition (`github.com/bala/tradedesk-watcher`) |
| `watcher/cmd/watcher/main.go` | Entrypoint — arg parsing, config load, run loop |
| `watcher/internal/tvconn/conn.go` | TradingView WebSocket connection manager (extracted from POC) |
| `watcher/internal/tvconn/protocol.go` | TV message framing: `wrapMsg`, `sendMsg`, `parseMessages` |
| `watcher/internal/tvconn/types.go` | Quote, Bar, SeriesUpdate structs |
| `watcher/internal/metrics/vwap.go` | Running VWAP calculator (typical_price * volume / total_volume) |
| `watcher/internal/metrics/rsi.go` | RSI(14) on 1m bars — Wilder's smoothing |
| `watcher/internal/metrics/ema.go` | EMA(9), EMA(20) — used by MACD and standalone |
| `watcher/internal/metrics/macd.go` | MACD(12,26,9) — signal line + histogram |
| `watcher/internal/metrics/volume.go` | Rolling volume average, spike detection (>2x, >3x) |
| `watcher/internal/metrics/atr.go` | ATR(14) — true range smoothed |
| `watcher/internal/position/position.go` | Position struct: ticker, shares, avg, stop, target, direction |
| `watcher/internal/position/loader.go` | Load/watch `data/positions.json` |
| `watcher/internal/market/hours.go` | Abu Dhabi market hours: session detection, poll interval logic |
| `watcher/internal/config/config.go` | Load `watcher/config/settings.json`, env overrides |
| `watcher/config/settings.json` | Default settings (poll interval, cooldowns, socket path) |
| `data/positions.json` | Initial position config (GLD + MU from spec) |

### Build Order

1. `go.mod` + `go get github.com/gorilla/websocket`
2. `tvconn/protocol.go` — pure functions, test with unit tests
3. `tvconn/types.go` — struct definitions
4. `tvconn/conn.go` — extract POC connection logic into `Connect()`, `Subscribe()`, `ReadLoop()` methods
5. `metrics/vwap.go` — `NewVWAP()`, `Update(typicalPrice, volume)`, `Value()` — stateful, testable
6. `metrics/rsi.go` — `NewRSI(period)`, `Update(close)`, `Value()` — Wilder's method
7. `metrics/ema.go` — `NewEMA(period)`, `Update(value)`, `Value()`
8. `metrics/macd.go` — wraps two EMAs + signal EMA
9. `metrics/volume.go` — `NewVolumeTracker(window)`, `Update(vol)`, `Average()`, `IsSpike(multiplier)`
10. `metrics/atr.go` — `NewATR(period)`, `Update(high, low, close)`, `Value()`
11. `market/hours.go` — `CurrentSession()` returns `PreMarket|Market|AfterHours|Overnight`
12. `position/position.go` + `position/loader.go` — JSON loader
13. `config/config.go` — settings loader
14. `cmd/watcher/main.go` — wire everything, single ticker, stdout output

### Testing

```bash
# Unit tests for each metrics package
go test ./internal/metrics/...

# Unit test for protocol parsing
go test ./internal/tvconn/...

# Unit test for market hours (mock time)
go test ./internal/market/...

# Manual integration test — connect to TV, watch MU for 60s
go run ./cmd/watcher -ticker MU -timeout 60s
```

### Key Implementation Details

**VWAP:** On startup, fetch bars since market open (request 390 1m bars via `create_series`). Compute initial VWAP from historical bars, then maintain running numerator/denominator on each new bar. Persist running sums to `data/watcher_state.json` every 5 minutes.

**TV Connection (from POC):**
- Auth: `set_auth_token` with token from `.secrets/tradingview.json`
- Quote session: `quote_create_session` → `quote_add_symbols` → `qsd` messages
- Chart session: `chart_create_session` → `resolve_symbol` → `create_series` → `du` messages
- Heartbeat: respond to `~h~` messages immediately
- Exchange prefix: need to map ticker → exchange (NASDAQ, NYSE, AMEX). Start with hardcoded map, later use TV's symbol search.

**RSI Wilder's Method:**
```
avg_gain = prev_avg_gain * 13/14 + current_gain * 1/14
avg_loss = prev_avg_loss * 13/14 + current_loss * 1/14
RS = avg_gain / avg_loss
RSI = 100 - (100 / (1 + RS))
```
First 14 bars use simple average to seed.

---

## Phase 2: Multi-Ticker Goroutine Architecture

**Goal:** Single binary managing N goroutines — one per ticker. Supervisor goroutine monitors health and restarts panicked watchers. Shared state via channels.

**Duration:** ~30 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/internal/engine/watcher.go` | Single-ticker watcher goroutine: connect, subscribe, process loop |
| `watcher/internal/engine/supervisor.go` | Supervisor: spawn watchers, health check, restart on panic |
| `watcher/internal/engine/registry.go` | In-memory registry + JSON persistence (`data/registry.json`) |
| `watcher/internal/engine/types.go` | WatcherState, WatcherCommand, WatcherEvent enums |
| `watcher/internal/state/state.go` | Atomic JSON state file (write-tmp + rename pattern) |

### Architecture

```
main.go
  └── supervisor.Run()
        ├── for each position in positions.json:
        │     └── go watcher.Run(ctx, position, eventCh)
        ├── go healthChecker(30s interval)
        └── select on eventCh for alerts
```

**Watcher goroutine lifecycle:**
```go
func (w *Watcher) Run(ctx context.Context, pos Position, events chan<- Event) {
    defer func() {
        if r := recover(); r != nil {
            events <- Event{Type: Panic, Ticker: pos.Ticker, Error: r}
        }
    }()
    conn := tvconn.Connect(authToken)
    conn.Subscribe(pos.Ticker)
    for {
        select {
        case <-ctx.Done():
            return
        case msg := <-conn.Messages():
            w.processMessage(msg)
            if alert := w.checkAlerts(); alert != nil {
                events <- *alert
            }
        }
    }
}
```

**Supervisor restart logic:**
- On `Panic` event → wait 5s → respawn goroutine
- Max 3 restarts per ticker per hour → alert user, stop retrying
- On startup: load `registry.json`, reconcile with `positions.json`

**State persistence:**
- `state.WriteAtomic(path, data)` — writes to `.tmp` then `os.Rename`
- All JSON writes go through this function
- Used for: `registry.json`, `watcher_state.json`

### Testing

```bash
# Unit test supervisor restart logic
go test ./internal/engine/ -run TestSupervisorRestart

# Integration: start 2 tickers, verify both receive data
go run ./cmd/watcher -config data/positions.json -timeout 120s
```

---

## Phase 3: Alert Engine

**Goal:** Full alert condition evaluation with cooldown, rate limiting, and storm protection.

**Duration:** ~30 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/internal/alerts/conditions.go` | All alert condition checks (stop hit, target hit, VWAP cross, etc.) |
| `watcher/internal/alerts/cooldown.go` | Per-type-per-ticker cooldown tracker |
| `watcher/internal/alerts/ratelimit.go` | Global rate limiter (max 5/min across all tickers) |
| `watcher/internal/alerts/formatter.go` | Format alert messages (Telegram markdown) |
| `watcher/internal/alerts/types.go` | AlertType enum, Alert struct, Severity levels |
| `data/watcher_state.json` | Persisted alert history (auto-created) |

### Alert Conditions (from spec)

```go
// Critical — instant, bypass cooldown for first occurrence
func CheckStopHit(price, stop float64, dir Direction) bool
func CheckTargetHit(price, target float64, dir Direction) bool
func CheckFlashCrash(prices []TimedPrice, thresholdPct float64, windowMins int) bool

// Warning — respect cooldown
func CheckNearStop(price, stop float64, thresholdPct float64) bool
func CheckVWAPBreak(price, prevPrice, vwap float64) bool      // cross below
func CheckVWAPReclaim(price, prevPrice, vwap float64) bool     // cross above
func CheckHighVolumeSell(volume, avgVolume float64, isRedCandle bool) bool

// Direction-aware: short positions invert stop/target logic
```

### Cooldown Logic

```go
type CooldownTracker struct {
    mu     sync.RWMutex
    alerts map[string]time.Time  // key: "MU_stop_warning"
}

func (c *CooldownTracker) CanAlert(ticker, alertType string, cooldown time.Duration) bool
func (c *CooldownTracker) Record(ticker, alertType string)
func (c *CooldownTracker) LoadState(path string) error
func (c *CooldownTracker) SaveState(path string) error
```

### Storm Protection

- Per-type cooldown: 15 min default (configurable in `settings.json`)
- Global rate limit: token bucket — 5 tokens, refill 1/12s
- Market open grace: suppress non-critical alerts for 2 min after 5:30 PM Abu Dhabi
- Critical alerts (stop/target hit) bypass cooldown on FIRST trigger, then 15 min cooldown

### Message Formatting

```go
// Position update line
func FormatPositionLine(pos Position, price float64) string
// Returns: "🟢 GLD  $408.20 (+$26.40) | P&L +$6,600"

// Full snapshot
func FormatSnapshot(positions []PositionStatus, timestamp time.Time) string

// Individual alert
func FormatAlert(alert Alert) string
```

### Testing

```bash
# Unit tests — all conditions with edge cases
go test ./internal/alerts/ -v

# Key test cases:
# - Stop hit at exact price
# - Stop hit for short position (price ABOVE stop)
# - VWAP cross detection (both directions)
# - Cooldown respects timer
# - Rate limiter blocks 6th alert in 1 minute
# - Market open grace period suppression
```

---

## Phase 4: Telegram Notifier

**Goal:** Send formatted alerts to Telegram chat. Uses OpenClaw message tool (existing infra) or direct Telegram Bot API.

**Duration:** ~20 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/internal/notifier/telegram.go` | Telegram Bot API sender (HTTP POST to `api.telegram.org`) |
| `watcher/internal/notifier/notifier.go` | Notifier interface + dispatcher (routes alerts to Telegram) |
| `watcher/internal/notifier/queue.go` | Buffered send queue — batch nearby alerts, retry on failure |

### Implementation

```go
type Notifier interface {
    Send(ctx context.Context, msg string) error
    SendAlert(ctx context.Context, alert Alert) error
    SendSnapshot(ctx context.Context, snapshot Snapshot) error
}

type TelegramNotifier struct {
    botToken string
    chatID   string
    client   *http.Client
    queue    chan string
}
```

**Config:** Bot token + chat ID stored in `.secrets/telegram.json` (or env vars `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)

**Queue behavior:**
- Buffer up to 10 messages
- Batch alerts within 2s window into single message
- Retry failed sends 3x with exponential backoff (1s, 2s, 4s)
- Drop after 3 failures, log error

### Periodic Updates (cron-like goroutine)

```go
func (n *Notifier) StartScheduler(ctx context.Context, engine *Engine) {
    // Every 30 mins during market hours → send P&L snapshot
    // 5:30 PM Abu Dhabi → market open summary
    // Midnight Abu Dhabi → EOD recap
}
```

### Testing

```bash
# Unit test: message formatting
go test ./internal/notifier/ -run TestFormat

# Integration: send test message to Telegram
go run ./cmd/watcher -test-telegram

# Verify: queue batching, retry logic
go test ./internal/notifier/ -run TestQueue
```

---

## Phase 5: Manager HTTP API

**Goal:** HTTP-over-Unix-socket server for bidirectional communication. Python agent (or curl) can start/stop/query watchers.

**Duration:** ~30 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/internal/api/server.go` | `net/http` server listening on Unix socket |
| `watcher/internal/api/handlers.go` | Route handlers for all endpoints |
| `watcher/internal/api/middleware.go` | Request logging, panic recovery |
| `watcher/internal/api/types.go` | Request/response JSON structs |

### Endpoints (from spec)

```go
mux.HandleFunc("POST /watch", h.StartWatcher)          // Start watching a ticker
mux.HandleFunc("DELETE /watch/{ticker}", h.StopWatcher) // Stop watching
mux.HandleFunc("GET /status", h.AllStatus)              // All watchers status
mux.HandleFunc("GET /status/{ticker}", h.TickerStatus)  // Single ticker status
mux.HandleFunc("GET /health", h.Health)                 // Uptime, count, last poll
mux.HandleFunc("POST /update/{ticker}", h.UpdateLevels) // Update stop/target
mux.HandleFunc("POST /pause/{ticker}", h.PauseAlerts)   // Pause alerts N minutes
```

### Socket Setup

```go
socketPath := "/run/tradedesk/manager.sock"

// Cleanup stale socket on startup
os.Remove(socketPath)
os.MkdirAll(filepath.Dir(socketPath), 0755)

listener, _ := net.Listen("unix", socketPath)
os.Chmod(socketPath, 0660)
http.Serve(listener, mux)
```

### Status Response (from spec)

```json
{
  "ticker": "MU",
  "status": "active",
  "price": 363.44,
  "avg_price": 358.45,
  "pnl_dollars": 791.0,
  "pnl_percent": 1.39,
  "vwap": 361.20,
  "vwap_position": "above",
  "rsi": 52.3,
  "stop": 348.0,
  "stop_distance_pct": 4.3,
  "target": 382.0,
  "target_distance_pct": 5.1,
  "running_since": "2026-03-27T17:36:00Z",
  "last_alert": null
}
```

### Testing

```bash
# Unit test: handlers with httptest
go test ./internal/api/ -v

# Integration: start server, curl commands
curl --unix-socket /run/tradedesk/manager.sock http://localhost/health
curl --unix-socket /run/tradedesk/manager.sock http://localhost/status
curl --unix-socket /run/tradedesk/manager.sock http://localhost/watch \
  -d '{"ticker":"MRVL","avg":108.50,"stop":102,"target":118}'
curl --unix-socket /run/tradedesk/manager.sock -X DELETE http://localhost/watch/MRVL
```

---

## Phase 6: Python Analysis Bridge

**Goal:** FastAPI server wrapping existing Python analysis scripts. Go watcher calls this for deep analysis on setup detection.

**Duration:** ~30 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/bridge/server.py` | FastAPI app wrapping existing scripts |
| `watcher/bridge/requirements.txt` | FastAPI, uvicorn |
| `watcher/internal/bridge/client.go` | Go HTTP client to call Python bridge |

### FastAPI Endpoints (wrapping existing scripts)

```python
# server.py
from fastapi import FastAPI
import subprocess, json

app = FastAPI()

@app.get("/analyze/{ticker}")
async def analyze(ticker: str):
    """Calls scripts/technical_analyst.py"""
    result = subprocess.run(
        ["python", "../scripts/technical_analyst.py", ticker],
        capture_output=True, text=True
    )
    return {"result": json.loads(result.stdout)}

@app.get("/news/{ticker}")
async def news(ticker: str):
    """Calls scripts/news_fetcher.py"""

@app.get("/vwap/{ticker}")
async def vwap(ticker: str):
    """Calls scripts/vwap_watcher.py"""

@app.get("/pattern/{ticker}")
async def pattern(ticker: str):
    """Calls scripts/pattern_finder.py"""

@app.get("/earnings/{ticker}")
async def earnings(ticker: str):
    """Calls scripts/earnings_expert.py"""
```

### Go Bridge Client

```go
type BridgeClient struct {
    baseURL string  // "http://localhost:8000"
    client  *http.Client
}

func (b *BridgeClient) Analyze(ticker string) (*AnalysisResult, error)
func (b *BridgeClient) FetchNews(ticker string) (*NewsResult, error)
func (b *BridgeClient) CheckPattern(ticker string) (*PatternResult, error)
```

**Trigger rules (in Go watcher):**
- VWAP bounce + RSI oversold → call `/analyze/{ticker}` for confirmation
- Volume spike >3x → call `/news/{ticker}` for catalyst
- Pattern detected → call `/pattern/{ticker}` for full analysis
- Calls are async — don't block the price watching loop

### Testing

```bash
# Start Python bridge
cd watcher/bridge && uvicorn server:app --port 8000

# Test endpoints
curl http://localhost:8000/analyze/MU
curl http://localhost:8000/news/MU

# Go bridge client unit test with httptest mock
go test ./internal/bridge/ -v
```

---

## Phase 7: Lifecycle & Deployment

**Goal:** Production-grade reliability — systemd service, crash recovery, dead man's switch, token refresh.

**Duration:** ~30 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/deploy/tradedesk-watcher.service` | systemd unit file for Go watcher |
| `watcher/deploy/tradedesk-bridge.service` | systemd unit file for Python bridge |
| `watcher/deploy/healthcheck.sh` | Dead man's switch cron script |
| `watcher/deploy/install.sh` | One-shot install: build, create dirs, install services |
| `watcher/internal/auth/token.go` | TV token loader + refresh detection |
| `watcher/Makefile` | Build, test, install, run targets |

### systemd Service

```ini
# tradedesk-watcher.service
[Unit]
Description=TradeDesk Watcher Service
After=network.target

[Service]
Type=simple
ExecStart=/home/bala/dev/apps/agent-trader/watcher/bin/watcher
WorkingDirectory=/home/bala/dev/apps/agent-trader
Restart=on-failure
RestartSec=10
Environment=WATCHER_SOCKET=/run/tradedesk/manager.sock
RuntimeDirectory=tradedesk

[Install]
WantedBy=multi-user.target
```

### Dead Man's Switch

```bash
#!/bin/bash
# healthcheck.sh — runs via cron every 5 mins during market hours
SOCKET="/run/tradedesk/manager.sock"
RESPONSE=$(curl -s --unix-socket "$SOCKET" http://localhost/health 2>/dev/null)
if [ $? -ne 0 ]; then
    # Send alert via direct Telegram API call
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "text=⚠️ TradeDesk Watcher may be down — health check failed"
fi
```

### Crash Recovery

On binary restart:
1. Load `data/watcher_state.json` — restore last prices, VWAP running sums, alert cooldowns
2. Load `data/positions.json` — get current positions
3. Clean up stale socket: `os.Remove(socketPath)` before binding
4. Spawn watcher goroutines for all active positions
5. Send Telegram: "🔄 Watcher restarted — resuming all positions"

### Token Refresh

```go
// Watch .secrets/tradingview.json for changes (fsnotify)
// On change → signal all watchers to reconnect with new token
// If token read fails → retry 3x, then alert user
```

### Makefile

```makefile
.PHONY: build test run install

build:
	go build -o bin/watcher ./cmd/watcher

test:
	go test ./... -v -race

run: build
	./bin/watcher

install: build
	sudo cp deploy/tradedesk-watcher.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable tradedesk-watcher
	sudo systemctl start tradedesk-watcher

health:
	curl -s --unix-socket /run/tradedesk/manager.sock http://localhost/health | jq .

status:
	curl -s --unix-socket /run/tradedesk/manager.sock http://localhost/status | jq .
```

### Testing

```bash
# Build and run
make build && make run

# Full test suite with race detector
make test

# Test crash recovery: kill -9 watcher, verify restart + state restore
# Test token refresh: modify .secrets/tradingview.json, verify reconnect
```

---

## Phase 8: Intelligence Layer

**Goal:** Real-time setup detection, pattern recognition, and risk alerts. This is the "mini-analyst" layer.

**Duration:** ~45 mins

### Files to Create

| File | Purpose |
|------|---------|
| `watcher/internal/intel/setups.go` | Setup detection: VWAP bounce, breakout, consolidation |
| `watcher/internal/intel/patterns.go` | Live pattern recognition: bull/bear flag, inside bar |
| `watcher/internal/intel/risk.go` | Risk alerts: volume spike, flash move, consecutive reds |
| `watcher/internal/intel/context.go` | Position context: P&L thresholds, target ladder |

### Setup Detection (runs on every new bar)

```go
type SetupDetector struct {
    bars    []Bar           // rolling window of recent bars
    metrics *MetricsSuite   // VWAP, RSI, EMA, MACD, volume
}

func (s *SetupDetector) Evaluate() []Setup {
    var setups []Setup

    // VWAP Bounce: price near VWAP + RSI oversold + volume rising
    if s.isNearVWAP(0.3) && s.metrics.RSI.Value() < 35 && s.volumeRising() {
        setups = append(setups, VWAPBounceSetup{...})
    }

    // Breakout: price breaks above resistance with volume
    // Consolidation: 4+ bars with <0.5% range near VWAP
    // MACD crossover: signal line cross with momentum confirmation

    return setups
}
```

### Pattern Recognition

```go
func DetectBullFlag(bars []Bar) *Pattern    // Flagpole + consolidation
func DetectBearFlag(bars []Bar) *Pattern
func DetectInsideBar(bars []Bar) *Pattern   // Current bar inside previous
func DetectHigherHighs(bars []Bar) bool     // Trend detection
func DetectLowerLows(bars []Bar) bool
```

### Risk Alerts

```go
func CheckVolumeSpike(currentVol, avgVol float64, multiplier float64) bool  // >3x
func CheckFlashMove(bars []Bar, thresholdPct float64, windowBars int) bool  // >1% in 1 bar
func CheckGap(prevClose, currentOpen float64, thresholdPct float64) bool
func CheckConsecutiveRed(bars []Bar, count int) bool                        // 5+ red bars
```

### Position Context Awareness

```go
func CheckTargetLadder(price, avg, target float64) *Alert {
    progress := (price - avg) / (target - avg)
    switch {
    case progress >= 1.0:  // 100% of target
        return &Alert{Type: TargetHit, Msg: "🎯 Target reached — consider trimming"}
    case progress >= 0.75: // 75% of target
        return &Alert{Type: TargetApproaching, Msg: "📈 75% to target"}
    case progress >= 0.50: // 50% of target
        return &Alert{Type: TargetHalfway, Msg: "📊 Halfway to target"}
    }
    return nil
}

func CheckPortfolioLoss(positions []PositionStatus, threshold float64) *Alert
// Aggregate P&L across all positions → alert if total loss > $1,000
```

### Testing

```bash
# Unit tests with synthetic bar data
go test ./internal/intel/ -v

# Test cases:
# - VWAP bounce setup with confirming RSI
# - Bull flag with 5-bar consolidation after 2% move
# - Volume spike 3.5x on red candle
# - 5 consecutive red bars
# - Portfolio loss exceeding $1,000 threshold
# - Target ladder at 50%, 75%, 100%
```

---

## Complete File Tree

```
agent-trader/
├── data/
│   ├── positions.json              # Phase 1 — user positions
│   ├── watcher_state.json          # Phase 3 — alert history (auto)
│   └── registry.json               # Phase 2 — watcher registry (auto)
│
├── watcher/
│   ├── SPEC.md                     # existing
│   ├── IMPLEMENTATION-PLAN.md      # this file
│   ├── go.mod                      # Phase 1
│   ├── go.sum                      # Phase 1
│   ├── Makefile                    # Phase 7
│   │
│   ├── cmd/
│   │   └── watcher/
│   │       └── main.go             # Phase 1 — entrypoint
│   │
│   ├── config/
│   │   └── settings.json           # Phase 1 — default settings
│   │
│   ├── internal/
│   │   ├── tvconn/
│   │   │   ├── conn.go             # Phase 1 — TV WebSocket manager
│   │   │   ├── protocol.go         # Phase 1 — message framing
│   │   │   └── types.go            # Phase 1 — Quote, Bar structs
│   │   │
│   │   ├── metrics/
│   │   │   ├── vwap.go             # Phase 1 — running VWAP
│   │   │   ├── rsi.go              # Phase 1 — RSI(14)
│   │   │   ├── ema.go              # Phase 1 — EMA(9, 20)
│   │   │   ├── macd.go             # Phase 1 — MACD(12,26,9)
│   │   │   ├── volume.go           # Phase 1 — volume avg + spike
│   │   │   └── atr.go              # Phase 1 — ATR(14)
│   │   │
│   │   ├── position/
│   │   │   ├── position.go         # Phase 1 — Position struct
│   │   │   └── loader.go           # Phase 1 — JSON loader
│   │   │
│   │   ├── market/
│   │   │   └── hours.go            # Phase 1 — Abu Dhabi sessions
│   │   │
│   │   ├── config/
│   │   │   └── config.go           # Phase 1 — settings loader
│   │   │
│   │   ├── engine/
│   │   │   ├── watcher.go          # Phase 2 — per-ticker goroutine
│   │   │   ├── supervisor.go       # Phase 2 — spawn/health/restart
│   │   │   ├── registry.go         # Phase 2 — in-memory + JSON
│   │   │   └── types.go            # Phase 2 — WatcherState, events
│   │   │
│   │   ├── state/
│   │   │   └── state.go            # Phase 2 — atomic JSON writes
│   │   │
│   │   ├── alerts/
│   │   │   ├── conditions.go       # Phase 3 — all alert checks
│   │   │   ├── cooldown.go         # Phase 3 — per-type cooldown
│   │   │   ├── ratelimit.go        # Phase 3 — global rate limiter
│   │   │   ├── formatter.go        # Phase 3 — Telegram message format
│   │   │   └── types.go            # Phase 3 — AlertType, Severity
│   │   │
│   │   ├── notifier/
│   │   │   ├── telegram.go         # Phase 4 — Telegram Bot API
│   │   │   ├── notifier.go         # Phase 4 — interface + dispatch
│   │   │   └── queue.go            # Phase 4 — buffered send queue
│   │   │
│   │   ├── api/
│   │   │   ├── server.go           # Phase 5 — Unix socket HTTP
│   │   │   ├── handlers.go         # Phase 5 — route handlers
│   │   │   ├── middleware.go       # Phase 5 — logging, recovery
│   │   │   └── types.go            # Phase 5 — request/response
│   │   │
│   │   ├── bridge/
│   │   │   └── client.go           # Phase 6 — Go→Python HTTP client
│   │   │
│   │   ├── auth/
│   │   │   └── token.go            # Phase 7 — TV token loader/refresh
│   │   │
│   │   └── intel/
│   │       ├── setups.go           # Phase 8 — setup detection
│   │       ├── patterns.go         # Phase 8 — pattern recognition
│   │       ├── risk.go             # Phase 8 — risk alerts
│   │       └── context.go          # Phase 8 — position context
│   │
│   ├── bridge/
│   │   ├── server.py               # Phase 6 — FastAPI wrapper
│   │   └── requirements.txt        # Phase 6 — Python deps
│   │
│   ├── deploy/
│   │   ├── tradedesk-watcher.service   # Phase 7 — systemd (Go)
│   │   ├── tradedesk-bridge.service    # Phase 7 — systemd (Python)
│   │   ├── healthcheck.sh              # Phase 7 — dead man's switch
│   │   └── install.sh                  # Phase 7 — one-shot install
│   │
│   └── poc/
│       └── main.go                 # existing — TV WebSocket POC
│
└── skills/
    └── watcher/
        └── SKILL.md                # Phase 7 — documentation
```

---

## Dependency Graph

```
Phase 1 ─── Phase 2 ─── Phase 3 ─── Phase 4
  (core)     (multi)     (alerts)    (telegram)
                │                        │
                └──── Phase 5 ───────────┘
                      (API)              │
                        │                │
                   Phase 6          Phase 7
                   (bridge)         (deploy)
                        │                │
                        └───── Phase 8 ──┘
                              (intel)
```

Phases 1→2→3→4 are strictly sequential. Phase 5 can start after Phase 2. Phase 6 can start after Phase 5. Phase 7 can start after Phase 4. Phase 8 requires all others.

---

## Go Dependencies

```
require (
    github.com/gorilla/websocket v1.5.3   // TV WebSocket (already used in POC)
)
```

No other external Go dependencies needed. Standard library covers:
- `net/http` — Unix socket HTTP server
- `encoding/json` — all serialization
- `math` — metrics calculations
- `time` — scheduling, cooldowns
- `sync` — goroutine coordination
- `context` — cancellation propagation
- `os/signal` — graceful shutdown

---

## Testing Strategy

### Unit Tests (every phase)
- Each `internal/` package has `*_test.go` files
- Use `testing.T` + table-driven tests
- Race detector on all tests: `go test -race ./...`
- Metrics tests use known OHLCV sequences with verified expected outputs

### Integration Tests (Phase 2+)
- `TestLiveConnection` — connect to TV WebSocket, receive 1 quote (skip in CI)
- `TestMultiTicker` — 2 goroutines watching different tickers
- `TestAPIEndpoints` — httptest with Unix socket server

### End-to-End (Phase 7)
- Start watcher with 2 positions
- Verify Telegram receives startup message
- Mock price movement → verify alert delivery
- Kill process → verify restart + state recovery
- Run for 30 min during market hours → verify periodic updates

### Build Tags
```go
//go:build integration
// +build integration

// Live TV connection tests — require auth token
// Run with: go test -tags=integration ./...
```

---

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| TV WebSocket disconnects | Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, max 60s) |
| TV rate limiting | Max 5 concurrent quote sessions; batch tickers if >5 |
| Token expiry mid-session | Watch `.secrets/tradingview.json` via fsnotify; reconnect on change |
| Stale VWAP after crash | Persist VWAP running sums every 5 min; re-fetch full day bars on cold start |
| Alert spam | Three-layer protection: per-type cooldown → global rate limit → market open grace |
| Goroutine leak | Context cancellation; supervisor tracks all goroutines; defer cleanup |
| Corrupt state file | Atomic writes (tmp + rename); validate JSON on load; fall back to defaults |
| Exchange prefix wrong | Maintain ticker→exchange map in config; default to NASDAQ; log warnings |

---

## Milestone Checkpoints

| After Phase | You should be able to... |
|-------------|--------------------------|
| 1 | Run `./bin/watcher -ticker MU` and see live price + VWAP + RSI in stdout |
| 2 | Run with `positions.json` containing 3 tickers, see all updating concurrently |
| 3 | See "STOP HIT" / "NEAR STOP" / "VWAP BREAK" messages in stdout when conditions trigger |
| 4 | Receive actual Telegram messages on your phone when alerts fire |
| 5 | Run `curl --unix-socket ... /status` and get JSON status of all watchers |
| 6 | Go watcher calls Python for deep analysis and includes result in Telegram alert |
| 7 | `systemctl start tradedesk-watcher` runs the service; survives reboot; dead man's switch works |
| 8 | Receive "VWAP Bounce Setup" / "Bull Flag Forming" intelligent alerts during market hours |
