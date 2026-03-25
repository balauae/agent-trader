# Skill: VWAP Watcher

**Agent:** `vwap-watcher`
**Trigger:** VWAP setup requests, intraday entry/exit around VWAP, "what's the VWAP setup on [ticker]?", scalp entries near VWAP

## Purpose

Detect VWAP-based intraday setups and present a clean trade plan with setup type, entry, stop, target, and risk/reward.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/vwap_watcher.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches 200 bars of 1m data, computes session VWAP with standard deviation bands, and detects the active setup.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "timeframe": "1m",
  "bars": 200,
  "price": 120.45,
  "vwap": 119.8500,
  "bands": {
    "upper_2σ": 122.10,
    "upper_1σ": 120.97,
    "lower_1σ": 118.73,
    "lower_2σ": 117.60
  },
  "price_vs_vwap": "ABOVE",
  "distance_pct": 0.501,
  "setup": "VWAP Bounce Long",
  "bias": "LONG",
  "entry": 119.96,
  "stop": 119.29,
  "target": 120.97,
  "risk_reward": 1.51,
  "volume_confirmation": true,
  "notes": "Price pulled back to VWAP and holding above — bounce long"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
VWAP WATCHER: NVDA
══════════════════════════════

SETUP: VWAP Bounce Long       Bias: LONG
Price: $120.45                 VWAP: $119.85
Position: ABOVE VWAP           Distance: +0.50%

VWAP BANDS
  Upper 2σ:  $122.10
  Upper 1σ:  $120.97
  ── VWAP ── $119.85
  Lower 1σ:  $118.73
  Lower 2σ:  $117.60

TRADE PLAN
  Entry:       $119.96
  Stop Loss:   $119.29
  Target:      $120.97
  Risk/Reward: 1:1.51
  Volume:      Confirmed

NOTES
  Price pulled back to VWAP and holding above — bounce long
```

### Step 4: Add Context

After the formatted output:

- **Bounce / Break / Reclaim**: "Actionable setup — confirm with volume and price action"
- **Extended**: "Mean reversion play — wait for momentum to stall before entry"
- **Rejection**: "Failed breakout — look for continuation lower"
- **No Setup**: "No clean VWAP setup — stand aside or wait for price to approach VWAP"
- If `volume_confirmation` is false: "Volume not confirming — reduce size or wait"
- If `risk_reward` < 1.5: "R:R below 1.5 — consider tighter stop or wider target"

### Step 5: VWAP Context Reminders

- VWAP resets each session — most reliable during RTH (9:30 AM - 4:00 PM ET)
- Pre-market VWAP has lower reliability — flag this if trading before open
- First 15 minutes: VWAP is volatile, setups are less reliable
- VWAP is institutional — large players use it as a benchmark

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If market is closed, 1m data may be stale — note "Data from last session"
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **full technical analysis**, hand off to `technical-analyst` — do not duplicate indicator work
- For **multi-timeframe context**, coordinate with `timeframe-analyzer`
- For **scalp entries in first 30 min**, coordinate with `market-open-scalper`
- For **news catalysts** driving the move, coordinate with `news-fetcher`

## Reference

See [references/setups.md](references/setups.md) for detailed VWAP setup definitions and examples.
