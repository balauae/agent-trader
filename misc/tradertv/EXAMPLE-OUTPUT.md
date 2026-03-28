# TraderTV Parser — Example Output

## Usage

```bash
# JSON output (for downstream processing)
.venv/bin/python misc/tradertv/parser.py misc/tradertv/sample3.pdf

# Text output (raw, readable, as-is from PDF)
.venv/bin/python misc/tradertv/parser.py misc/tradertv/sample3.pdf --format text

# Filter to specific tickers
.venv/bin/python misc/tradertv/parser.py misc/tradertv/sample3.pdf --format text --watchlist GLD,ARM,AAPL
```

---

## JSON Output (single stock — GLD)

```json
{
  "ticker": "GLD",
  "headline": "Gold Rebounds as Oil Drops & Geopolitical Risk Shifts",
  "bias": "BULLISH",
  "bias_detail": "Bias: Short-term bounce within a broader downtrend, not a confirmed reversal yet. Price reclaiming near-term momentum but still below key moving averages — neutral to slightly bullish. Bias favors continuation higher toward $425 if $405 holds, but failure below support shifts back to trend continuation lower",
  "support": [
    {
      "low": 405.0,
      "high": 407.0,
      "zone": "$405.0–$407.0",
      "notes": "Current consolidation base; holding here keeps bounce intact"
    },
    {
      "low": 395.0,
      "high": 398.0,
      "zone": "$395.0–$398.0",
      "notes": "Recent panic low and strong reversal zone; key downside pivot"
    },
    {
      "low": 385.0,
      "high": 390.0,
      "zone": "$385.0–$390.0",
      "notes": "Extreme flush area; loss here would confirm broader breakdown continuation"
    }
  ],
  "resistance": [
    {
      "low": 418.0,
      "high": 420.0,
      "zone": "$418.0–$420.0",
      "notes": "Immediate breakout zone; current test area after bounce"
    },
    {
      "low": 425.0,
      "high": 428.0,
      "zone": "$425.0–$428.0",
      "notes": "Prior lower high + MA resistance; key for trend shift"
    },
    {
      "low": 435.0,
      "high": 440.0,
      "zone": "$435.0–$440.0",
      "notes": "Major supply zone; reclaim needed for sustained upside move"
    }
  ],
  "trader_takeaway": "Gold is trading the intersection of macro and geopolitics right now. The drop in oil is easing inflation fears, which helps gold, but rising rates still cap upside. Add in mixed signals from the Middle East, and you get a market that's reacting quickly to headlines rather than trending cleanly. For traders, this is a tactical bounce setup, not a full trend reversal — unless price can reclaim higher resistance levels. The bigger picture remains constructive long-term, but short-term price action is still range-to-downtrend biased until proven otherwise.",
  "news_bullets": [
    "🛢️ Oil Decline Eases Inflation Pressure",
    "● Gold moved higher as oil prices dropped sharply (Brent -5%, WTI -4%),",
    "reducing near-term inflation concerns.",
    "● Lower energy prices help ease pressure on central banks, supporting",
    "non-yielding assets like gold.",
    "● Spot gold rose +1.6% to ~$4,548, while futures gained +3%, showing",
    "strong momentum.",
    "● Move reflects shifting macro expectations rather than a pure safe-haven",
    "panic bid.",
    "🌍 Geopolitical Developments & Mixed Signals",
    "● Trump indicated the U.S. and Iran are \"in negotiations\", backing off",
    "potential energy infrastructure strikes.",
    "● Iran denied direct talks, keeping uncertainty elevated despite de-escalation",
    "headlines.",
    "● Tehran confirmed conditional passage through the Strait of Hormuz, easing immediate supply",
    "fears.",
    "● Markets reacting to headline-driven shifts, not a confirmed resolution.",
    "📉 Dollar & Rates Impact",
    "● U.S. dollar index slipped -0.17%, providing additional support for gold prices.",
    "● However, rising interest rate expectations remain a headwind for gold demand, especially via ETFs.",
    "● Goldman notes gold is highly rate-sensitive, with higher yields reducing its relative appeal.",
    "● Recent gold weakness partly tied to these macro factors, not just geopolitical changes.",
    "📊 Positioning & Structural Outlook",
    "● Gold still down ~-17% from January highs, indicating prior rally overshot fundamentals.",
    "● Recent pullback seen as \"normalization\" after an extended move higher.",
    "● Despite short-term volatility, Goldman maintains bullish outlook with $5,400 target by year-end.",
    "● Central bank buying remains a key structural driver, as countries diversify reserves."
  ]
}
```

---

## Text Output (single stock — GLD)

```
GLD — Gold Rebounds as Oil Drops & Geopolitical Risk Shifts
--------------------------------------------------
🛢️ Oil Decline Eases Inflation Pressure
● Gold moved higher as oil prices dropped sharply (Brent -5%, WTI -4%),
reducing near-term inflation concerns.
● Lower energy prices help ease pressure on central banks, supporting
non-yielding assets like gold.
● Spot gold rose +1.6% to ~$4,548, while futures gained +3%, showing
strong momentum.
● Move reflects shifting macro expectations rather than a pure safe-haven
panic bid.
🌍 Geopolitical Developments & Mixed Signals
● Trump indicated the U.S. and Iran are "in negotiations", backing off
potential energy infrastructure strikes.
● Iran denied direct talks, keeping uncertainty elevated despite de-escalation
headlines.
● Tehran confirmed conditional passage through the Strait of Hormuz, easing immediate supply
fears.
● Markets reacting to headline-driven shifts, not a confirmed resolution.
📉 Dollar & Rates Impact
● U.S. dollar index slipped -0.17%, providing additional support for gold prices.
● However, rising interest rate expectations remain a headwind for gold demand, especially via ETFs.
● Goldman notes gold is highly rate-sensitive, with higher yields reducing its relative appeal.
● Recent gold weakness partly tied to these macro factors, not just geopolitical changes.
📊 Positioning & Structural Outlook
● Gold still down ~-17% from January highs, indicating prior rally overshot fundamentals.
● Recent pullback seen as "normalization" after an extended move higher.
● Despite short-term volatility, Goldman maintains bullish outlook with $5,400 target by year-end.
● Central bank buying remains a key structural driver, as countries diversify reserves.

Support:
  $405.0–$407.0 — Current consolidation base; holding here keeps bounce intact
  $395.0–$398.0 — Recent panic low and strong reversal zone; key downside pivot
  $385.0–$390.0 — Extreme flush area; loss here would confirm broader breakdown continuation

Resistance:
  $418.0–$420.0 — Immediate breakout zone; current test area after bounce
  $425.0–$428.0 — Prior lower high + MA resistance; key for trend shift
  $435.0–$440.0 — Major supply zone; reclaim needed for sustained upside move

Bias: Short-term bounce within a broader downtrend, not a confirmed reversal yet. Price reclaiming
near-term momentum but still below key moving averages — neutral to slightly bullish. Bias favors
continuation higher toward $425 if $405 holds, but failure below support shifts back to trend
continuation lower

Trader Takeaway: Gold is trading the intersection of macro and geopolitics right now. The drop in
oil is easing inflation fears, which helps gold, but rising rates still cap upside. Add in mixed
signals from the Middle East, and you get a market that's reacting quickly to headlines rather than
trending cleanly. For traders, this is a tactical bounce setup, not a full trend reversal — unless
price can reclaim higher resistance levels. The bigger picture remains constructive long-term, but
short-term price action is still range-to-downtrend biased until proven otherwise.
```

---

## Sample PDFs (Mar 2026)

| File | Date | Stocks |
|------|------|--------|
| `sample_Mar27.pdf` | Mar 27, 2026 | 17 — META, AMZN, MSFT, MU, NFLX, WBD, TGT, SMCI, KWEB, U, SNPS, MA, RTX, USO... |
| `sample2.pdf` | Mar 26, 2026 | 15 — META, GOOGL, UBER, MU, SMCI, CRWD, BABA, QCOM, JBLU... |
| `sample3.pdf` | Mar 25, 2026 | 19 — META, AAPL, GOOGL, ARM, MU, USO, GLD, GME, KBH, PDD, CHWY, MRK, ONON, SHOP, HOOD, SPCE, CIFR... |

---

## Design Principle

> **Parser = faithful extraction only. No summarizing. No trimming. No decisions.**
>
> Every word Cherif wrote goes into the JSON exactly as-is.
> Downstream consumers (LLM, setup_finder.py, Telegram formatter) decide what to surface.
