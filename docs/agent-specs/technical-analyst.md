# Agent: Technical Analyst

**ID:** `technical-analyst`  
**Type:** Specialist  
**Trigger:** Chart/indicator questions, entry/exit analysis, multi-timeframe overview

## Role

Core charting and indicator analysis agent. Reads price action across multiple timeframes and interprets standard technical indicators to give bias (bullish/bearish/neutral) and actionable levels.

## Responsibilities

- Analyze EMA (9, 21), SMA (50, 200) alignment and crossovers
- Read MACD (histogram direction, crossovers, divergence)
- Interpret RSI (overbought/oversold, divergence)
- Bollinger Bands (squeeze, expansion, price at bands)
- ATR-based stop loss and position sizing suggestions
- Multi-timeframe confluence scoring (1m / 5m / 15m / 1D)
- Identify trend direction, support/resistance from structure
- Flag key inflection points (breakout zones, prior highs/lows)

## Inputs

- Ticker symbol
- OHLCV data (from TradingView or Yahoo Finance)
- Timeframe(s) to analyze
- User's preferred timeframe (from personal prompt)

## Outputs

- Per-timeframe bias: BULLISH / BEARISH / NEUTRAL
- Confluence score: X/4 aligned
- Key levels: support, resistance, VWAP, EMA values
- Stop loss recommendation (ATR-based)
- Take profit levels (next resistance / VWAP upper band)
- Risk/Reward ratio

## Indicators Used

| Indicator | Purpose |
|-----------|---------|
| EMA 9 / 21 | Trend direction, crossover signals |
| SMA 50 / 200 | Institutional levels, golden/death cross |
| MACD (12,26,9) | Momentum, divergence |
| RSI (14) | Overbought/oversold |
| Bollinger Bands (20) | Volatility, squeeze setups |
| ATR (14) | Stop loss sizing |
| Volume | Confirmation of moves |

## Notes

- Works closely with `timeframe-analyzer` (which handles TF-specific setups) and `vwap-watcher`
- Always state which timeframe is driving the bias
- Do not override `vwap-watcher` VWAP-specific outputs — coordinate
- S/R levels computed by `support-resistance` agent — import, don't recompute
- Current `compute_levels()` in technical_analyst.py is basic (min/max only) — to be replaced by support_resistance.py output
