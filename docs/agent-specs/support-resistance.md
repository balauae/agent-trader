# Agent: Support & Resistance Detector

**ID:** `support-resistance`  
**Type:** Specialist  
**Trigger:** "levels on GLD", "where's support", "key levels", "S/R zones", automatically called by technical-analyst

## Role

Programmatically detect and rank significant price levels where the market has previously reversed, consolidated, or traded heavy volume. Outputs ranked S/R zones used by the watcher for real-time proximity alerts.

## Two-Layer Architecture

### Layer 1 — Python (Compute)
Runs once on demand or at session start. Detects levels from historical OHLCV data.

### Layer 2 — Go (Monitor)
Loads levels from bridge on watcher startup. Fires real-time alerts when price approaches or breaks a level.

---

## Detection Methods (Python)

### 1. Swing Pivots
Identify local highs and lows using a lookback window (default: 5 bars left/right).
- Swing high: bar[i].high > all surrounding bars → resistance candidate
- Swing low: bar[i].low < all surrounding bars → support candidate
- Cluster nearby pivots within 0.3% into a single zone

### 2. Volume Clusters (HVN — High Volume Nodes)
Divide price range into bins. Sum volume at each bin.
- Bins with volume > 1.5x average = high volume node → strong S/R
- These levels act as magnets — price tends to return

### 3. Round Numbers
For every $5 or $10 increment within 5% of current price:
- $410, $415, $420, $425 on GLD
- Flag as "psychological level"
- Weight lower if no price history at that level

### 4. Previous Day / Week Highs & Lows
- PDH (Previous Day High) — key intraday resistance
- PDL (Previous Day Low) — key intraday support
- PWH / PWL — weekly high/low for swing context

### 5. Moving Average Levels
- Price at SMA50, SMA200, EMA9, EMA21
- These become dynamic S/R levels
- Already computed by technical_analyst.py — import, don't recompute

---

## Level Scoring

Each level gets a strength score 1–5:

| Factor | Score |
|--------|-------|
| Tested 3+ times | +2 |
| High volume node | +2 |
| Round number | +1 |
| Recent (last 20 bars) | +1 |
| Multiple timeframe confluence | +2 |

Max score = 5 (cap). Levels with score ≥ 3 = **key levels**.

---

## Output JSON

```json
{
  "ticker": "GLD",
  "price": 414.69,
  "timeframe": "1D",
  "computed_at": "2026-03-28T...",
  "resistance": [
    {"level": 418.40, "type": "swing_high", "strength": 4, "label": "Recent high (Mar 27)"},
    {"level": 420.00, "type": "round_number+target", "strength": 3, "label": "Round number / target"},
    {"level": 425.00, "type": "round_number", "strength": 2, "label": "Round number"}
  ],
  "support": [
    {"level": 412.87, "type": "vwap", "strength": 3, "label": "VWAP"},
    {"level": 410.00, "type": "round_number+hvn", "strength": 4, "label": "HVN / Round number"},
    {"level": 405.41, "type": "swing_low", "strength": 3, "label": "Session low (Mar 27)"},
    {"level": 400.00, "type": "round_number", "strength": 2, "label": "Round number"}
  ],
  "key_levels": [418.40, 420.00, 412.87, 410.00, 405.41],
  "nearest_resistance": 418.40,
  "nearest_support": 412.87,
  "nearest_resistance_dist_pct": 0.89,
  "nearest_support_dist_pct": 0.44
}
```

---

## Go Watcher Integration

On watcher startup (or on-demand refresh):
1. Call `GET /sr/{ticker}` on FastAPI bridge
2. Load `key_levels` array into watcher goroutine
3. On each bar, check: `abs(price - level) / price < 0.002` (within 0.2%)
4. Fire alert: `"⚠️ GLD approaching resistance $418.40 (0.4% away)"`
5. On break: `"🔼 GLD broke above $418.40 — next resistance $420.00"`

Alert cooldown: 30 mins per level (levels don't change often).

---

## Script

`scripts/support_resistance.py TICKER [timeframe] [bars]`

- Default timeframe: `1D`
- Default bars: `200`
- Outputs JSON to stdout

---

## Notes

- Python computes **where** levels are (historical analysis)
- Go monitors **if price reaches** them (real-time)
- Refresh levels: daily at market open, or on-demand
- Levels loaded into watcher via bridge `/sr/{ticker}` endpoint
- Do not recompute moving averages — import from `data_fetcher.py`
