#!/usr/bin/env python3
"""
misc/tradertv/fetcher.py — Download TraderTV Morning Note PDF from Google Drive

Given a Google Drive file ID or share URL, downloads the PDF to misc/tradertv/downloads/

Usage:
    python misc/tradertv/fetcher.py <drive_url_or_id>
    python misc/tradertv/fetcher.py https://drive.google.com/file/d/15QMSbC7aHLI5iPJPiMoV109J2ET-Knbi/view
    python misc/tradertv/fetcher.py 15QMSbC7aHLI5iPJPiMoV109J2ET-Knbi

Output (stdout JSON):
    {"status": "ok", "drive_id": "...", "pdf_path": "...", "size_kb": 123}

Note:
    Getting the Drive URL from YouTube community post is handled by the
    TradeDesk agent (uses OpenClaw browser tool). This script only handles
    the download step.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DOWNLOAD_DIR = Path(__file__).parent / "downloads"


def extract_drive_id(url_or_id: str) -> str:
    """Extract file ID from a Drive URL or return as-is if already an ID."""
    # Pattern: /file/d/{ID}/
    match = re.search(r'/file/d/([A-Za-z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    # Pattern: id={ID}
    match = re.search(r'id=([A-Za-z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    # Assume it's already a bare ID
    return url_or_id.strip()


def download(drive_id: str, date_str: str = None) -> dict:
    """Download PDF from Google Drive public link."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    out_path = DOWNLOAD_DIR / f"morning_note_{date_str}.pdf"

    if out_path.exists():
        size_kb = out_path.stat().st_size // 1024
        return {"status": "ok", "drive_id": drive_id, "pdf_path": str(out_path), "size_kb": size_kb, "cached": True}

    url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    result = subprocess.run(
        ["curl", "-L", "-o", str(out_path), url],
        capture_output=True, timeout=30
    )

    if result.returncode != 0 or not out_path.exists():
        return {"status": "error", "error": result.stderr.decode()[:200]}

    size_kb = out_path.stat().st_size // 1024
    return {"status": "ok", "drive_id": drive_id, "pdf_path": str(out_path), "size_kb": size_kb, "cached": False}


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetcher.py <drive_url_or_id> [date YYYY-MM-DD]", file=sys.stderr)
        sys.exit(1)

    drive_id = extract_drive_id(sys.argv[1])
    date_str = sys.argv[2] if len(sys.argv) > 2 else None

    result = download(drive_id, date_str)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
