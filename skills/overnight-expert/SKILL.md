# Skill: Overnight Expert

**Agent:** `overnight-expert`
**Trigger:** Overnight trade planning, "overnight", "after hours", "AH", "tomorrow setup", "hold overnight", after-hours analysis

## Purpose

Analyze after-hours price action, assess overnight hold risk, identify key levels, and flag earnings or events that could impact the next session.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/overnight_expert.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches after-hours data, calculates risk metrics, and identifies key support/resistance levels for the next session.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "close": 122.30,
  "ah_price": 123.10,
  "ah_change_pct": 0.65,
  "ah_direction": "UP",
  "ah_high": 123.50,
  "ah_low": 121.80,
  "ah_volume": 3200000,
  "risk_level": "MODERATE",
  "support": [121.00, 119.50],
  "resistance": [124.00, 125.80],
  "earnings_tonight": false,
  "next_earnings_date": "2026-05-28",
  "overnight_gap_risk": "LOW",
  "notes": "Modest AH drift higher — no major catalyst, moderate overnight risk"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
OVERNIGHT EXPERT: NVDA
══════════════════════════════

RISK LEVEL: MODERATE

AFTER HOURS
  Close:    $122.30            AH Price: $123.10
  AH Change: +0.65% UP
  AH High:  $123.50            AH Low:   $121.80
  AH Volume: 3.2M

KEY LEVELS
  Resistance: $124.00 / $125.80
  Support:    $121.00 / $119.50

EVENTS
  Earnings Tonight: No
  Next Earnings:    2026-05-28
  Gap Risk:         LOW

NOTES
  Modest AH drift higher — no major catalyst, moderate overnight risk
```

### Step 4: Add Context

After the formatted output:

- **Risk LOW**: "Low overnight risk — holding through is reasonable with standard stop"
- **Risk MODERATE**: "Moderate risk — size accordingly, consider reducing position"
- **Risk HIGH**: "High overnight risk — earnings, macro event, or elevated AH volatility. Consider closing or hedging"
- If `earnings_tonight` is true: "Earnings after close — expect significant gap. Do NOT hold unhedged"
- If `ah_change_pct` > 2.0: "Large AH move — reassess position and levels before next session"
- If `ah_volume` is very low: "Thin AH volume — price may not hold at these levels"

### Step 5: Overnight Context Reminders

- After-hours liquidity is thin — AH price can be misleading
- Earnings, Fed announcements, and macro events are the biggest overnight risk factors
- Futures movement overnight can shift the open regardless of AH price
- Support/resistance levels from the regular session are more reliable than AH levels
- If holding overnight, always have a stop plan for the next open

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If run during market hours, note "Market still open — AH data not yet available"
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **today's session recap**, coordinate with `postmarket-summarizer`
- For **earnings analysis** if earnings are tonight, hand off to `earnings-expert`
- For **next-day pre-market** setup, coordinate with `premarket-specialist`
- For **news catalysts** after hours, coordinate with `news-fetcher`

## Reference

See [references/setups.md](references/setups.md) for detailed overnight setup definitions and examples.
