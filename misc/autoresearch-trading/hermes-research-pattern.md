# Hermes Research Pattern — Applied to TradeDesk

**Source:** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)  
**Cloned at:** `~/dev/apps/hermes-agent/`  
**Status:** Concept — implement after core TradeDesk is proven live

---

## What Hermes Research Does

Hermes runs an AI agent autonomously across hundreds of prompts overnight, captures every turn as a "trajectory" (reasoning + tool calls + results), scores the outcomes, and uses them to fine-tune the model. The model learns from its own real behavior — not human-written examples.

```
Prompts dataset (JSONL)
        ↓
BatchRunner: N parallel workers
        ↓
Each worker: AIAgent runs prompt autonomously
  → reasons step by step
  → uses tools (terminal, web, files)
  → completes task
        ↓
Trajectory = full conversation saved
  (prompt → reasoning → tool calls → answer)
        ↓
Score trajectories (did it succeed?)
        ↓
Fine-tune model on winning trajectories
        ↓
Better model → better trajectories → repeat
```

---

## Applied to TradeDesk

### The Dream

A model fine-tuned on **real trading analysis outcomes** — not generic data.
It learns which setups, reasoning patterns, and signals actually lead to profitable trades.

### The Loop

```
Phase 1 — Generate Trajectories
  Prompts = [
    "Analyze GLD technical setup for today",
    "Is NVDA a VCP breakout candidate?",
    "What is the Weinstein stage for ARM?",
    "Should I enter TSLA given current VWAP and S/R?",
    ...hundreds of prompts...
  ]
        ↓
  TradeDesk agent runs each overnight
  → calls technical.py, levels.py, vwap.py
  → reasons about setup quality
  → outputs buy/sell/pass decision + reasoning
        ↓
  Trajectories saved: trajectories.jsonl

Phase 2 — Score Outcomes
  After N days: did the trade work?
  Score = actual P&L of the suggested trade
  Keep trajectories where agent was RIGHT
  Discard trajectories where agent was WRONG

Phase 3 — Fine-tune
  Fine-tune a small local model (Mistral 7B, Llama 3.1 8B)
  on winning trajectories
  → Model learns which reasoning patterns predict good trades

Phase 4 — Deploy
  Replace generic Claude with fine-tuned TradeDesk model
  for analysis tasks (not for conversation)
  → Faster, cheaper, specialized
```

---

## What the Trajectory Looks Like

```json
{
  "conversations": [
    {
      "from": "human",
      "value": "Analyze GLD technical setup for today. Current price $415."
    },
    {
      "from": "assistant",
      "value": "<REASONING>\nGLD is near $415 resistance. Let me check S/R levels and VWAP...\n</REASONING>",
      "reasoning": "GLD at key resistance. Checking multi-timeframe..."
    },
    {
      "from": "tool_call",
      "value": "levels.py GLD 1D 200"
    },
    {
      "from": "tool_result",
      "value": "{\"key_levels\": [{\"price\": 415.0, \"strength\": 4, \"type\": \"resistance\"}...]}"
    },
    {
      "from": "assistant",
      "value": "GLD is testing $415 resistance (strength 4/5). VWAP at $412. Bias: short-term bearish unless $415 breaks. Setup: wait for break + retest above $415 before entering long."
    }
  ],
  "outcome": {
    "trade_taken": true,
    "entry": 416.50,
    "exit": 420.00,
    "pnl_pct": 0.84,
    "result": "WIN"
  },
  "score": 1.0
}
```

---

## Scoring Function

```python
def score_trajectory(trajectory, outcome):
    """
    Score a trading analysis trajectory based on actual outcome.
    
    Returns 0.0–1.0
    """
    if not outcome.get("trade_taken"):
        return 0.5  # Neutral — agent said pass, can't evaluate
    
    pnl = outcome.get("pnl_pct", 0)
    
    if pnl > 0.02:   return 1.0   # Strong win
    if pnl > 0:      return 0.7   # Small win
    if pnl > -0.01:  return 0.4   # Small loss
    return 0.0                     # Big loss — discard
```

---

## Infrastructure Needed

### Already Built ✅
- `scripts/analysis/technical.py` — technical analysis
- `scripts/analysis/levels.py` — S/R levels
- `scripts/indicators/core.py` — all math
- `scripts/feeds/vwap.py` — VWAP
- `data/alerts.db` — SQLite alert log (can record outcomes)
- Go watcher — real-time price data

### To Build
| Component | Description |
|-----------|-------------|
| `prompts/` | JSONL dataset of analysis prompts |
| `batch_runner.py` | Run agent on all prompts overnight |
| `trajectory_saver.py` | Save reasoning + tool calls per run |
| `outcome_tracker.py` | Record actual trade outcomes in alerts.db |
| `scorer.py` | Score trajectories by outcome |
| `fine_tuner.py` | Fine-tune Mistral 7B on winning trajectories |

---

## Parallel Subagent Mode (from Hermes delegate_task)

For watchlist analysis, use parallel subagents:

```
Parent: "Analyze today's watchlist"
    ↓
Subagent 1: "Analyze GLD"  ──┐
Subagent 2: "Analyze NVDA" ──┼── run in parallel
Subagent 3: "Analyze AMD"  ──┘
    ↓
Parent gets 3 summaries (zero intermediate context cost)
    ↓
Parent synthesizes: "Top setups today: GLD > NVDA > AMD"
```

Each subagent has:
- Own conversation (no parent context pollution)
- Own tool calls (terminal, scripts)
- Returns only final summary

---

## Why This Is the End Game

| Today | After Fine-tuning |
|-------|------------------|
| Claude (generic) analyzes GLD | TradeDesk-7B (specialized) analyzes GLD |
| $0.015/1K tokens | $0.001/1K tokens (local) |
| Generic reasoning | Trained on 10,000 real GLD setups |
| No memory of past setups | Knows which patterns worked historically |
| Can't improve | Gets better every week |

---

## Build Sequence (when ready)

1. **Collect 6 months of live data** — let watcher run, capture all alerts + outcomes
2. **Build prompt dataset** — 500+ analysis prompts with known outcomes
3. **Run BatchRunner** — generate trajectories overnight
4. **Score by P&L** — keep winners, discard losers
5. **Fine-tune Mistral 7B** — on winning trajectories
6. **Deploy** — replace Claude for analysis tasks, keep Claude for conversation

---

## References

- Hermes batch runner: `~/dev/apps/hermes-agent/batch_runner.py`
- Hermes delegate tool: `~/dev/apps/hermes-agent/tools/delegate_tool.py`
- Karpathy autoresearch: `~/dev/apps/autoresearch/`
- Our idea doc: `misc/autoresearch-trading/idea.md`
