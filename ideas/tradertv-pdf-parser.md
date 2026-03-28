# Idea: TraderTV Daily PDF Parser

**Status:** Concept  
**Priority:** Low (adhoc)  
**Folder:** `ideas/` — standalone, not part of core TradeDesk

---

## What

TraderTV Live (YouTube channel) posts a daily pre-market analysis PDF every morning via their YouTube community tab. The post contains a Google Drive link to a PDF with:
- Tickers to watch
- Key support/resistance levels
- Pre-market gaps
- Bullish/bearish bias per stock
- Catalysts and news

Parse this PDF daily and cross-reference with Bala's watchlist.

---

## Why

- Free professional pre-market analysis every day
- Saves time reviewing manually
- Can auto-alert if they mention GLD or watchlist tickers
- Adds external analyst view to TradeDesk morning brief

---

## Pipeline

```
YouTube community post (daily)
        ↓
Extract Google Drive PDF link from post text
        ↓
Download PDF (public link or authenticated)
        ↓
Parse PDF with pdfplumber
        ↓
Extract: tickers, levels, bias, catalysts
        ↓
Cross-reference with watchlist (USER.md)
        ↓
Output JSON → morning brief / Telegram alert
```

---

## Questions to resolve before building

1. **Is the PDF link public?** (no Google login needed) or requires Drive auth?
2. **What time do they post?** (to schedule the fetch cron)
3. **YouTube API key available?** or use scraping?
4. **PDF format consistent?** (same layout every day or varies)

---

## Implementation Plan (when ready)

### Phase 1 — Manual test
```bash
# Manually grab a PDF link from their community post
# Test parsing with pdfplumber
python ideas/tradertv/test_parse.py path/to/sample.pdf
```

### Phase 2 — Automate fetch
```python
# ideas/tradertv/fetcher.py
# Option A: YouTube Data API v3 (free, 10k units/day)
#   GET https://www.googleapis.com/youtube/v3/activities?channelId=...
# Option B: yt-dlp to scrape community posts (no API key needed)
#   yt-dlp --get-comments https://www.youtube.com/@TraderTVLive
```

### Phase 3 — Parse PDF
```python
# ideas/tradertv/parser.py
import pdfplumber

def parse_tradertv_pdf(pdf_path: str) -> dict:
    # Extract text
    # Find tickers (regex: uppercase 2-5 chars)
    # Find price levels ($XXX.XX pattern)
    # Find bias keywords (bullish, bearish, long, short, watch)
    # Return structured JSON
```

### Phase 4 — Cross-reference watchlist
```python
# Check if any mentioned tickers are in Bala's watchlists
# Alert if GLD or current positions mentioned
# Include in morning brief
```

### Phase 5 — Cron
```
Daily at 11:30 AM AbuDhabi (pre-market, before 12 PM open)
→ Fetch post → Download PDF → Parse → Send Telegram summary
```

---

## Output JSON (target)
```json
{
  "date": "2026-03-31",
  "source": "TraderTV Live",
  "watchlist_mentions": ["NVDA", "TSLA", "GLD"],
  "tickers": [
    {
      "ticker": "NVDA",
      "bias": "BULLISH",
      "levels": {"support": 165.0, "resistance": 172.0},
      "notes": "Breaking out of consolidation, watching $172 pivot"
    }
  ],
  "key_themes": ["AI momentum", "Fed meeting tomorrow", "Tech sector strength"],
  "pdf_url": "https://drive.google.com/...",
  "parsed_at": "2026-03-31T07:30:00Z"
}
```

---

## Dependencies
```
pdfplumber    ← PDF text extraction
yt-dlp        ← YouTube community post scraping (optional)
google-api-python-client ← YouTube Data API (optional)
```

---

## Notes
- Keep entirely in `ideas/tradertv/` — do NOT mix with core scripts
- Not wired into bridge or watcher until proven reliable
- PDF format may change — parser needs to be flexible
- Consider storing parsed PDFs in `ideas/tradertv/archive/YYYY-MM-DD.pdf`
