# Timeframe Analyzer Skill

## Description
Multi-timeframe confluence analysis — checks 1m, 5m, 15m, and 1D simultaneously to find high-conviction setups. The more timeframes that agree, the stronger the signal.

## Triggers
- "timeframe analysis on X"
- "multi timeframe X"
- "MTF X"
- "all timeframes X"
- "confluence on X"
- "what do all timeframes say about X"

## Usage
```bash
python scripts/timeframe_analyzer.py TICKER
```

## Timeframes Analyzed
| TF | Purpose |
|----|---------|
| 1m | Scalp — intraday noise + VWAP setup |
| 5m | Primary intraday — main signal |
| 15m | Confirmation — trend within day |
| 1D | Daily — overall trend direction |

## Confluence Scoring
- **HIGH (3-4/4)** — Strong signal, act with conviction
- **MEDIUM (2/4)** — Mixed, wait for clarity
- **LOW (1/4 or less)** — No trade, conflicting signals

## Sample Output
```json
{
  "ticker": "MRVL",
  "overall_bias": "BULLISH",
  "confluence": "HIGH",
  "confluence_score": "3/4",
  "timeframes": {
    "1m": {"bias": "BULLISH", "rsi": 65.8, "macd": 0.08, "setup": "VWAP Bounce Long", "rr": 1.57},
    "5m": {"bias": "NEUTRAL", "rsi": 56.2, "macd": 0.04},
    "15m": {"bias": "BULLISH", "rsi": 67.3, "macd": 0.90},
    "1D": {"bias": "BULLISH", "rsi": 67.6, "macd": 3.13}
  },
  "recommendation": "Strong long — 3/4 TFs aligned. Wait for 5m to confirm.",
  "best_entry": "$98.44",
  "stop": "$97.99",
  "target": "$98.82"
}
```

## Notes
- All 4 timeframes fetched in parallel (fast)
- VWAP setup only on 1m (intraday)
- Entry/stop/target from 5m levels (most reliable for day trading)
