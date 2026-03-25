# Skill: Orchestrator

**Agent:** `orchestrator`
**Trigger:** Any user query — this is the primary entry point for all TradeDesk interactions
**Always Active:** Yes

## Purpose

Route user queries to the right specialist agents, run them in parallel, and synthesize all outputs into a single coherent trader response. Detects market session from current time and adjusts context accordingly.

## Market Sessions (Eastern Time)

| Session       | Hours (ET)          | Notes                                      |
|---------------|---------------------|--------------------------------------------|
| Pre-Market    | 04:00 - 09:29       | Thin liquidity, gap analysis, news-driven  |
| Open          | 09:30 - 09:59       | High volatility, opening range             |
| Regular       | 10:00 - 15:29       | Core session, most setups valid            |
| Close         | 15:30 - 15:59       | MOC flows, positioning                     |
| Post-Market   | 16:00 - 19:59       | Earnings reactions, thin books             |
| Overnight     | 20:00 - 03:59       | Futures-driven, macro/geopolitical risk    |

## How to Execute

### Step 1: Run the Orchestrator

```bash
.venv/bin/python scripts/orchestrator.py "USER QUERY HERE"
```

Examples:
```bash
.venv/bin/python scripts/orchestrator.py "analyze NVDA"
.venv/bin/python scripts/orchestrator.py "news on TSLA"
.venv/bin/python scripts/orchestrator.py "what's the VWAP setup on AAPL"
.venv/bin/python scripts/orchestrator.py "any earnings this week?"
.venv/bin/python scripts/orchestrator.py "market summary"
```

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "query": "analyze NVDA",
  "ticker": "NVDA",
  "intent": "analyze",
  "session": "Regular",
  "timestamp": "2026-03-25T14:30:00-04:00",
  "agents_used": ["technical_analyst", "vwap_watcher", "news_fetcher", "economic_calendar"],
  "results": {
    "technical_analyst": { ... },
    "vwap_watcher": { ... },
    "news_fetcher": { ... },
    "economic_calendar": { ... }
  },
  "errors": {},
  "summary": "NVDA is showing a BULLISH bias with 4/5 confluence..."
}
```

### Step 3: Present Synthesized Response

Combine all agent results into a single trader briefing:

```
TRADEDESK: NVDA — Regular Session
===================================

BIAS: BULLISH (4/5 confluence)
Price: $120.45 | VWAP: $119.85 (ABOVE)

TECHNICAL
  EMA 9/21: Bullish alignment
  MACD: Positive momentum
  RSI: 62.3 (bullish zone)
  R:R: 1:1.85

VWAP SETUP
  Setup: VWAP Bounce Long
  Entry: $119.96 | Stop: $119.29 | Target: $120.97

NEWS
  [HIGH] Earnings beat: Q4 EPS $5.16 vs $4.64 est.
  [MED]  New AI partnership announced

CALENDAR
  No high-impact events in next 48h

SUMMARY
  Strong bullish setup with volume confirmation. Consider
  long entry on pullback to VWAP with 1.5:1 R:R.
```

### Step 4: Session-Aware Context

Add session-specific notes:

- **Pre-Market**: "Pre-market — VWAP not yet established, gaps may fill at open"
- **Open**: "Opening range forming — wait for first 15 min to settle before entries"
- **Regular**: Standard analysis, all setups valid
- **Close**: "Approaching close — watch for MOC imbalances"
- **Post-Market**: "After hours — thin liquidity, spreads wide"
- **Overnight**: "Overnight session — futures-driven, watch for macro catalysts"

## Intent Routing

See [references/routing-table.md](references/routing-table.md) for the full routing matrix.

| Intent           | Agents Invoked                                              |
|------------------|-------------------------------------------------------------|
| `analyze`        | technical_analyst, vwap_watcher, news_fetcher, economic_calendar |
| `news`           | news_fetcher                                                |
| `chart` / `setup`| technical_analyst, vwap_watcher                             |
| `earnings` / `calendar` | economic_calendar                                    |
| `market`         | technical_analyst, news_fetcher, economic_calendar          |

## Error Handling

- If an agent times out (15s limit), include partial results from agents that succeeded and note: "[agent] timed out — results unavailable"
- If all agents fail, return the raw error and suggest checking data connectivity
- If no ticker is detected and one is required, note: "No ticker detected — showing market-wide data"

## Coordination

- The orchestrator never fabricates data — all data comes from agent outputs
- Each agent runs independently with a 15-second timeout
- Agents run in parallel via ThreadPoolExecutor for speed
- If conflicting signals across agents, present both and flag the conflict
