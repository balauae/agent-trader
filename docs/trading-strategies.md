# Trading Strategies — Research & Implementation Plan

Based on top Wall Street analysts. Each strategy has a clear implementation path in our codebase.

---

## 1. Mark Minervini — SEPA / VCP (Volatility Contraction Pattern)

**Core Idea:** Stocks tighten up before explosive breakouts. Volume dries up during contraction, then surges on breakout. Only buy when all criteria align.

### SEPA Trend Template (all must be true to consider a stock)
1. Price above both 150MA and 200MA
2. 200MA trending up for at least 1 month
3. 50MA above both 150MA and 200MA
4. Price at least 30% above 52-week low
5. Price within 25% of 52-week high
6. Relative Strength (RS) rank ≥ 70

### VCP Pattern Detection
- 3–4 price contractions, each tighter than the last
- Volume declines on each contraction
- Final contraction: price range <10%, volume at lows
- Breakout: price clears pivot on volume >150% avg

### Implementation Plan
- **New script:** `scripts/vcp_scanner.py TICKER`
- Input: ticker or watchlist
- Output: JSON with VCP stage, pivot level, contraction count, volume trend
- **Watcher alert:** "🔥 NVDA VCP pivot at $172 — breakout watch"
- **Bridge endpoint:** `GET /vcp/{ticker}`

### Example Output
```json
{
  "ticker": "NVDA",
  "sepa_score": "5/6",
  "vcp_detected": true,
  "contractions": 3,
  "pivot_level": 172.50,
  "volume_trend": "declining",
  "setup": "VCP Stage 3 — near pivot",
  "action": "watch_for_breakout"
}
```

---

## 2. William O'Neil — CANSLIM

**Core Idea:** Combine fundamental strength with technical breakout. Only buy leading stocks with accelerating earnings, institutional backing, and new catalysts.

### CANSLIM Criteria
| Letter | Factor | Threshold |
|--------|--------|-----------|
| C | Current quarterly EPS growth | ≥ 25% YoY |
| A | Annual EPS growth (3 years) | ≥ 25% avg |
| N | New product/catalyst/52w high | Present |
| S | Shares outstanding (float) | < 50M preferred |
| L | Leader in its sector (RS rank) | Top 20% |
| I | Institutional sponsorship trend | Increasing |
| M | Market direction (SPY/QQQ) | Uptrend |

### Implementation Plan
- **Enhance:** `scripts/fundamental_analyst.py` — add CANSLIM score (0–7)
- **New field in output:** `"canslim_score": 5, "canslim_flags": ["C", "A", "N", "M"]`
- **Scanner integration:** filter watchlist by CANSLIM ≥ 4
- **Data sources:** yfinance (C, A, S), news_fetcher (N), SPY trend (M)

### Example Output Addition
```json
{
  "canslim_score": "5/7",
  "canslim_flags": {
    "C": {"pass": true,  "eps_growth_pct": 35.2},
    "A": {"pass": true,  "annual_growth_pct": 28.1},
    "N": {"pass": true,  "catalyst": "New AI chip launch"},
    "S": {"pass": false, "float_m": 24500},
    "L": {"pass": true,  "rs_rank": 85},
    "I": {"pass": true,  "inst_trend": "increasing"},
    "M": {"pass": false, "spy_trend": "downtrend"}
  }
}
```

---

## 3. Linda Raschke — 80/20 Fade Setup

**Core Idea:** If price opens in the top 20% of prior day's range → expect fade back down (80% of the time). If opens in bottom 20% → expect bounce. Simple, high-probability mean reversion.

### Rules
```
prior_range = PDH - PDL
open_position = (open_price - PDL) / prior_range

If open_position > 0.80:
  setup = "fade-short"
  target = PDL + (prior_range * 0.50)   # mean of prior range
  stop   = today's high + 0.1%

If open_position < 0.20:
  setup = "fade-long"
  target = PDH - (prior_range * 0.50)
  stop   = today's low - 0.1%
```

### Implementation Plan
- **Enhance:** `scripts/premarket_specialist.py` — add `raschke_fade` field
- **5 lines of code** — quick win
- Works best on: low-float momentum stocks, gap plays

### Example Output Addition
```json
{
  "raschke_fade": {
    "open_position_pct": 85,
    "setup": "fade-short",
    "target": 412.30,
    "stop": 416.80,
    "notes": "Opened in top 20% of prior range — fade candidate"
  }
}
```

---

## 4. Larry Williams — %R + Volatility Breakout Levels

**Core Idea:** Two tools:
1. **Williams %R** — overbought/oversold oscillator (similar to RSI but range-bound)
2. **Volatility Breakout** — exact price levels at open where momentum kicks in

### Williams %R
```
%R = (Highest High - Close) / (Highest High - Lowest Low) × -100
Range: 0 to -100
Overbought: > -20 (near 0)
Oversold:   < -80 (near -100)
```

### Volatility Breakout Levels
```
Buy level   = yesterday's open + (ATR × 0.6)
Short level = yesterday's open - (ATR × 0.6)
```
If price opens and immediately clears the buy level → momentum long.

### Implementation Plan
- **Williams %R:** add to `scripts/technical_analyst.py` indicators section
- **Breakout levels:** add to `scripts/market_open_scalper.py`
- **Alert in watcher:** "⚡ GLD cleared Williams breakout level $416.20"

### Example Output Addition
```json
{
  "williams_r": -22.5,
  "williams_r_signal": "overbought",
  "williams_breakout": {
    "buy_level":   416.20,
    "short_level": 413.10,
    "atr":         2.83,
    "notes": "Break above $416.20 = momentum long signal"
  }
}
```

---

## 5. Stan Weinstein — Stage Analysis

**Core Idea:** Every stock goes through 4 stages. Only buy in Stage 2 (uptrend). Never buy Stage 4 (downtrend). Simple but powerful filter.

### The 4 Stages
| Stage | Name | Description | Action |
|-------|------|-------------|--------|
| 1 | Basing | Flat, below/at 30-week MA, volume low | Wait |
| 2 | Advancing | Above 30-week MA, higher highs/lows, volume rising | **BUY** |
| 3 | Topping | Churning at highs, erratic, MA flattening | Sell/Avoid |
| 4 | Declining | Below 30-week MA, lower lows | **AVOID / SHORT** |

### Detection Rules
```python
ma_30w = SMA(close, 150)  # ~30 weeks on daily chart

if price > ma_30w and ma_30w trending up:
    if prev_week_low > prev_prev_week_low:  # higher lows
        stage = 2  # ADVANCING — buy zone
elif price > ma_30w and ma_30w flattening:
    stage = 3  # TOPPING — caution
elif price < ma_30w and ma_30w trending down:
    stage = 4  # DECLINING — avoid
else:
    stage = 1  # BASING — wait
```

### Implementation Plan
- **Enhance:** `scripts/technical_analyst.py` — add `weinstein_stage` field
- **Scanner filter:** skip Stage 3/4 stocks from momentum watchlist
- **Alert:** "⚠️ NVDA entering Stage 3 — consider reducing position"

### Example Output Addition
```json
{
  "weinstein_stage": 2,
  "weinstein_label": "ADVANCING",
  "ma_30w": 158.40,
  "ma_30w_trend": "up",
  "stage_notes": "Price above rising 30-week MA, higher lows — buy zone"
}
```

---

## 6. Jesse Livermore — Pivot Points + Line of Least Resistance

**Core Idea:** Price always follows the "line of least resistance" — the direction it wants to move with least effort. Buy pivot breakouts only when confirmed by volume. Never average down — cut losers fast.

### Key Concepts

**Pivot Point Breakout:**
- Stock consolidates (forms a base)
- Breaks out of base on 2x+ average volume
- This is the "natural buying point"
- Stop: just below the pivot/breakout level

**Line of Least Resistance:**
```
If stock breaks resistance on high volume → upside is path of least resistance
If stock fails resistance 2+ times → downside is path of least resistance
```

**Livermore Key Price Levels:**
- Previous significant high = resistance
- Round numbers = natural pivots ($100, $200, $500)
- 50% retracement of a major move = key level

### Implementation Plan
- **Enhance:** `scripts/support_resistance.py` — add `livermore_pivot` detection
- **New field:** breakout confirmation (volume check at pivot)
- **Alert in watcher:** "🎯 GLD Livermore pivot breakout at $415 confirmed — volume 2.3x"
- Already have S/R detection — add volume confirmation layer on top

### Example Output Addition
```json
{
  "livermore_pivot": {
    "level": 415.00,
    "type": "breakout_pivot",
    "volume_ratio": 2.3,
    "confirmed": true,
    "line_of_least_resistance": "UP",
    "notes": "Clean breakout above $415 on 2.3x volume — upside path clear"
  }
}
```

---

## Implementation Priority

| # | Strategy | Script | Effort | Value |
|---|----------|--------|--------|-------|
| 1 | **Raschke Fade** | `premarket_specialist.py` | Low (5 lines) | High |
| 2 | **Williams %R + Breakout** | `technical_analyst.py` + `market_open_scalper.py` | Low | High |
| 3 | **Weinstein Stage** | `technical_analyst.py` | Low | High |
| 4 | **Livermore Pivot Confirm** | `support_resistance.py` | Medium | High |
| 5 | **CANSLIM Score** | `fundamental_analyst.py` | Medium | High |
| 6 | **VCP Scanner** | New `vcp_scanner.py` | High | Very High |

---

## Quick Wins (build next session)
1. Raschke fade → `premarket_specialist.py` (5 lines)
2. Williams %R → `technical_analyst.py` (10 lines)
3. Williams breakout levels → `market_open_scalper.py` (5 lines)
4. Weinstein stage → `technical_analyst.py` (15 lines)

These 4 can be done in one session with minimal risk of breaking existing code.
