# TradeDesk-7B Training Plan

**Status:** Concept — start after core system proven live  
**Revised timeline:** 2–4 weeks (not 12 months) using historical data

---

## The Goal

A fine-tuned LLM that replaces the generic Claude for trading analysis decisions.

```
TODAY:
  Market data → Claude (generic, expensive, slow) → decision

FUTURE:
  Market data → TradeDesk-7B (specialized, cheap, fast) → decision
                      +
               Claude (judge, deep analysis on top 3 only)
```

---

## Data Strategy — Use Historical Data

### Why Not Wait for Live Data?
- 12 months to collect enough live trades
- Historical data gives 5 years instantly
- Same quality if handled correctly (no leakage)

### The Approach
```
Yahoo Finance / TradingView historical OHLCV
  5 years × 50 tickers = 250,000 daily bars
        ↓
Simulate: "What would TradeDesk have said on date X about ticker Y?"
  → Run analysis scripts on that day's data
  → Record: entry signal, stop, target, reasoning
  → Check what price did next 1–5 days
  → Label: WIN / LOSS / PASS
        ↓
10,000+ labeled trajectories in 2–3 days
        ↓
Fine-tune on labeled winners
```

### Why This Works
The model never sees future data during training — it only sees what was available on that exact date. The outcome (WIN/LOSS) is the label, not a feature.

---

## Data Split (Prevent Leakage)

```
2020 ──── 2021 ──── 2022 ──── 2023 | 2024 ──── 2025
│←────── TRAINING DATA ────────────│←── TEST DATA ──→│
```

**Walk-forward validation (best practice):**
```
Round 1: Train 2020-2022 → Test 2023
Round 2: Train 2020-2023 → Test 2024
Round 3: Train 2020-2024 → Test 2025
Average Sharpe across rounds = honest estimate
```

**Rule: Never test on data the model was trained on. Ever.**

---

## Trajectory Format

Each training example = one trading decision:

```json
{
  "input": {
    "ticker": "GLD",
    "date": "2023-03-15",
    "price": 182.50,
    "vwap": 180.20,
    "rsi": 65,
    "support": [{"zone": "$178-180", "strength": 4}],
    "resistance": [{"zone": "$185-187", "strength": 3}],
    "weinstein_stage": 2,
    "volume_ratio": 1.4,
    "session": "intraday"
  },
  "reasoning": "GLD in Stage 2 uptrend. Price above VWAP by 1.3%. RSI 65 — momentum but not overbought. Support at $178-180 is strong (4/5). Resistance at $185-187 is next target. R/R = 2.5:1. Setup quality: HIGH.",
  "decision": {
    "action": "LONG",
    "entry": 183.00,
    "stop": 179.50,
    "target": 186.00,
    "rr_ratio": 2.14,
    "confidence": 0.75,
    "position_size_pct": 0.01
  },
  "outcome": {
    "price_5d_later": 186.50,
    "pnl_pct": 0.84,
    "result": "WIN"
  },
  "score": 1.0
}
```

---

## Scoring Function

```python
def score_trajectory(outcome):
    pnl = outcome["pnl_pct"]
    
    if not outcome["trade_taken"]:
        return 0.5   # PASS — can't evaluate, neutral
    if pnl > 0.03:   return 1.0   # Strong win (>3%)
    if pnl > 0.01:   return 0.8   # Good win (1-3%)
    if pnl > 0:      return 0.6   # Small win
    if pnl > -0.01:  return 0.3   # Small loss
    return 0.0                     # Big loss — discard
```

Only trajectories with score ≥ 0.6 used for training.

---

## Full Architecture

```
┌─────────────────────────────────────────────────┐
│                 DATA LAYER                      │
│  TradingView + Cherif PDF + News + Options flow │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│         FAST FILTER (TradeDesk-7B)              │
│  Scans 20 stocks in <2 seconds                 │
│  Output: Top 3 setups + confidence scores      │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│          DEEP ANALYSIS (Claude)                 │
│  Full reasoning on top 3 only                  │
│  Cross-check: macro, news, risk                │
│  Output: Final entry/stop/size                 │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│            EXECUTION LAYER                      │
│  Go watcher: real-time price monitoring        │
│  Alert when entry level hit                    │
│  You confirm → trade                           │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│            LEARNING LOOP                        │
│  AutoResearch agent records outcome            │
│  Scores trajectory                             │
│  Weekly fine-tune                              │
│  Model improves                                │
└─────────────────────────────────────────────────┘
```

---

## Build Sequence

### Phase 1 — Historical Data Collection (Week 1)
```bash
# Fetch 5 years OHLCV for all watchlist tickers
python misc/autoresearch-trading/collect_historical.py

# Tickers: all from USER.md watchlists (~50 tickers)
# Data: daily OHLCV, 2020-2025
# Source: Yahoo Finance (free)
```

### Phase 2 — Trajectory Generation (Week 1-2)
```bash
# Simulate TradeDesk analysis on every historical date
python misc/autoresearch-trading/generate_trajectories.py \
  --tickers GLD,NVDA,TSLA,AMD,META,AAPL... \
  --start 2020-01-01 --end 2023-12-31 \
  --output data/trajectories_train.jsonl

# Target: 10,000+ labeled examples
```

### Phase 3 — Fine-tune (Week 2)
```bash
# Fine-tune Mistral 7B on winning trajectories
# Base model: mistralai/Mistral-7B-Instruct-v0.3
# Framework: Unsloth (fast, low VRAM)
# GPU: single RTX 4090 or cloud (RunPod ~$20)
python misc/autoresearch-trading/fine_tune.py \
  --train data/trajectories_train.jsonl \
  --model mistral-7b \
  --output models/tradedesk-7b-v1
```

### Phase 4 — Validate (Week 2-3)
```bash
# Test on held-out 2024-2025 data
python misc/autoresearch-trading/validate.py \
  --model models/tradedesk-7b-v1 \
  --test data/trajectories_test.jsonl

# Target metrics:
# Sharpe ratio > 1.0
# Win rate > 55%
# Max drawdown < 15%
```

### Phase 5 — Deploy (Week 3-4)
```bash
# Run locally via Ollama
ollama create tradedesk-7b -f models/tradedesk-7b-v1/Modelfile

# Wire into bridge
# GET /analyze/fast/{ticker} → uses TradeDesk-7B
# GET /analyze/deep/{ticker} → uses Claude (top 3 only)
```

---

## Dedicated AutoResearch Agent

A lightweight cron-based agent that runs nightly:

```
11:00 PM AbuDhabi (market closed):
  1. Pull today's price data for all watchlist tickers
  2. For each ticker: run analysis, record decision + reasoning
  3. Check yesterday's decisions vs actual price movement
  4. Score outcomes, append to trajectories.jsonl
  5. If dataset > 1000 new entries → trigger fine-tune job
```

This agent uses the **same methodology as Hermes BatchRunner** but trading-specific:
- Fixed evaluation metric: Sharpe ratio (not val_bpb)
- Domain-specific prompts: S/R levels, VWAP, Weinstein stage
- Outcome tracking: actual P&L (not model loss)

---

## v1 Limitations (acceptable)

Historical data won't include:
- ❌ Cherif's daily notes (only 3 PDFs so far)
- ❌ Real-time news sentiment
- ❌ Options flow / dark pool data

v1 will use:
- ✅ OHLCV (Yahoo Finance)
- ✅ VWAP, RSI, MACD, ATR (computed)
- ✅ S/R levels (computed via levels.py)
- ✅ Weinstein stage (computed)
- ✅ Volume patterns

Add Cherif data to v2 as we accumulate more PDFs.

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Sharpe ratio (2024-2025 test) | > 1.0 |
| Win rate | > 55% |
| Max drawdown | < 15% |
| Avg R/R ratio | > 1.8:1 |
| Inference speed | < 500ms |
| Cost per analysis | < $0.001 |

If test metrics pass → deploy to production alongside Claude.

---

## References

- Hermes research pattern: `misc/autoresearch-trading/hermes-research-pattern.md`
- Karpathy autoresearch: `~/dev/apps/autoresearch/`
- Hermes agent: `~/dev/apps/hermes-agent/`
- Our scripts: `scripts/analysis/`, `scripts/indicators/core.py`
- Watchlists: `USER.md`
