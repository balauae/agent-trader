# Idea: AutoResearch for Trading Strategies

**Status:** Concept  
**Priority:** Medium (build after Monday live test passes)  
**Inspired by:** [karpathy/autoresearch](https://github.com/karpathy/autoresearch)  
**Repo cloned at:** `~/dev/apps/autoresearch/`

---

## The Core Idea

Karpathy's autoresearch = AI agent autonomously experiments with LLM training code overnight.
Keeps improvements (git commit), discards failures (git reset). 100 experiments while you sleep.

**Our version:** AI agent autonomously experiments with trading strategy rules overnight.
Keeps strategies with better Sharpe ratio, discards losers. Wake up to the best strategy it found.

---

## Karpathy's Methodology (what we're borrowing)

```
LOOP FOREVER:
  1. Have an idea → edit strategy.py
  2. git commit
  3. Run backtest → measure Sharpe ratio
  4. If improved → KEEP (advance branch)
  5. If worse → DISCARD (git reset)
  6. Log to results.tsv
  7. Repeat until human interrupts
```

Key design decisions to borrow:
- **Single metric** — one clear objective (Sharpe ratio or expectancy)
- **Fixed backtest window** — all experiments comparable
- **One file to edit** — manageable scope, reviewable diffs
- **git as memory** — branch = best strategy DNA so far
- **Never stop** — agent works overnight autonomously
- **Simplicity criterion** — improvement must justify complexity added

---

## How It Maps to Trading

| autoresearch | TradeDesk AutoResearch |
|-------------|----------------------|
| `train.py` | `strategy.py` — entry/exit/sizing rules |
| `val_bpb` (lower=better) | Sharpe ratio (higher=better) |
| 5-min training budget | 1-year backtest window |
| H100 GPU required | Just CPU + historical data (runs on laptop!) |
| `program.md` | Agent instructions: what strategies to try |
| `results.tsv` | Strategy performance log |
| git branch per run | Strategy version per experiment |

---

## What the Agent Would Experiment With

Each experiment tweaks one thing in `strategy.py`:

```python
# Entry rules
ENTRY_SIGNAL = "vwap_reclaim"  # try: sr_bounce, vcp_breakout, rsi_reversal
ENTRY_TIMEFRAME = "5min"       # try: 1min, 15min, 1h

# Exit rules  
STOP_ATR_MULT = 1.5            # try: 1.0, 2.0, 2.5
TARGET_RR = 2.0                # try: 1.5, 2.5, 3.0
TRAIL_STOP = False             # try: True

# Filters
MIN_VOLUME_MULT = 1.5          # try: 1.0, 2.0
REQUIRE_TREND = True           # try: False
WEINSTEIN_STAGE = 2            # try: None (no filter)

# Position sizing
RISK_PCT = 0.01                # try: 0.005, 0.02
MAX_POSITIONS = 3              # try: 1, 5
```

---

## The Metric

**Primary:** Sharpe ratio (annualized) — risk-adjusted returns
**Secondary:** 
- Win rate (%)
- Expectancy (avg $ per trade)
- Max drawdown (%)
- Total return (%)

```python
def evaluate(trades):
    returns = [t.pnl_pct for t in trades]
    sharpe = mean(returns) / std(returns) * sqrt(252)
    return sharpe
```

---

## Data Sources

- **Historical OHLCV:** Yahoo Finance (free, 5yr history)
- **Tickers:** Bala's watchlists from USER.md
- **S/R levels:** Pre-computed from support_resistance.py
- **Indicators:** scripts/indicators/core.py (RSI, VWAP, ATR, etc.)

No TV needed for backtesting — yfinance is fine for historical data.

---

## File Structure (when we build it)

```
misc/autoresearch-trading/
  idea.md              ← this file
  program.md           ← agent instructions (what to try)
  strategy.py          ← the file the agent edits
  backtest.py          ← fixed backtest engine (never modified)
  evaluate.py          ← fixed evaluation (Sharpe, drawdown, etc.)
  results.tsv          ← experiment log (gitignored)
  data/                ← cached historical data (gitignored)
```

---

## Why This Is Powerful

1. **No GPU needed** — backtesting is pure math
2. **Overnight runs** — 100 experiments while you sleep
3. **Proven methodology** — directly from Karpathy
4. **Our data** — uses Cherif's S/R levels as inputs
5. **Explainable** — every strategy is readable Python rules
6. **Compounding** — each day the strategy gets better

---

## Build Sequence (when ready)

1. `backtest.py` — fixed engine, takes strategy params, returns trades list
2. `evaluate.py` — fixed metric (Sharpe ratio)
3. `strategy.py` — baseline strategy (VWAP reclaim + ATR stop)
4. `program.md` — agent instructions
5. Run overnight → review `results.tsv` in morning

---

## References

- Karpathy repo: `~/dev/apps/autoresearch/`
- GitHub: https://github.com/karpathy/autoresearch
- Tweet: https://x.com/karpathy/status/2029701092347630069
