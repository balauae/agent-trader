# Skill: Market Open Scalper

**Agent:** `market-open-scalper`
**Trigger:** Opening range breakout, "ORB", "first candle", "9:30", "market open", first 30 minutes scalp setups

## Purpose

Detect opening range breakout (ORB) setups during the first 30 minutes of regular trading (9:30-10:00AM ET) and present a clean trade plan with entry, stop, target, and risk/reward.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/market_open_scalper.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches the first 30 minutes of 1m data, calculates the opening range high/low, and detects the active ORB setup.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "timeframe": "1m",
  "orb_period": "9:30-10:00",
  "price": 121.30,
  "orb_high": 122.50,
  "orb_low": 119.80,
  "orb_range": 2.70,
  "orb_range_pct": 2.24,
  "setup": "ORB Long",
  "bias": "LONG",
  "entry": 122.55,
  "stop": 119.75,
  "target": 125.35,
  "risk_reward": 1.0,
  "volume_confirmation": true,
  "notes": "Price breaking above opening range high with volume — ORB long"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
MARKET OPEN SCALPER: NVDA
══════════════════════════════

SETUP: ORB Long                Bias: LONG
Price: $121.30                 Period: 9:30-10:00

OPENING RANGE
  ORB High (ORH): $122.50
  ORB Low  (ORL): $119.80
  Range:          $2.70 (2.24%)

TRADE PLAN
  Entry:       $122.55 (above ORH)
  Stop Loss:   $119.75 (below ORL)
  Target:      $125.35
  Risk/Reward: 1:1.00
  Volume:      Confirmed

NOTES
  Price breaking above opening range high with volume — ORB long
```

### Step 4: Add Context

After the formatted output:

- **ORB Long**: "Breakout above ORH — confirm with volume surge and hold above level"
- **ORB Short**: "Breakdown below ORL — confirm with volume and no immediate reclaim"
- **Inside Range**: "Price still within opening range — wait for breakout or breakdown"
- **Failed ORB**: "Breakout failed and reversed — potential fade setup"
- If `volume_confirmation` is false: "Volume not confirming — reduce size or wait for retest"
- If `risk_reward` < 1.5: "R:R below 1.5 — consider using half-range stop or narrower entry"
- If `orb_range_pct` > 3.0: "Wide opening range — consider scaling in or using micro pullback entry"

### Step 5: ORB Context Reminders

- The opening range is defined by the first 30 minutes (9:30-10:00AM ET)
- ORB works best on stocks with a catalyst or pre-market momentum
- First 5-minute candle breakouts are aggressive — higher win rate with 15- or 30-min ORB
- VWAP often acts as a magnet during the opening range — coordinate with `vwap-watcher`
- Avoid ORB on low-float stocks with erratic price action in the first minutes

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If run before 10:00AM ET, note "Opening range still forming — partial data"
- If run outside RTH, note "Market is closed — showing last session's opening range"
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **pre-market gap context**, coordinate with `premarket-specialist`
- For **VWAP levels** during the open, coordinate with `vwap-watcher`
- For **news catalysts** driving the move, coordinate with `news-fetcher`
- For **full technical analysis**, hand off to `technical-analyst`

## Reference

See [references/setups.md](references/setups.md) for detailed ORB setup definitions and examples.
