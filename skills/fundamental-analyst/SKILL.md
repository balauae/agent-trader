# Skill: Fundamental Analyst

**Agent:** `fundamental-analyst`
**Trigger:** Fundamental valuation, "fundamentals", "valuation", "PE ratio", "revenue growth", "analyst target", financial metrics

## Purpose

Provide fundamental valuation analysis — PE, growth metrics, margins, analyst ratings, and earnings risk — to complement technical setups with a fundamental perspective.

## How to Execute

### Step 1: Run Analysis

```bash
.venv/bin/python scripts/fundamental_analyst.py TICKER
```

Replace `TICKER` with the symbol (e.g., `AAPL`, `NVDA`).

The script fetches financial data, analyst estimates, and valuation metrics for the ticker.

### Step 2: Parse JSON Output

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "price": 122.30,
  "market_cap": "3.01T",
  "pe_ratio": 54.2,
  "forward_pe": 32.8,
  "peg_ratio": 1.15,
  "revenue_growth_yoy": 78.4,
  "earnings_growth_yoy": 108.2,
  "gross_margin": 74.6,
  "operating_margin": 61.2,
  "net_margin": 55.8,
  "analyst_rating": "Strong Buy",
  "analyst_target": 155.00,
  "target_upside_pct": 26.7,
  "num_analysts": 42,
  "next_earnings_date": "2026-05-28",
  "earnings_risk": "MODERATE",
  "notes": "Premium valuation justified by triple-digit earnings growth — forward PE more reasonable"
}
```

If the script returns an `"error"` key, report the error to the user.

### Step 3: Present as Trader-Friendly Analysis

Format the output like this:

```
FUNDAMENTAL ANALYST: NVDA
══════════════════════════════

VALUATION
  Price:      $122.30            Market Cap: $3.01T
  PE Ratio:   54.2x              Forward PE: 32.8x
  PEG Ratio:  1.15

GROWTH
  Revenue Growth (YoY):  +78.4%
  Earnings Growth (YoY): +108.2%

MARGINS
  Gross:     74.6%
  Operating: 61.2%
  Net:       55.8%

ANALYST CONSENSUS
  Rating:    Strong Buy (42 analysts)
  Target:    $155.00 (+26.7% upside)

EARNINGS
  Next Date: 2026-05-28
  Risk:      MODERATE

NOTES
  Premium valuation justified by triple-digit earnings growth — forward PE more reasonable
```

### Step 4: Add Context

After the formatted output:

- **PE < 15**: "Value territory — check if it's cheap for a reason (declining growth, sector headwinds)"
- **PE 15-30**: "Fairly valued — growth rate should justify the multiple"
- **PE > 30**: "Growth premium — forward PE and PEG ratio matter more than trailing PE"
- If `peg_ratio` < 1.0: "PEG below 1 — growth may be underpriced"
- If `peg_ratio` > 2.0: "PEG above 2 — priced for perfection, earnings misses will hurt"
- If `target_upside_pct` < 5: "Analyst target nearly reached — upside may be limited"
- If `target_upside_pct` > 30: "Large analyst upside — check if targets are stale or recent"
- If `earnings_risk` is HIGH: "Earnings approaching — fundamentals could shift significantly"

### Step 5: Fundamental Context Reminders

- PE ratio alone is misleading — always compare to growth rate (PEG) and sector peers
- Forward PE reflects expectations — a low forward PE with high trailing PE signals expected growth
- Analyst targets lag — check when consensus was last updated
- Margins trending down quarter-over-quarter is a red flag even if absolute levels look good
- Fundamentals set the floor/ceiling; technicals determine timing

## Error Handling

- If the script returns `"error"`, report it directly: "Could not analyze [TICKER]: [error message]"
- If data is unavailable for a metric, note "N/A" and explain (e.g., pre-revenue company)
- If the script fails entirely, suggest the user check data connectivity

## Coordination

- For **earnings-specific analysis**, hand off to `earnings-expert`
- For **technical setup** to time entries, coordinate with `technical-analyst` or `vwap-watcher`
- For **news catalysts** affecting fundamentals, coordinate with `news-fetcher`
- For **watchlist screening**, coordinate with `scanner`

## Reference

See [references/setups.md](references/setups.md) for detailed fundamental analysis definitions and examples.
