# VWAP Setup Guide

## What is VWAP?

Volume Weighted Average Price (VWAP) is the average price weighted by volume for the session. It represents the "fair value" where institutions transact. Price above VWAP = buyers in control. Price below VWAP = sellers in control.

**Formula:**
```
VWAP = cumsum(typical_price * volume) / cumsum(volume)
typical_price = (high + low + close) / 3
```

**Bands** are standard deviations from VWAP, calculated using cumulative variance:
- Upper/Lower 1σ: ~68% of price action contained
- Upper/Lower 2σ: ~95% of price action contained

---

## Setup Types

### 1. VWAP Bounce Long

**Condition:** Price pulls back to VWAP from above and holds. Price stays above VWAP with buying pressure.

**Entry:** Just above VWAP (VWAP + 0.1σ)
**Stop:** Below VWAP (VWAP - 0.5σ)
**Target:** Upper 1σ band

**Confirmation:**
- Price touches or comes within 0.5% of VWAP
- Higher lows forming near VWAP
- Volume increasing on bounce candles
- EMA9 turning up near VWAP

**Best when:** Stock has been trending above VWAP all session and pulls back for the first time.

---

### 2. VWAP Bounce Short

**Condition:** Price rallies to VWAP from below and rejects. Price fails to reclaim VWAP.

**Entry:** Just below VWAP (VWAP - 0.1σ)
**Stop:** Above VWAP (VWAP + 0.5σ)
**Target:** Lower 1σ band

**Confirmation:**
- Price touches VWAP and forms a rejection candle (upper wick)
- Lower highs forming near VWAP
- Volume increasing on rejection
- EMA9 turning down near VWAP

**Best when:** Stock has been weak below VWAP and rallies on low volume.

---

### 3. VWAP Break Long

**Condition:** Price breaks above VWAP with strong volume. Clean break, not a wick.

**Entry:** Just above VWAP after break confirms (VWAP + 0.1σ)
**Stop:** Below VWAP (VWAP - 0.5σ)
**Target:** Upper 1σ band

**Confirmation:**
- Close above VWAP (not just a wick)
- Volume on break candle >110% of 20-bar average
- Follow-through candle holds above VWAP
- Previously below VWAP for multiple bars

**Best when:** Stock has been consolidating near VWAP with a catalyst or sector strength.

---

### 4. VWAP Break Short

**Condition:** Price breaks below VWAP with strong volume. Clean breakdown.

**Entry:** Just below VWAP after break confirms (VWAP - 0.1σ)
**Stop:** Above VWAP (VWAP + 0.5σ)
**Target:** Lower 1σ band

**Confirmation:**
- Close below VWAP (not just a wick)
- Volume on break candle >110% of 20-bar average
- Follow-through candle holds below VWAP
- Previously above VWAP for multiple bars

**Best when:** Stock loses VWAP in the first hour with heavy selling.

---

### 5. VWAP Reclaim

**Condition:** Price dips below VWAP, then quickly reclaims above. Failed breakdown.

**Entry:** Just above VWAP on reclaim (VWAP + 0.1σ)
**Stop:** Below VWAP (VWAP - 0.5σ)
**Target:** Upper 1σ band

**Confirmation:**
- Price was below VWAP for 3+ bars
- Reclaim happens with increasing volume
- "V-shape" recovery back above VWAP
- Short squeeze dynamics (rapid covering)

**Best when:** Morning dip that traps shorts, then strong reversal. Very powerful in the 10:00-10:30 AM window.

---

### 6. VWAP Rejection

**Condition:** Price breaks above VWAP, then fails back below. Failed breakout.

**Entry:** Just below VWAP on failure (VWAP - 0.1σ)
**Stop:** Above VWAP (VWAP + 0.5σ)
**Target:** Lower 1σ band

**Confirmation:**
- Price was above VWAP for 3+ bars
- Fails back below on increasing volume
- Upper wicks forming at/above VWAP
- Sellers stepping in at VWAP level

**Best when:** Weak stock tries to reclaim VWAP on low volume and fails.

---

### 7. Extended Short (Mean Reversion)

**Condition:** Price is >2σ above VWAP. Stretched, likely to revert.

**Entry:** At current price (fade)
**Stop:** 0.5σ above Upper 2σ band
**Target:** Upper 1σ band

**Confirmation:**
- Momentum weakening (smaller candles, wicks forming)
- Volume declining at highs
- RSI overbought (>70)
- Multiple upper wicks on recent candles

**Caution:** Do NOT fade strong momentum blindly. Wait for the stall.

---

### 8. Extended Long (Mean Reversion)

**Condition:** Price is <2σ below VWAP. Oversold, likely to bounce.

**Entry:** At current price (fade)
**Stop:** 0.5σ below Lower 2σ band
**Target:** Lower 1σ band

**Confirmation:**
- Selling pressure drying up (volume declining)
- Hammer/doji candles forming
- RSI oversold (<30)
- Approaching key daily support level

**Caution:** Do NOT catch falling knives. Wait for volume to dry up.

---

## Key Principles

1. **VWAP is institutional** — large funds use VWAP algorithms. Respect the level.
2. **First touch is best** — the first pullback to VWAP in a trend has the highest probability.
3. **Volume confirms** — always check volume on the setup. No volume = no conviction.
4. **Time of day matters** — VWAP is most reliable during RTH (9:30 AM - 4:00 PM ET). The first 15 minutes are noisy.
5. **VWAP resets daily** — it is a session indicator. Don't carry it overnight.
6. **Bands expand** — as the session progresses, bands widen. Early-session bands are tighter and more actionable.
7. **Context is king** — combine VWAP with the overall trend, sector strength, and catalysts.
