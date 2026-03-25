# Skill: Technical Analyst

**Agent:** `technical-analyst`
**Trigger:** Chart/indicator questions, entry/exit analysis, "what's the setup on [ticker]?", bias check, multi-timeframe overview

## Purpose

Run a full technical indicator sweep on a ticker and present a clean, trader-friendly analysis with directional bias, confluence score, key levels, and risk/reward.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/technical_analyst.py TICKER [timeframe]
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`). Timeframe defaults to `1D`.

Valid timeframes: `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1D`, `1W`

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "timeframe": "5m",
  "price": 120.45,
  "bias": "BULLISH",
  "confluence_score": "4/5",
  "indicators": {
    "ema_9": 120.30, "ema_21": 119.85,
    "sma_50": 118.20, "sma_200": 112.50,
    "macd_line": 0.45, "macd_signal": 0.30, "macd_histogram": 0.15,
    "rsi": 62.3,
    "bb_upper": 122.10, "bb_mid": 119.80, "bb_lower": 117.50,
    "atr": 1.85, "vwap": 119.95,
    "volume": 1250000, "volume_sma_20": 980000, "volume_above_avg": true
  },
  "levels": { "support": 117.50, "resistance": 122.10, "vwap": 119.95 },
  "signals": ["EMA9 above EMA21 — short-term bullish", "..."],
  "stop_loss": 117.67,
  "take_profit": 122.10,
  "risk_reward": 1.85
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
TECHNICAL ANALYSIS: NVDA — 5m
══════════════════════════════

BIAS: BULLISH          Confluence: 4/5
Price: $120.45         ATR(14): $1.85

INDICATORS
  EMA 9:    $120.30    EMA 21:  $119.85   (bullish alignment)
  SMA 50:   $118.20    SMA 200: $112.50   (golden cross territory)
  MACD:     0.45 / 0.30 / +0.15           (bullish)
  RSI(14):  62.3                          (bullish zone)
  BBands:   $122.10 / $119.80 / $117.50
  VWAP:     $119.95    (price above)
  Volume:   1.25M vs 980K avg             (above average)

KEY LEVELS
  Resistance:  $122.10
  VWAP:        $119.95
  Support:     $117.50

SIGNALS
  • EMA9 above EMA21 — short-term bullish
  • MACD histogram positive — bullish momentum
  • Price above VWAP — intraday bullish
  • Volume above 20-SMA — confirming move

TRADE SETUP
  Stop Loss:    $117.67  (1.5x ATR)
  Take Profit:  $122.10  (next resistance)
  Risk/Reward:  1:1.85
```

### Step 4: Add Context

After the formatted output:

- If **confluence >= 4/5**: "Strong confluence — high-conviction setup"
- If **confluence == 3/5**: "Mixed signals — wait for confirmation or reduce size"
- If **confluence <= 2/5**: "Weak/conflicting signals — no clear edge, stand aside"
- If **RSI > 70 or < 30**: Flag extreme reading prominently
- If **Bollinger squeeze** detected: Flag potential volatility expansion

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If data is insufficient (< 30 bars), suggest trying a higher timeframe
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **VWAP-specific setups**, coordinate with `vwap-watcher` — do not override its VWAP analysis
- For **multi-timeframe confluence**, run this skill on multiple timeframes and synthesize
- For **fundamentals context**, hand off to `fundamentals-analyst`
- For **news-driven moves**, coordinate with `news-fetcher` to explain catalyst
