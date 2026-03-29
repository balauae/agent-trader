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

### 3. Test new script paths (refactored modules)
```bash
# NEW paths — these must work now
.venv/bin/python scripts/analysis/levels.py GLD 1D 200 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('levels OK:', d.get('ticker'), d.get('data_source'))"
.venv/bin/python scripts/analysis/technical.py GLD 1D 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('technical OK:', d.get('bias'), 'weinstein:', d.get('weinstein',{}).get('label'))"
.venv/bin/python scripts/analysis/fundamental.py GLD 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('fundamental OK, canslim:', d.get('canslim',{}).get('score'))"
.venv/bin/python scripts/vcp_scanner.py GLD 1D 200 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('vcp OK:', d.get('summary'))"
```

### 4. Test bridge endpoints (new paths)
```bash
curl -s http://localhost:8000/technical/GLD | python3 -c "import sys,json; d=json.load(sys.stdin); print('bridge technical OK:', d.get('bias'))"
curl -s http://localhost:8000/sr/GLD | python3 -c "import sys,json; d=json.load(sys.stdin); print('bridge SR OK:', d.get('nearest_resistance'))"
curl -s http://localhost:8000/vcp/GLD | python3 -c "import sys,json; d=json.load(sys.stdin); print('bridge VCP OK:', d.get('action'))"
```

---

## Market Open (5:30 PM AbuDhabi)

### 5. Test session scripts with live data
```bash
# Pre-market (run at 5 PM before open)
.venv/bin/python scripts/session/premarket.py GLD 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('premarket OK:', d.get('setup'), 'raschke:', d.get('raschke_fade',{}).get('setup'))"

# Opening range (run at 5:35 PM)
.venv/bin/python scripts/session/open.py GLD 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('open OK:', d.get('setup'), 'williams:', d.get('williams_breakout',{}).get('buy_level'))"

# Post-market (run after 30 min of trading)
.venv/bin/python scripts/session/postmarket.py GLD 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('postmarket OK:', d.get('data_source'))"
```

### 6. Watch for alerts
- GLD closed Friday at $414.70
- **$415.00** resistance — 0.07% away, alert fires almost immediately
- **$420.59** — EMA9/target area, confluent 1D+1h
- Expected: `📍 GLD approaching resistance $415.00`
- Expected: `📊 P&L Snapshot` every 30 min after 5:30 PM

---

## New Strategy Fields to Verify

| Script | New Field | Expected |
|--------|-----------|---------|
| `analysis/technical.py` | `weinstein` | `{stage: 2, label: "ADVANCING"}` |
| `analysis/technical.py` | `indicators.williams_r` | number between -100 and 0 |
| `session/premarket.py` | `raschke_fade` | `{setup: "fade-short/long/no-fade"}` |
| `session/open.py` | `williams_breakout` | `{buy_level: X, short_level: Y}` |
| `analysis/levels.py` | `livermore_pivot` | `{pivot_level: X, confirmed: bool}` |
| `analysis/fundamental.py` | `canslim` | `{score: "X/7", rating: "Strong/Moderate/Weak"}` |
| `vcp_scanner.py` | `vcp.vcp_detected` | true/false |

---

## SQLite Alert Log

### 7. Verify alerts are being logged
```bash
sqlite3 data/alerts.db "SELECT * FROM alerts ORDER BY ts DESC LIMIT 10;"
```

### 8. Test bridge alert endpoints
```bash
curl -s http://localhost:8000/alerts/GLD | python3 -m json.tool
curl -s http://localhost:8000/alerts | python3 -m json.tool
```

---

## Things to verify

| Check | Expected |
|-------|----------|
| New module paths work | ✅ all imports |
| `data_source: "tv"` in outputs | TV when market open |
| S/R proximity alert fires | Within first few bars |
| P&L snapshot sends to Telegram | Every 30 min |
| SQLite alert log populates | After first alert |
| No duplicate alerts | 30 min cooldown |

---

## If something breaks

```bash
# Check logs
journalctl --user -u tradedesk-watcher -f
journalctl --user -u tradedesk-bridge -f

# Restart
cd ~/dev/apps/agent-trader/watcher && make deploy
systemctl --user restart tradedesk-bridge

# Fallback — old flat scripts still exist until confirmed working
.venv/bin/python scripts/technical_analyst.py GLD  # old path still works
```

---

## After Monday test passes → cleanup

```bash
# Delete old flat scripts (only after new paths confirmed working)
cd ~/dev/apps/agent-trader/scripts
rm technical_analyst.py fundamental_analyst.py pattern_finder.py support_resistance.py \
   timeframe_analyzer.py premarket_specialist.py market_open_scalper.py \
   postmarket_summarizer.py overnight_expert.py news_fetcher.py \
   economic_calendar.py vwap_watcher.py data_fetcher.py scanner.py build_ticker_db.py
git add -A && git commit -m "Remove old flat scripts — refactor complete" && git push
```

---

## Pending features (build after Monday test)

- [ ] Break alerts: `🔼 GLD broke above $420.59` (proximity built, break detection not yet)
- [ ] S/R levels refresh mid-day (currently loaded once on startup)
- [ ] Pre-market brief automation (daily 5 PM AbuDhabi)
- [ ] `watch TICKER` auto-persist to positions.json (lost on restart)
- [ ] Reorganize orchestrator.py to use new module paths
- [ ] Update SCRIPT-EXAMPLE-USAGE.md with new paths

---

## Build: Position Sizing & Risk Calculator

Complete the trading system with the missing risk management layer.

### What to build
A position sizing calculator integrated into TradeDesk:

```
You: "GLD entry $415, stop $410"
TradeDesk: "Position size: 142 shares. Risk: $710 (1.4% of $50K account)"
```

### Formula (ATR-based — pro standard)
```
Shares = (Account × Risk%) / (Entry - Stop)

Example:
Account   = $50,000
Risk      = 1% = $500
Entry     = $415
Stop      = $410
Risk/share = $5

Shares = $500 / $5 = 100 shares
Dollar risk = 100 × $5 = $500
Target (2:1) = $415 + $10 = $425
```

### System rules to define
- Max risk per trade: 1–2% of account
- Max daily loss: 5% of account → stop trading
- Max drawdown: 15% → review system
- Min R/R ratio: 2:1 before entering any trade
- Correlation limit: no more than 3 correlated positions

### Integration points
- Telegram: "size GLD 415 stop 410" → instant calculation
- Bridge endpoint: `POST /size` with entry/stop/account
- Watcher: include suggested size in P&L snapshot

### Phase 2 (after calculator works)
- Backtest our existing signals (VWAP, S/R, VCP) on historical data
- Measure actual win rate, expectancy, Sharpe ratio
- Only keep signals with proven edge
