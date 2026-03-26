# Pattern Finder Skill

## Description
Chart pattern detection using pure pandas/numpy on daily OHLCV data. Detects classic technical patterns with confidence scoring and entry/stop/target levels.

## Triggers
- "chart patterns on X"
- "pattern X"
- "is there a flag on X"
- "double top/bottom X"
- "head and shoulders X"
- "wedge on X"
- "triangle X"

## Usage
```bash
python scripts/pattern_finder.py TICKER
```

## Patterns Detected
| Pattern | Bias | Description |
|---------|------|-------------|
| Bull Flag | BULLISH | Strong up move + tight consolidation |
| Bear Flag | BEARISH | Strong down move + tight consolidation |
| Double Bottom | BULLISH | Two similar lows + neckline break |
| Double Top | BEARISH | Two similar highs + neckline break |
| Rising Wedge | BEARISH | Converging upward channel |
| Falling Wedge | BULLISH | Converging downward channel |
| Symmetrical Triangle | NEUTRAL | Coiling — watch for breakout |

## Sample Output
```json
{
  "ticker": "MRVL",
  "patterns_found": [
    {
      "pattern": "Double Bottom",
      "bias": "BULLISH",
      "confidence": 90,
      "description": "Two lows at $79.20 and $77.72, neckline $81.34 broken",
      "entry": 81.34,
      "stop": 76.94,
      "target": 84.96,
      "bars_ago": 24
    }
  ],
  "best_pattern": {...},
  "overall_bias": "BULLISH",
  "summary_text": "Double Bottom detected (90% confidence)"
}
```

## Notes
- Uses 60 days of daily data
- Pure pandas/numpy — no ta-lib
- Confidence score 0-100%
- `bars_ago` = how many bars ago the pattern completed (0 = current)
