# Skill: Earnings Expert

**Agent:** `earnings-expert`
**Trigger:** Earnings play analysis, "earnings", "IV crush", "options", "expected move", "earnings play", pre-earnings setup

## Purpose

Analyze earnings plays — expected move, IV crush risk, historical earnings reactions, and play recommendations for trading around an earnings event.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/earnings_expert.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches earnings date, options data, implied volatility, historical reactions, and generates a play recommendation.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "price": 122.30,
  "earnings_date": "2026-05-28",
  "earnings_timing": "AMC",
  "days_until_earnings": 63,
  "expected_move_pct": 8.5,
  "expected_move_dollars": 10.40,
  "iv_rank": 82,
  "iv_percentile": 78,
  "iv_crush_risk": "HIGH",
  "historical_reactions": [
    {"date": "2026-02-26", "move_pct": 7.2, "direction": "UP"},
    {"date": "2025-11-20", "move_pct": -3.1, "direction": "DOWN"},
    {"date": "2025-08-28", "move_pct": 12.8, "direction": "UP"},
    {"date": "2025-05-28", "move_pct": 9.4, "direction": "UP"}
  ],
  "avg_historical_move_pct": 8.13,
  "beat_rate_pct": 75,
  "play_recommendation": "Iron Condor or Straddle Sell",
  "notes": "High IV rank with expected move in line with historical — IV crush favors premium selling"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
EARNINGS EXPERT: NVDA
══════════════════════════════

EARNINGS DATE: 2026-05-28 (AMC)    Days Until: 63

EXPECTED MOVE
  Expected Move: +/-8.5% ($10.40)
  Avg Historical: +/-8.13%

IMPLIED VOLATILITY
  IV Rank:       82
  IV Percentile: 78
  IV Crush Risk: HIGH

HISTORICAL REACTIONS (last 4)
  2026-02-26:  +7.2%
  2025-11-20:  -3.1%
  2025-08-28: +12.8%
  2025-05-28:  +9.4%
  Beat Rate:   75%

PLAY RECOMMENDATION
  Iron Condor or Straddle Sell

NOTES
  High IV rank with expected move in line with historical — IV crush favors premium selling
```

### Step 4: Add Context

After the formatted output:

- **IV Crush HIGH**: "IV is elevated — premium sellers have an edge. Buying options into earnings is expensive"
- **IV Crush MODERATE**: "IV is fair — directional plays are viable if you have conviction"
- **IV Crush LOW**: "IV is cheap relative to history — long options/straddles may be underpriced"
- If `expected_move_pct` > `avg_historical_move_pct` * 1.3: "Market pricing a larger move than usual — options may be overpriced"
- If `expected_move_pct` < `avg_historical_move_pct` * 0.7: "Market pricing a smaller move than usual — options may be underpriced"
- If `days_until_earnings` < 7: "Earnings imminent — IV will not expand further, position now or stand aside"
- If `beat_rate_pct` > 80: "Consistent beater — but the bar is high, even beats can sell off"

### Step 5: Earnings Context Reminders

- IV crush happens immediately after earnings — long options lose value even if direction is right
- Expected move is derived from at-the-money straddle price — it's the market's best guess
- Historical reactions show magnitude, not direction — a stock can beat and still drop
- AMC (after market close) earnings: gap shows at next open. BMO (before market open): reaction is intraday
- Earnings are binary events — position sizing is more important than direction

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If no upcoming earnings date is found, note "No earnings date scheduled"
- If options data is unavailable, note "Options data unavailable — cannot calculate expected move"
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **fundamental context** around earnings, coordinate with `fundamental-analyst`
- For **technical levels** to set strikes or stops, coordinate with `technical-analyst`
- For **news/whisper numbers**, coordinate with `news-fetcher`
- For **overnight risk** if holding through earnings, coordinate with `overnight-expert`

## Reference

See [references/setups.md](references/setups.md) for detailed earnings play definitions and examples.
