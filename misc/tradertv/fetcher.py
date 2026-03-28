#!/usr/bin/env python3
"""
misc/tradertv/fetcher.py — Fetch today's TraderTV Morning Note PDF

Uses the `bala` OpenClaw browser profile (already logged into YouTube)
to scrape the latest community post and extract the Google Drive PDF link.

Usage:
    python misc/tradertv/fetcher.py              # download to misc/tradertv/downloads/
    python misc/tradertv/fetcher.py --dry-run    # print Drive link only, don't download

Output (stdout JSON):
    {"date": "2026-03-27", "drive_id": "15QMSbC7...", "pdf_path": ".../Mar27.pdf", "status": "ok"}
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# --- Config ---
REPO_ROOT    = Path(__file__).parent.parent.parent
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
CDP_PORT     = 18801
YT_COMMUNITY = "https://www.youtube.com/channel/UCn75vF3UxwWeWPAY4-5Z6HQ/community"
WAIT_LOAD    = 5  # seconds for page to load


def log(msg, file=sys.stderr):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", file=file)


def start_browser():
    log("Starting bala browser profile...")
    subprocess.run(
        ["openclaw", "browser", "start", "--profile", "bala"],
        capture_output=True, text=True, timeout=15
    )
    time.sleep(3)


def stop_browser():
    subprocess.run(
        ["openclaw", "browser", "stop", "--profile", "bala"],
        capture_output=True, text=True, timeout=10
    )


def get_page_text() -> str:
    """Navigate to YouTube community tab and return page text via CDP."""
    import urllib.request
    import json as _json

    base = f"http://127.0.0.1:{CDP_PORT}"

    # Get list of pages
    tabs = _json.loads(urllib.request.urlopen(f"{base}/json").read())
    target = next((t for t in tabs if t.get("type") == "page"), None)
    if not target:
        raise RuntimeError("No browser page found")

    target_id = target["id"]

    # Navigate
    nav_url = f"{base}/json/new?{YT_COMMUNITY}"
    urllib.request.urlopen(nav_url)
    time.sleep(WAIT_LOAD)

    # Get page content via Runtime.evaluate
    ws_url = target["webSocketDebuggerUrl"]

    # Use CDP via curl subprocess (simpler than websocket lib)
    result = subprocess.run(
        ["curl", "-s", f"{base}/json"],
        capture_output=True, text=True
    )
    tabs = _json.loads(result.stdout)

    # Find the community tab
    for tab in tabs:
        if "community" in tab.get("url", ""):
            target_id = tab["id"]
            break

    # Extract text content using CDP evaluate
    eval_result = subprocess.run([
        "curl", "-s", "-X", "POST",
        f"{base}/json/runtime/evaluate",
        "-H", "Content-Type: application/json",
        "-d", _json.dumps({
            "id": target_id,
            "expression": "document.body.innerText"
        })
    ], capture_output=True, text=True)

    return eval_result.stdout


def extract_drive_link_from_snapshot(snapshot_text: str) -> tuple[str, str] | None:
    """
    Parse snapshot text for a Morning Market Brief post with Drive link.
    Returns (date_str, drive_file_id) or None.
    """
    # Look for Morning Market Brief posts
    # Drive links appear as redirect URLs: q=https%3A%2F%2Fdrive.google.com%2Ffile%2Fd%2F{ID}
    
    # Pattern 1: encoded redirect URL
    pattern = r'q=https%3A%2F%2Fdrive\.google\.com%2Ffile%2Fd%2F([A-Za-z0-9_-]+)'
    matches = re.findall(pattern, snapshot_text)
    
    if not matches:
        # Pattern 2: direct drive URL
        pattern2 = r'drive\.google\.com/file/d/([A-Za-z0-9_-]+)'
        matches = re.findall(pattern2, snapshot_text)

    if not matches:
        return None

    drive_id = matches[0]

    # Try to extract date from post text
    date_match = re.search(r'Morning Market Brief[^\n]*–\s*(\w+ \d+)', snapshot_text)
    if date_match:
        date_str = date_match.group(1)  # e.g. "March 27"
        # Convert to YYYY-MM-DD
        try:
            year = datetime.now().year
            dt = datetime.strptime(f"{date_str} {year}", "%B %d %Y")
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    return date_str, drive_id


def download_pdf(drive_id: str, date_str: str) -> Path:
    """Download PDF from Google Drive public link."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOWNLOAD_DIR / f"morning_note_{date_str}.pdf"

    if out_path.exists():
        log(f"Already downloaded: {out_path.name}")
        return out_path

    url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    log(f"Downloading PDF from Drive ID: {drive_id}...")

    result = subprocess.run(
        ["curl", "-L", "-o", str(out_path), url],
        capture_output=True, timeout=30
    )

    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"Download failed: {result.stderr.decode()}")

    size = out_path.stat().st_size
    log(f"Downloaded: {out_path.name} ({size/1024:.0f} KB)")
    return out_path


def fetch_via_browser_snapshot() -> tuple[str, str] | None:
    """
    Use OpenClaw browser tool (via gateway API) to get YouTube community page snapshot.
    This is the primary method — uses bala's logged-in Chrome profile.
    """
    import urllib.request
    import json as _json

    gateway_url = "http://localhost:9999"  # OpenClaw gateway
    gateway_token = None

    # Try to read gateway token
    try:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            cfg = _json.loads(config_path.read_text())
            gateway_token = cfg.get("gatewayToken")
            gateway_url = cfg.get("gatewayUrl", gateway_url)
    except Exception:
        pass

    # This script is designed to be called by TradeDesk agent which has browser tool access
    # For standalone use, fall back to CDP direct approach
    return None


def main():
    dry_run = "--dry-run" in sys.argv
    started_browser = False

    try:
        # Start browser
        start_browser()
        started_browser = True
        time.sleep(2)

        log(f"Opening YouTube community tab...")
        
        # Navigate via CDP
        import json as _json
        base = f"http://127.0.0.1:{CDP_PORT}"
        
        # Open new tab with community URL
        result = subprocess.run(
            ["curl", "-s", f"{base}/json/new?{urllib.parse.quote(YT_COMMUNITY, safe=':/?=')}"],
            capture_output=True, text=True, timeout=10
        )
        
        log(f"Waiting {WAIT_LOAD}s for page to load...")
        time.sleep(WAIT_LOAD)

        # Get all tabs
        tabs_result = subprocess.run(
            ["curl", "-s", f"{base}/json"],
            capture_output=True, text=True, timeout=5
        )
        tabs = _json.loads(tabs_result.stdout)

        # Find community tab and get its text
        page_text = ""
        for tab in tabs:
            if "community" in tab.get("url", "") or "TraderTV" in tab.get("title", ""):
                tab_id = tab["id"]
                # Evaluate page text
                eval_cmd = {
                    "expression": "document.body.innerText",
                    "returnByValue": True
                }
                eval_result = subprocess.run([
                    "curl", "-s",
                    f"http://127.0.0.1:{CDP_PORT}/json/runtime/evaluate/{tab_id}",
                    "-X", "POST", "-H", "Content-Type: application/json",
                    "-d", _json.dumps(eval_cmd)
                ], capture_output=True, text=True, timeout=10)
                page_text = eval_result.stdout
                break

        if not page_text:
            # Try reading page source directly
            for tab in tabs:
                if "community" in tab.get("url", ""):
                    src_result = subprocess.run(
                        ["curl", "-s", f"{base}/json/source/{tab['id']}"],
                        capture_output=True, text=True, timeout=10
                    )
                    page_text = src_result.stdout
                    break

        log(f"Page text length: {len(page_text)} chars")

        result = extract_drive_link_from_snapshot(page_text)

        if not result:
            log("ERROR: No Drive link found in community posts", sys.stderr)
            print(json.dumps({"status": "error", "error": "no_drive_link_found"}))
            sys.exit(1)

        date_str, drive_id = result
        log(f"Found: date={date_str}, drive_id={drive_id}")

        if dry_run:
            print(json.dumps({
                "status": "ok",
                "date": date_str,
                "drive_id": drive_id,
                "drive_url": f"https://drive.google.com/file/d/{drive_id}/view",
                "pdf_path": None
            }, indent=2))
            return

        pdf_path = download_pdf(drive_id, date_str)
        print(json.dumps({
            "status": "ok",
            "date": date_str,
            "drive_id": drive_id,
            "pdf_path": str(pdf_path)
        }))

    finally:
        if started_browser:
            stop_browser()


if __name__ == "__main__":
    main()
