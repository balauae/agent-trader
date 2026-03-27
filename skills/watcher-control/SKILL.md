# Watcher Control Skill

Handle TradeDesk watcher commands from Telegram.

## Triggers
Any message matching these patterns:
- `status` / `positions` / `pnl`
- `watch <TICKER>`
- `stop <TICKER>` / `unwatch <TICKER>`
- `update <TICKER> stop=X target=Y`
- `pause <TICKER> <mins>`
- `news <TICKER>`
- `analyze <TICKER>`
- `watchers` / `how many watch`

## Socket
SOCKET=/tmp/tradedesk-manager.sock
BRIDGE=http://localhost:8000

## Commands

### status
```bash
curl -s --unix-socket $SOCKET http://localhost/status
```
Format each position:
```
📊 TradeDesk — 3:45 PM

🟢 GLD  $414.60 | P&L +$8,200 | VWAP +0.02%
🔴 MU   $355.45 | P&L   -$490 | VWAP -0.01%
🟡 NVDA $167.34 | P&L      $0 | VWAP -0.01%
─────────────────────
💰 Total: +$7,710
```

### watch TICKER
1. Call: `POST $SOCKET /watch` with `{"ticker":"X","exchange":"NASDAQ"}`
2. Also append to `watcher/data/positions.json` so it survives restarts
3. Reply: `👁️ Now watching NVDA`

### stop TICKER
1. Call: `DELETE $SOCKET /stop/TICKER`
2. Remove from `watcher/data/positions.json`
3. Reply: `✅ Stopped watching MU`

### update TICKER stop=X target=Y
```bash
curl -X POST --unix-socket $SOCKET http://localhost/update/TICKER \
  -d '{"stop": X, "target": Y}'
```
Also update positions.json.

### news TICKER
```bash
curl -s $BRIDGE/news/TICKER
```
Show top 5 headlines with publisher and time.

### analyze TICKER
```bash
curl -s $BRIDGE/analyze/TICKER
```
Show bias, price, RSI, summary.

## Error Handling
- If socket not found: "⚠️ Watcher not running. Start with: `systemctl --user start tradedesk-watcher`"
- If bridge not found: "⚠️ Bridge not running. Start with: `systemctl --user start tradedesk-bridge`"
