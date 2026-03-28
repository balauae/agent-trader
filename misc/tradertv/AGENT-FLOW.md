# TraderTV — Agent Flow

## How it works

When Bala says **"fetch today's TraderTV"**, the agent does this:

### Step 1 — Browser: YouTube → Drive link
```
browser(action="open", url="https://www.youtube.com/channel/UCn75vF3UxwWeWPAY4-5Z6HQ/community", profile="bala")
browser(action="snapshot", ...)
→ read snapshot text
→ find Drive redirect URL: q=https%3A%2F%2Fdrive.google.com%2Ffile%2Fd%2F{FILE_ID}
→ extract FILE_ID
```

**Why `bala` profile?** Posts are "Members only" — requires logged-in YouTube session.
**Why browser tool?** YouTube community posts can't be scraped with yt-dlp or curl.
**This step cannot be a Python script** — only the agent can use the OpenClaw browser tool.

### Step 2 — Download: Drive → PDF
```bash
python misc/tradertv/fetcher.py <drive_url_or_id> [date]
# Output: {"status": "ok", "pdf_path": "...", "size_kb": 3124}
```

### Step 3 — Parse: PDF → JSON
```bash
python misc/tradertv/parser.py <pdf_path>
# Output: full JSON — ticker, headline, bias, S/R zones, news bullets, trader takeaway
```

### Step 4 — Setups: JSON → ranked setups
```bash
python misc/tradertv/setup_finder.py <pdf_path> --format telegram
# Output: watchlist hits + top setups formatted for Telegram
```

---

## Full flow diagram

```
Bala: "fetch today's TraderTV"
        ↓
[AGENT] browser tool (bala profile)
        → open YouTube community tab
        → snapshot page
        → extract Drive file ID
        ↓
[SCRIPT] fetcher.py <drive_id>
        → curl download PDF
        → save to downloads/morning_note_YYYY-MM-DD.pdf
        ↓
[SCRIPT] parser.py <pdf_path>
        → PyMuPDF text extraction
        → parse: ticker, headline, bias, S/R, news, takeaway
        → output: full JSON (zero data loss)
        ↓
[SCRIPT] setup_finder.py <pdf_path>
        → score setups
        → cross-reference watchlist
        → output: Telegram message
        ↓
[AGENT] send Telegram to Bala
```

---

## Why not automate Step 1?

`fetcher.py` was originally written to do the YouTube scraping too (via CDP curl commands). It was broken and has been removed. Reasons it can't work as a standalone script:

1. YouTube community posts require a logged-in session
2. OpenClaw's browser tool is only accessible to the agent, not Python scripts
3. yt-dlp doesn't support community post scraping (returns 0 entries)

**The browser step must stay as an agent action.**

---

## Triggering phrases

- "fetch today's TraderTV"
- "get Cherif's note"
- "TraderTV morning brief"
- "what does Cherif say today"

---

## Scheduled automation (future)

When ready, a cron job can trigger the agent daily:
```
3:30 PM AbuDhabi (2.5 hrs before market open at 5:30 PM)
→ agent wakes up
→ runs full flow
→ sends Telegram summary
```

Cron payload (agentTurn):
```
"Fetch today's TraderTV morning note and send the setup summary to Telegram."
```
