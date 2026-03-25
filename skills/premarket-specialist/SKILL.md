# Skill: Pre-Market Specialist

**Agent:** `premarket-specialist`
**Trigger:** Pre-market gap analysis, "pre-market", "gap", "before open", gap-and-go vs gap-fill, 4AM-9:30AM ET setups

## Purpose

Detect pre-market gap setups (4AM-9:29AM ET) and classify them as gap-and-go or gap-fill candidates with key levels and a trade plan.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/premarket_specialist.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches pre-market data, calculates gap metrics against prior close, and identifies the setup type.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "prior_close": 118.50,
  "pm_price": 123.75,
  "gap_pct": 4.43,
  "gap_direction": "UP",
  "pm_high": 124.20,
  "pm_low": 121.80,
  "pm_volume": 2850000,
  "pm_volume_ratio": 2.1,
  "setup": "Gap-and-Go Long",
  "bias": "LONG",
  "entry": 124.25,
  "stop": 121.70,
  "target": 127.50,
  "risk_reward": 1.27,
  "catalyst": "Earnings beat",
  "notes": "Large gap with heavy PM volume — momentum continuation likely"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
PRE-MARKET SPECIALIST: NVDA
══════════════════════════════

SETUP: Gap-and-Go Long        Bias: LONG
Prior Close: $118.50           PM Price: $123.75
Gap: +4.43% UP

PM LEVELS
  PM High:   $124.20
  PM Low:    $121.80
  PM Volume: 2.85M (2.1x avg)

TRADE PLAN
  Entry:       $124.25 (above PM high)
  Stop Loss:   $121.70 (below PM low)
  Target:      $127.50
  Risk/Reward: 1:1.27

CATALYST
  Earnings beat

NOTES
  Large gap with heavy PM volume — momentum continuation likely
```

### Step 4: Add Context

After the formatted output:

- **Gap-and-Go**: "Strong gap with volume — look for breakout above PM high for continuation"
- **Gap-Fill**: "Weak gap or fading — watch for rejection at open and fill toward prior close"
- **Small gap (<1%)**: "Gap is minor — treat as normal open, not a gap play"
- If `pm_volume_ratio` < 1.0: "PM volume is light — gap may lack conviction"
- If `risk_reward` < 1.5: "R:R below 1.5 — consider waiting for a better entry or tighter stop"

### Step 5: Pre-Market Context Reminders

- Pre-market data starts at 4AM ET — liquidity is thin before 7AM
- Gaps > 5% are more likely to gap-and-go; gaps < 2% are more likely to fill
- Always check for a catalyst (earnings, news, sector move) — gapless gaps often fill
- PM high/low are key levels at the open — breakout or breakdown from these sets the tone
- Pre-market spreads are wide — use limit orders only

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If run outside 4AM-9:29AM ET, note "Pre-market session is closed — showing last PM data"
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **opening range breakout** after 9:30, hand off to `market-open-scalper`
- For **VWAP context** once the session opens, coordinate with `vwap-watcher`
- For **news catalysts** driving the gap, coordinate with `news-fetcher`
- For **full technical analysis**, hand off to `technical-analyst`

## Reference

See [references/setups.md](references/setups.md) for detailed pre-market setup definitions and examples.
