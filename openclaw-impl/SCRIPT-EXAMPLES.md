# TradeDesk Script Examples
> Real outputs captured on 2026-03-26 using MRVL as example ticker

---

## 1. `vwap_watcher.py` — VWAP Setup Detection

```bash
python scripts/vwap_watcher.py MRVL
python scripts/vwap_watcher.py TSLA
python scripts/vwap_watcher.py NVDA
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "price": 98.44,
  "vwap": 98.17,
  "bands": {"upper_2σ": 98.64, "upper_1σ": 98.41, "lower_1σ": 97.93, "lower_2σ": 97.69},
  "price_vs_vwap": "ABOVE",
  "distance_pct": 0.272,
  "setup": "VWAP Bounce Long",
  "bias": "LONG",
  "entry": 98.19,
  "stop": 98.05,
  "target": 98.41,
  "risk_reward": 1.57,
  "volume_confirmation": true,
  "notes": "Price pulled back to VWAP and holding above — bounce long"
}
```

---

## 2. `technical_analyst.py` — Technical Analysis

```bash
python scripts/technical_analyst.py MRVL 1D
python scripts/technical_analyst.py TSLA 5m
python scripts/technical_analyst.py NVDA 1m
```

**Real output (MRVL 1D):**
```json
{
  "ticker": "MRVL",
  "timeframe": "1D",
  "price": 98.45,
  "bias": "BULLISH",
  "confluence_score": "5/5",
  "indicators": {
    "ema_9": 91.25, "ema_21": 87.97, "sma_50": 82.83, "sma_200": 80.72,
    "macd_line": 3.13, "rsi": 67.55, "atr": 4.54
  },
  "signals": [
    "EMA9 above EMA21 — short-term bullish",
    "SMA50 above SMA200 — golden cross",
    "Price above SMA200 — long-term uptrend",
    "MACD histogram positive — bullish momentum",
    "RSI 67.6 — bullish zone"
  ],
  "stop_loss": 91.64,
  "take_profit": 98.82
}
```

---

## 3. `premarket_specialist.py` — Pre-Market Gap Analysis

```bash
python scripts/premarket_specialist.py MRVL
python scripts/premarket_specialist.py ARM
python scripts/premarket_specialist.py TSLA
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "prior_close": 98.50,
  "premarket_price": 96.79,
  "gap_pct": -1.74,
  "gap_direction": "DOWN",
  "pm_high": 97.60,
  "pm_low": 96.72,
  "volume_ratio": 0.0,
  "setup": "gap-fill",
  "notes": "Gap on low volume — likely to fill back toward prior close"
}
```
Setups: `gap-and-go` | `gap-fill` | `watch` | `no-trade`

---

## 4. `market_open_scalper.py` — Opening Range Breakout

```bash
python scripts/market_open_scalper.py MRVL
python scripts/market_open_scalper.py TSLA
python scripts/market_open_scalper.py NVDA
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "current_price": 98.44,
  "orh": 98.19,
  "orl": 97.86,
  "or_midpoint": 98.03,
  "or_size": 0.33,
  "setup": "ORB Long",
  "bias": "LONG",
  "entry": 98.20,
  "stop": 98.03,
  "target": 98.52,
  "risk_reward": 1.88,
  "volume_confirmed": true
}
```
Setups: `ORB Long` | `ORB Short` | `Inside Range`

---

## 5. `postmarket_summarizer.py` — EOD Recap

```bash
python scripts/postmarket_summarizer.py MRVL
python scripts/postmarket_summarizer.py MSFT
python scripts/postmarket_summarizer.py HIMS
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "open": 95.49,
  "close": 98.42,
  "high": 98.81,
  "low": 94.00,
  "day_change_pct": 3.07,
  "total_volume": 19981868,
  "volume_ratio": 1.08,
  "vwap_close": 97.20,
  "close_vs_vwap": "ABOVE",
  "summary_text": "MRVL closed +3.07%, ABOVE VWAP, volume 1.1x avg"
}
```

---

## 6. `overnight_expert.py` — Overnight Risk Assessment

```bash
python scripts/overnight_expert.py MRVL
python scripts/overnight_expert.py NVDA
python scripts/overnight_expert.py TSLA
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "regular_close": 98.42,
  "ah_price": 96.79,
  "ah_change_pct": -1.66,
  "support": 85.13,
  "resistance": 98.82,
  "next_earnings_date": "2026-05-29",
  "earnings_tonight": false,
  "risk_level": "Medium"
}
```
Risk levels: `Low` | `Medium` | `High`

---

## 7. `fundamental_analyst.py` — Fundamentals & Valuation

```bash
python scripts/fundamental_analyst.py MRVL
python scripts/fundamental_analyst.py NVDA
python scripts/fundamental_analyst.py MSFT
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "name": "Marvell Technology, Inc.",
  "pe_ratio": 32.07,
  "forward_pe": 18.10,
  "revenue_growth": 0.221,
  "gross_margin": 0.510,
  "analyst_target": 120.50,
  "analyst_rating": "strong_buy",
  "valuation_grade": "Pricey",
  "growth_grade": "High growth",
  "earnings_risk": "LOW",
  "risk_flags": [],
  "summary_text": "Pricey (PE 32, Fwd PE 18) → Improving. High growth 22.1%. strong_buy → $120.50"
}
```

---

## 8. `earnings_expert.py` — Earnings Intelligence

```bash
python scripts/earnings_expert.py MRVL
python scripts/earnings_expert.py TSLA
python scripts/earnings_expert.py AAPL
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "current_price": 98.45,
  "next_earnings_date": "2026-05-29",
  "days_to_earnings": 64,
  "expected_move_pct": 4.72,
  "expected_move_dollar": 4.65,
  "avg_historical_move_pct": 12.59,
  "historical_reactions": [
    {"date": "2026-03-05", "move_pct": 18.35, "direction": "UP"},
    {"date": "2025-12-02", "move_pct": 7.87, "direction": "UP"},
    {"date": "2025-08-28", "move_pct": -18.59, "direction": "DOWN"}
  ],
  "iv_crush_risk": "LOW",
  "play_recommendation": "Directional trade based on technicals"
}
```

---

## 9. `timeframe_analyzer.py` — Multi-Timeframe Confluence

```bash
python scripts/timeframe_analyzer.py MRVL
python scripts/timeframe_analyzer.py TSLA
python scripts/timeframe_analyzer.py AMD
```

**Real output (MRVL):**
```json
{
  "ticker": "MRVL",
  "overall_bias": "BULLISH",
  "confluence": "HIGH",
  "confluence_score": "3/4",
  "timeframes": {
    "1m":  {"bias": "BULLISH", "rsi": 65.8, "macd": 0.08, "setup": "VWAP Bounce Long", "rr": 1.57},
    "5m":  {"bias": "NEUTRAL", "rsi": 56.2, "macd": 0.04},
    "15m": {"bias": "BULLISH", "rsi": 67.3, "macd": 0.90},
    "1D":  {"bias": "BULLISH", "rsi": 67.6, "macd": 3.13}
  },
  "recommendation": "Strong long — 3/4 TFs aligned. Wait for 5m to confirm.",
  "best_entry": "$98.44",
  "stop": "$97.99",
  "target": "$98.82"
}
```

---

## 10. `pattern_finder.py` — Chart Pattern Detection

```bash
python scripts/pattern_finder.py MRVL
python scripts/pattern_finder.py MU
python scripts/pattern_finder.py TSLA
```

**Real output (MRVL):**
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
    },
    {
      "pattern": "Rising Wedge",
      "bias": "BEARISH",
      "confidence": 65,
      "description": "Converging upward channel",
      "entry": 98.45,
      "stop": 98.82,
      "target": 75.24
    }
  ],
  "best_pattern": "Double Bottom (90%)",
  "overall_bias": "NEUTRAL",
  "summary_text": "Double Bottom detected (90% confidence). Neckline $81.34 broken"
}
```
Patterns: `Bull Flag` | `Bear Flag` | `Double Bottom` | `Double Top` | `Rising Wedge` | `Falling Wedge` | `Symmetrical Triangle`

---

## 11. `scanner.py` — Parallel Watchlist Scanner

```bash
python scripts/scanner.py                          # full 70-ticker watchlist
python scripts/scanner.py NVDA AMD AAPL META PLTR  # specific tickers
python scripts/scanner.py --mode full NVDA AMD     # with fundamentals
```

**Real output:**
```
🔍 Scanning 10 tickers (mode=vwap)...

🟢 MRVL   $   98.44 | BULLISH  | RSI   68 | VWAP Bounce Long   | R:R 1.57
🟢 AMD    $  220.28 | BULLISH  | RSI   61 | VWAP Bounce Long   | R:R 1.48
🟡 CRWV   $   87.60 | NEUTRAL  | RSI   54 | VWAP Bounce Long   | R:R 1.53
🔴 NVDA   $  178.67 | BEARISH  | RSI   46 | VWAP Bounce Short  | R:R 1.55
🔴 AAPL   $  252.65 | BEARISH  | RSI   43 | VWAP Bounce Short  | R:R 1.52

📊 10 tickers | 🟢 2 bullish | 🔴 4 bearish | 5 with active setup
```

---

## 12. `multi_analyze.py` — Multi-Ticker Deep Dive

```bash
python scripts/multi_analyze.py NVDA TSLA AAPL META PLTR
python scripts/multi_analyze.py MRVL CRWV HIMS --mode full
```

**Real output (quick mode):**
```
⚡ Analyzing 5 tickers in parallel...

🟢 MRVL $98.44 | BULLISH | RSI 68
   📐 VWAP Bounce Long | Entry $98.19 | Stop $98.05 | Target $98.41 | R:R 1.57
   • EMA9 above EMA21 — short-term bullish
   • Golden cross — long-term uptrend
   • MACD bullish crossover

🔴 NVDA $178.67 | BEARISH | RSI 46
   📐 VWAP Bounce Short | Entry $178.71 | Stop $178.91 | Target $178.40 | R:R 1.55
```

---

## 13. `orchestrator.py` — Natural Language Router

```bash
python scripts/orchestrator.py "analyze MRVL"
python scripts/orchestrator.py "earnings play on TSLA"
python scripts/orchestrator.py "how did HIMS do today"
python scripts/orchestrator.py "pre-market gap on ARM"
python scripts/orchestrator.py "timeframe analysis NVDA"
python scripts/orchestrator.py "chart patterns on MU"
python scripts/orchestrator.py "fundamentals of AAPL"
python scripts/orchestrator.py "overnight CRWV"
```

**Intent routing:**
| Query | Intent | Agents Called |
|-------|--------|--------------|
| "analyze X" | analyze | tech + vwap + news + calendar + timeframe + pattern |
| "news on X" | news | news_fetcher |
| "earnings X" | earnings | earnings_expert + calendar |
| "fundamentals X" | fundamental | fundamental_analyst + earnings |
| "pre-market X" | premarket | premarket_specialist + vwap |
| "opening range X" | open | market_open_scalper + vwap |
| "how did X today" | postmarket | postmarket_summarizer + technical |
| "overnight X" | overnight | overnight_expert + fundamental |
| "timeframe X" | timeframe | timeframe_analyzer |
| "chart patterns X" | pattern | pattern_finder |

---

## 14. `news_fetcher.py` — News Aggregator

```bash
python scripts/news_fetcher.py MRVL
python scripts/news_fetcher.py TSLA
python scripts/news_fetcher.py NVDA
```

---

## 15. `economic_calendar.py` — Earnings & Events

```bash
python scripts/economic_calendar.py MRVL
python scripts/economic_calendar.py TSLA
python scripts/economic_calendar.py NVDA
```
