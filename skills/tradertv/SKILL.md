# Skill: TraderTV Morning Note

## Triggers
- "fetch today's TraderTV"
- "get Cherif's note"
- "TraderTV morning brief"
- "what does Cherif say today"
- "tradertv"
- User pastes a Google Drive PDF link

## What This Is
TraderTV Live (YouTube) posts a daily pre-market PDF ("Cherif's Morning Note") via their community tab.
Each PDF contains 15–21 stocks with: headline, news bullets, support/resistance zones, bias, trader takeaway.

## Agent Flow

### Step 1 — Get Drive link from YouTube (AGENT only — cannot be scripted)
```python
browser(action="open", url="https://www.youtube.com/channel/UCn75vF3UxwWeWPAY4-5Z6HQ/community", profile="bala")
browser(action="snapshot", profile="bala", targetId=<tab_id>)
# Extract Drive file ID from snapshot text:
# Pattern: q=https%3A%2F%2Fdrive.google.com%2Ffile%2Fd%2F{FILE_ID}
# Or direct: drive.google.com/file/d/{FILE_ID}
```
**Must use `bala` profile** — posts are Members only, requires logged-in YouTube session.

### Step 2 — Download PDF
```bash
cd ~/dev/apps/agent-trader
.venv/bin/python misc/tradertv/fetcher.py <drive_url_or_id> <YYYY-MM-DD>
# Output: {"status": "ok", "pdf_path": "...downloads/morning_note_YYYY-MM-DD.pdf"}
```

### Step 3 — Parse PDF (zero data loss)
```bash
.venv/bin/python misc/tradertv/parser.py <pdf_path>
# JSON output: ticker, headline, bias, support[], resistance[], bias_detail, trader_takeaway, news_bullets[]
```

### Step 4 — Send to Telegram
```bash
.venv/bin/python misc/tradertv/setup_finder.py <pdf_path> --format telegram
# Output: watchlist hits first, then top setups
```
Send the output to Bala via Telegram.

## Files
```
misc/tradertv/
  AGENT-FLOW.md       ← full architecture doc
  fetcher.py          ← Drive URL → download PDF
  parser.py           ← PDF → full JSON (no data loss)
  setup_finder.py     ← JSON → ranked setups + Telegram format
  downloads/          ← downloaded PDFs (gitignored)
  sample_Mar27.pdf    ← test sample
  sample2.pdf         ← test sample
  sample3.pdf         ← test sample
  output_Mar25.txt    ← example text output
  output_Mar26.txt    ← example text output
  output_Mar27.txt    ← example text output
  EXAMPLE-OUTPUT.md   ← full GLD example (JSON + text)
```

## If User Pastes a Drive Link Directly
Skip Step 1. Go straight to Step 2 with the provided URL.

## Parser Design Principle
> Parser = faithful extraction only. No summarizing. No trimming. No decisions.
> Every word Cherif wrote goes into JSON exactly as-is.
> Downstream consumers decide what to surface.
