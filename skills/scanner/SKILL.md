# Scanner Skill

## Description
Parallel watchlist scanner — scans multiple tickers simultaneously using ThreadPoolExecutor. Finds best VWAP setups, technical bias, and ranks by opportunity quality.

## Triggers
- "scan watchlist", "scan all", "find setups", "best setups right now"
- "what's moving", "full scan", "scan my watchlist"

## Usage
```bash
# Scan specific tickers (fast)
python scripts/scanner.py NVDA TSLA AAPL META AMD

# Scan full default watchlist (~35 tickers)
python scripts/scanner.py

# Full mode with fundamentals + earnings
python scripts/scanner.py --mode full NVDA TSLA AAPL
```

## Output
Ranked table sorted by: BULLISH above VWAP → BEARISH below VWAP

```
🟢 AMD    $220.28 | BULLISH  | RSI  61 | VWAP Bounce Long  | R:R 1.48
🔴 NVDA   $178.67 | BEARISH  | RSI  46 | VWAP Bounce Short | R:R 1.55
📊 6 tickers | 🟢 2 bullish | 🔴 4 bearish | 5 with active setup
```

## Key Fields
- Bias: BULLISH / BEARISH / NEUTRAL (from technical analysis)
- RSI: momentum indicator
- Setup: VWAP setup type detected
- R:R: risk/reward ratio for the setup

## Notes
- Uses parallel execution — 35 tickers in ~15-20 seconds
- Mode `vwap` = fastest (VWAP + Technical only)
- Mode `full` = adds Fundamental + Earnings data (~45s)
