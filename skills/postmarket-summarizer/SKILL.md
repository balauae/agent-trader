# Skill: Post-Market Summarizer

**Agent:** `postmarket-summarizer`
**Trigger:** End-of-day recap, "how did X do", "EOD", "end of day", "recap", "after close", daily performance summary

## Purpose

Generate an end-of-day recap for a ticker — how it performed during the session, key levels hit, volume profile, and VWAP close position.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/postmarket_summarizer.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches the full day's data, computes key metrics, and summarizes the session.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "date": "2026-03-26",
  "open": 119.50,
  "close": 122.30,
  "high": 123.80,
  "low": 118.90,
  "day_change_pct": 2.34,
  "day_change_direction": "UP",
  "hod_time": "14:22",
  "lod_time": "09:45",
  "vwap_close": 121.15,
  "vwap_close_position": "ABOVE",
  "volume": 58200000,
  "avg_volume": 42000000,
  "volume_ratio": 1.39,
  "range_pct": 4.12,
  "notes": "Strong day — closed near highs above VWAP with elevated volume"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
POST-MARKET SUMMARIZER: NVDA
══════════════════════════════

DATE: 2026-03-26               Change: +2.34% UP

PRICE ACTION
  Open:   $119.50              Close:  $122.30
  HOD:    $123.80 (14:22)      LOD:    $118.90 (09:45)
  Range:  4.12%

VWAP
  VWAP Close: $121.15
  Position:   ABOVE VWAP (bullish close)

VOLUME
  Volume:     58.2M
  Avg Volume: 42.0M
  Ratio:      1.39x (above average)

NOTES
  Strong day — closed near highs above VWAP with elevated volume
```

### Step 4: Add Context

After the formatted output:

- **Closed above VWAP**: "Institutional buyers in control — bullish for next session"
- **Closed below VWAP**: "Sellers dominated — watch for follow-through weakness"
- **Closed at VWAP**: "Neutral close — no clear edge for next day"
- If `volume_ratio` > 1.5: "Heavy volume day — move has conviction"
- If `volume_ratio` < 0.7: "Light volume — move may lack follow-through"
- If `close` near `high`: "Closed near HOD — strong finish, momentum may carry"
- If `close` near `low`: "Closed near LOD — weak finish, caution for longs"

### Step 5: EOD Context Reminders

- VWAP close position is one of the best indicators for next-day bias
- Volume relative to average is more important than absolute volume
- HOD/LOD timing matters — late-day highs are stronger than morning spikes that faded
- Range % helps gauge volatility — compare to recent average for context

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If run during market hours, note "Market still open — partial day data"
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **overnight planning** based on today's action, hand off to `overnight-expert`
- For **VWAP context** from the session, coordinate with `vwap-watcher`
- For **news catalysts** that drove the move, coordinate with `news-fetcher`
- For **next-day pre-market** setup, coordinate with `premarket-specialist`

## Reference

See [references/setups.md](references/setups.md) for detailed EOD analysis definitions and examples.
