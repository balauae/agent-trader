# Next Action Items — Monday March 31

## Pre-Market (5:00 PM AbuDhabi)

### 1. Start services
```bash
systemctl --user start tradedesk-bridge
systemctl --user start tradedesk-watcher
```

### 2. Verify S/R levels loaded from TV
```bash
journalctl --user -u tradedesk-watcher -n 20 | grep "S/R levels"
# Expected: [watcher:GLD] loaded 4 S/R levels: [399.98 411.37 420.59 428.59]
```

### 3. Test support_resistance.py with TV source
```bash
# Should say data_source: "tv" (not "yfinance")
.venv/bin/python scripts/support_resistance.py GLD 1D 200
.venv/bin/python scripts/support_resistance.py GLD multi 1D,1h 200
```

### 4. Test bridge endpoints
```bash
curl -s http://localhost:8000/sr/GLD | python3 -m json.tool
curl -s "http://localhost:8000/sr-multi/GLD?timeframes=1D,1h" | python3 -m json.tool
```

---

## Market Open (5:30 PM AbuDhabi)

### 5. Test postmarket_summarizer (intraday data)
```bash
# Needs live session data — run after 30 min of trading
.venv/bin/python scripts/postmarket_summarizer.py GLD
# Check: data_source should be "tv"
```

### 6. Test premarket_specialist
```bash
# Run next pre-market (Mon 12 PM AbuDhabi)
.venv/bin/python scripts/premarket_specialist.py GLD
# Check: data_source field present
```

### 7. Test overnight_expert
```bash
.venv/bin/python scripts/overnight_expert.py GLD
# Check: data_source field, daily bars from TV
```

### 8. Watch for S/R proximity alert
- GLD closed Friday at $414.70
- Nearest resistance: $415.00 (0.07% away — will fire almost immediately)
- Target resistance: $420.59 (EMA9, confluent on 1D+1h)
- Expected alert: `📍 GLD approaching resistance $415.00`

---

## Things to verify

| Check | Expected |
|-------|----------|
| S/R levels loaded in watcher log | ✅ 4 levels |
| `data_source: "tv"` in S/R output | TV when market open |
| `data_source: "yfinance"` fallback | If TV slow/down |
| Proximity alert fires near $415 | Within first few bars |
| No duplicate alerts (cooldown works) | 30 min cooldown per level |
| Bridge `/sr/GLD` responds | HTTP 200 |

---

## Known issues to watch

- `premarket_specialist` extended hours data = yfinance only (TV doesn't expose pre/AH) — that's intentional
- If TV token expired → `data_source` will show `yfinance` → check `.secrets/tradingview.json`
- GLD on AMEX can take 30–60s to connect on TV WebSocket — be patient

---

## If something breaks

```bash
# Check watcher logs
journalctl --user -u tradedesk-watcher -f

# Check bridge logs  
journalctl --user -u tradedesk-bridge -f

# Restart both
cd ~/dev/apps/agent-trader/watcher && make deploy
systemctl --user restart tradedesk-bridge

# Manual S/R check via socket
curl -s --unix-socket /tmp/tradedesk-manager.sock http://localhost/status
```

---

## Pending features (build after Monday test)

- [ ] Break alerts: `🔼 GLD broke above $420.59` (proximity built, break detection not yet)
- [ ] S/R levels refresh mid-day (currently loaded once on startup)
- [ ] Periodic P&L snapshot every 30 min during market hours
- [ ] Pre-market brief automation (daily 5 PM AbuDhabi)
- [ ] `watch TICKER` auto-persist to positions.json (lost on restart)
