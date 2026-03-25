# Indicator Formulas & Signal Thresholds

Reference for the technical-analyst skill. All indicators are computed with pure pandas — no ta-lib.

## Moving Averages

### EMA (Exponential Moving Average)
- **Formula:** EMA_t = price_t * k + EMA_{t-1} * (1 - k), where k = 2 / (period + 1)
- **Periods used:** 9, 21
- **Signals:**
  - EMA9 > EMA21 = short-term bullish
  - EMA9 < EMA21 = short-term bearish
  - Crossover (EMA9 crosses above EMA21) = bullish crossover signal

### SMA (Simple Moving Average)
- **Formula:** SMA = sum(close, period) / period
- **Periods used:** 50, 200
- **Signals:**
  - SMA50 > SMA200 = golden cross territory (institutional bullish)
  - SMA50 < SMA200 = death cross territory (institutional bearish)
  - Price above SMA200 = long-term uptrend
  - Price below SMA200 = long-term downtrend

## MACD (Moving Average Convergence Divergence)

- **Parameters:** fast=12, slow=26, signal=9
- **Formula:**
  - MACD Line = EMA(12) - EMA(26)
  - Signal Line = EMA(9) of MACD Line
  - Histogram = MACD Line - Signal Line
- **Signals:**
  - Histogram > 0 = bullish momentum
  - Histogram < 0 = bearish momentum
  - MACD Line > Signal = bullish crossover
  - MACD Line < Signal = bearish crossover
  - Histogram increasing = momentum accelerating
  - Histogram decreasing = momentum fading

## RSI (Relative Strength Index)

- **Period:** 14
- **Formula:** RSI = 100 - (100 / (1 + RS)), where RS = avg_gain / avg_loss (Wilder smoothing)
- **Thresholds:**
  - RSI >= 70 = **overbought** (potential reversal / pullback)
  - RSI <= 30 = **oversold** (potential bounce)
  - RSI 60-70 = bullish zone
  - RSI 30-40 = bearish zone
  - RSI 40-60 = neutral

## Bollinger Bands

- **Parameters:** period=20, std_dev=2
- **Formula:**
  - Middle Band = SMA(20)
  - Upper Band = SMA(20) + 2 * StdDev(20)
  - Lower Band = SMA(20) - 2 * StdDev(20)
- **Signals:**
  - Price at upper band = possible resistance / overbought
  - Price at lower band = possible support / oversold
  - Band width < 4% of mid = **squeeze** (volatility expansion imminent)
  - Band expansion after squeeze = breakout likely

## ATR (Average True Range)

- **Period:** 14
- **Formula:**
  - True Range = max(high-low, |high-prev_close|, |low-prev_close|)
  - ATR = Wilder smoothing (EMA with alpha=1/period) of True Range
- **Usage:**
  - Stop loss = 1.5x ATR from entry (long: below, short: above)
  - Measures volatility — higher ATR = wider stops needed

## VWAP (Volume Weighted Average Price)

- **Scope:** Session-only (intraday: 1m, 5m, 15m, 30m)
- **Formula:** VWAP = cumsum(typical_price * volume) / cumsum(volume), where typical_price = (H+L+C)/3
- **Signals:**
  - Price > VWAP = intraday bullish (institutional buying)
  - Price < VWAP = intraday bearish (institutional selling)
- **Note:** Not computed for daily/weekly timeframes

## Volume SMA

- **Period:** 20
- **Signal:**
  - Current volume > SMA(20) = above average — move has participation
  - Current volume < SMA(20) = below average — weak conviction

## Confluence Scoring (X/5)

Five checks, each worth 1 point toward bullish:

| # | Check | Bullish if |
|---|-------|------------|
| 1 | EMA alignment | EMA9 > EMA21 |
| 2 | MACD | Histogram > 0 |
| 3 | RSI | RSI > 50 |
| 4 | Trend (SMA200 or SMA50) | Price > reference MA |
| 5 | VWAP (intraday) or BB position (daily) | Price > VWAP or price > BB mid |

**Interpretation:**
- **4-5/5:** Strong confluence — high-conviction setup
- **3/5:** Mixed — wait for confirmation or reduce size
- **0-2/5:** Weak/bearish — no clear bullish edge
