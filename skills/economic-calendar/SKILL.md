# Skill: Economic Calendar

**Agent:** `economic-calendar`
**Trigger:** "Any events today?", "what's on the calendar?", pre-trade risk check, earnings date questions, Fed meeting schedule, OPEX dates

## Purpose

Surface all scheduled market-moving events — macro releases, Fed decisions, earnings, and options expiry — sorted by date with impact ratings and urgency warnings.

## How to Execute

### Step 1: Run the Script

**Macro events only (no ticker):**
```bash
.venv/bin/python scripts/economic_calendar.py --days 7
```

**With a specific ticker (adds earnings):**
```bash
.venv/bin/python scripts/economic_calendar.py AAPL --days 7
```

Replace `AAPL` with any ticker. `--days` sets the lookahead window (default: 7).

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "generated_at": "2026-03-25T14:00:00+00:00",
  "lookahead_days": 7,
  "ticker": "AAPL",
  "events": [
    {
      "date": "2026-03-26",
      "time": "08:30",
      "event": "GDP Growth Rate QoQ Final",
      "impact": "High",
      "category": "Macro"
    },
    {
      "date": "2026-03-28",
      "time": "AMC/BMO",
      "event": "AAPL Earnings Report",
      "impact": "High",
      "category": "Earnings",
      "eps_estimate": 2.35,
      "revenue_estimate": 94200000000,
      "implied_move_pct": 4.2
    },
    {
      "date": "2026-04-17",
      "time": "16:00",
      "event": "Monthly Options Expiration (OPEX)",
      "impact": "Medium",
      "category": "OPEX"
    }
  ],
  "warnings": [
    "WITHIN 48H: GDP Growth Rate QoQ Final on 2026-03-26 — High impact",
    "EARNINGS ALERT: AAPL Earnings Report in 3 days — elevated IV risk"
  ],
  "next_high_impact": {
    "date": "2026-03-26",
    "event": "GDP Growth Rate QoQ Final",
    "impact": "High",
    "category": "Macro"
  }
}
```

### Step 3: Present as Trader-Friendly Briefing

Format the output like this:

```
ECONOMIC CALENDAR — Next 7 Days
════════════════════════════════

⚠ WARNINGS
  • WITHIN 48H: GDP Growth Rate QoQ Final on 2026-03-26 — High impact
  • EARNINGS ALERT: AAPL Earnings Report in 3 days — elevated IV risk

NEXT HIGH-IMPACT EVENT
  GDP Growth Rate QoQ Final — Wed Mar 26 08:30 ET

UPCOMING EVENTS
  Date        Time   Event                              Impact   Category
  ─────────── ────── ─────────────────────────────────── ──────── ────────
  2026-03-26  08:30  GDP Growth Rate QoQ Final          🔴 High  Macro
  2026-03-28  AMC    AAPL Earnings Report               🔴 High  Earnings
                     EPS Est: $2.35 | Rev Est: $94.2B
                     Implied Move: ±4.2%
  2026-04-17  16:00  Monthly Options Expiration (OPEX)  🟡 Med   OPEX
```

### Step 4: Add Context

After the formatted output:

- If **warnings are present**: Lead with them prominently — these are actionable
- If **earnings within 7 days**: Add "Consider IV crush risk before holding through earnings"
- If **FOMC today**: Add "FOMC day — expect wide ranges, thin liquidity before the announcement"
- If **OPEX this week**: Add "OPEX week — watch for pinning action near max pain levels"
- If **no events**: "Clear calendar — no scheduled high-impact events in this window"

## Error Handling

- If the script returns an empty `events` list with no errors, report: "No US macro events found in the lookahead window. Earnings data may still be available."
- If macro scraping fails, the script gracefully falls back to earnings + OPEX only — note this to the user
- If the script fails entirely, suggest checking network connectivity

## Coordination

- For **earnings play strategy**, hand off to `earnings-expert`
- For **technical levels around events**, coordinate with `technical-analyst`
- For **news context around macro releases**, coordinate with `news-fetcher`
- For **geopolitical risk overlay**, coordinate with `geopolitical-analyst`
- Auto-warn if any open ticker has earnings within 7 days — run the script with each open position ticker
