# Idea: TraderTV Daily PDF Parser

**Status:** Concept — PDF format analyzed ✅  
**Priority:** Low (adhoc)  
**Folder:** `misc/tradertv/`  
**Sample PDF:** `misc/tradertv/sample_Mar27.pdf` (Mar 27, 2026)

---

## What

TraderTV Live posts a daily pre-market PDF ("Cherif's Morning Note") via YouTube community tab. Each PDF contains 15–20 pages of stock analysis with:
- News catalyst per stock
- Exact support/resistance price levels
- Implied bias (bullish/bearish) from context

---

## PDF Format (confirmed from sample)

### Structure
- **Page 1:** Table of contents — stock name + page number
- **Pages 2–18:** One stock per page

### Each Page Layout
```
[STOCK NAME + HEADLINE]
[News summary — 3–4 bullet points]     |  Support:
                                        |  $XXX – $XXX — description
                                        |  $XXX – $XXX — description
                                        |  
                                        |  Resistance:
                                        |  $XXX – $XXX — description
                                        |  $XXX – $XXX — description
```
Two-column layout: news on left, levels on right.

### Tickers in sample (Mar 27)
META, AMZN, MSFT, USO (oil), MU, NFLX, WBD, TGT, SMCI, BABA

### Example extracted data
```json
{
  "ticker": "META",
  "headline": "Meta Legal Risk Escalates After Dual Jury Verdicts",
  "bias": "BEARISH",
  "bias_detail": "Intraday structure decisively bearish. Price below key MAs. $555-560 key pivot. Hold $540 critical.",
  "support": [
    {"zone": "540-545", "low": 540, "high": 545, "notes": "Current base after sharp selloff"},
    {"zone": "530-535", "low": 530, "high": 535, "notes": "Prior flush zone"},
    {"zone": "515-520", "low": 515, "high": 520, "notes": "Lower extension support"}
  ],
  "resistance": [
    {"zone": "555-560", "low": 555, "high": 560, "notes": "Immediate resistance"},
    {"zone": "575-580", "low": 575, "high": 580, "notes": "Prior consolidation"},
    {"zone": "600-605", "low": 600, "high": 605, "notes": "Major overhead supply"}
  ],
  "trader_takeaway": "Structural legal risk reshaping social media model. Weak chart + headline overhang. Path of least resistance lower."
}
```

---

## Pipeline

```
Google Drive PDF link (from YouTube community post)
        ↓
curl download (public link — no auth needed ✅)
        ↓
pdfplumber → extract text per page
        ↓
Parse: ticker from headline, levels from right column
        ↓
Cross-reference with Bala's watchlist
        ↓
Output JSON + Telegram summary
```

---

## Key Findings from Sample

1. **PDF is publicly accessible** — direct curl download works ✅
2. **18 pages** — one stock per page after TOC
3. **Consistent format** — same layout every day (confirmed)
4. **pdfplumber works** — text extraction clean ✅
5. **Levels always labeled** "Support:" and "Resistance:" — easy to parse
6. **No login needed** for Google Drive link

---

## Parsing Strategy

```python
# Page 1 = TOC, skip
# Pages 2+ = one stock each

for page in pdf.pages[1:]:
    text = page.extract_text()
    
    # Ticker: first line / headline contains stock name
    # e.g. "Meta Legal Risk..." → META from context or explicit mention
    
    # Support levels: text after "Support:"
    # Pattern: $XXX.XX – $XXX.XX — description
    
    # Resistance levels: text after "Resistance:"
    # Same pattern
    
    # Bias: infer from headline keywords
    # "Drops", "Freeze", "Risk", "Bearish" → BEARISH
    # "Surges", "Ramps", "Breaks out" → BULLISH
```

---

## Open Questions

1. **How to get the daily link?** — YouTube community post has Drive link
   - Option A: YouTube Data API v3 (free) — get latest community post
   - Option B: yt-dlp scrape (no API key needed)
   - Option C: Bala manually pastes link (simplest to start)

2. **What time does Cherif post?** — Need to know for cron timing

---

## Implementation Phases

### Phase 1 — Parser (ready to build)
```bash
python misc/tradertv/parser.py misc/tradertv/sample_Mar27.pdf
# Output: JSON with all tickers, levels, bias
```

### Phase 2 — Fetcher
```python
# misc/tradertv/fetcher.py
# Given a Drive link → download PDF → return path
```

### Phase 3 — Watchlist cross-reference
```python
# Check if any parsed tickers are in USER.md watchlists
# Alert if GLD or current positions mentioned
```

### Phase 4 — Telegram summary
```
📰 TraderTV Morning Note (Mar 31)
Watchlist mentions: NVDA, MU, META

🔴 MU — Bearish: Support $345–347, Resistance $352–355
🟢 NVDA — Bullish: Support $165–167, Resistance $171–172
```

### Phase 5 — Cron (daily pre-market)
```
Daily 11:30 AM AbuDhabi → fetch → parse → send Telegram
```

---

## Dependencies
```bash
uv pip install pymupdf  # ✅ already installed — faster + cleaner than pdfplumber
# yt-dlp (optional — for auto-fetch)
```

## Why PyMuPDF over pdfplumber
- Extracts two-column layouts correctly (news + levels side by side)
- Includes **Bias** section at bottom of each page (explicit bullish/bearish + reasoning)
- Faster parsing
- `import fitz` — `doc[i].get_text()`

---

## Files
```
misc/tradertv/
  idea.md              ← this file
  sample_Mar27.pdf     ← sample PDF for testing
  parser.py            ← (to build)
  fetcher.py           ← (to build)
```
