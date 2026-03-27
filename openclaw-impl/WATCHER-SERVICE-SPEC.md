# TradeDesk Watcher Service — Spec

**Status:** Design phase — decisions locked  
**Priority:** High  
**Estimated build time:** 2-3 hours  
**Language:** Python (asyncio) — same stack as all agents  
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
