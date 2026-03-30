#!/usr/bin/env python3
"""
TradingView Auth Token Refresher
=================================
Opens the 'bala' OpenClaw browser profile (already logged into TradingView via Google),
loads the chart page, extracts the JWT auth token from the page HTML, and saves it to
.secrets/tradingview.json.

Run manually:    python scripts/refresh_tv_token.py
Run via cron:    every 4 hours via OpenClaw cron job

How it works:
- TradingView embeds the auth_token JWT in the chart page HTML
- The token is used by tvdatafeed to authenticate WebSocket data feed
- The bala browser profile has persistent Google login (no re-auth needed)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANUAL FALLBACK (when this script fails — e.g. CDP connection refused)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If this script fails, the OpenClaw AI agent can refresh the token manually
using the browser tool. The agent should:

1. Use: browser(action="open", url="https://www.tradingview.com/chart/pDbiSupQ/", profile="bala")
2. Wait 6 seconds: browser(action="act", request={"kind":"wait","timeMs":6000})
3. Extract token from page HTML:
   browser(action="act", request={
     "kind": "evaluate",
     "fn": "document.documentElement.innerHTML.match(/\"auth_token\":\"([^\"]+)\"/)?.[1] || 'not found'"
   })
4. Save the returned JWT string to .secrets/tradingview.json as {"auth_token": "<token>"}

NOTE: The token is NOT in cookies — it is embedded in the page HTML as a JSON variable.
Cookies won't have it. localStorage won't have it. It's in document.documentElement.innerHTML.

The token format: eyJhbGci... (JWT, 3 dot-separated base64 segments)
Token lifespan: ~4 hours (check exp field in JWT payload)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import time
import subprocess
import urllib.request
import urllib.error
import re
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Config ---
REPO_ROOT       = Path(__file__).parent.parent
SECRETS_FILE    = REPO_ROOT / ".secrets" / "tradingview.json"
CDP_PORT        = 18801
CDP_URL         = f"http://127.0.0.1:{CDP_PORT}"
TV_CHART_URL    = "https://www.tradingview.com/chart/"
WAIT_LOAD_SEC   = 6      # seconds to wait for page to load
MAX_RETRIES     = 3


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def save_token_direct(token: str) -> bool:
    """
    Save a JWT token directly to .secrets/tradingview.json.
    
    Use this when the agent extracts the token manually via browser tool:
      python scripts/refresh_tv_token.py --token "eyJhbGci..."
    
    Also callable from OpenClaw agent after browser evaluate step.
    """
    import base64

    if not token or not token.startswith("eyJ"):
        log("ERROR: Invalid token format (expected JWT starting with eyJ)")
        return False

    try:
        # Decode JWT payload to get expiry + plan
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        exp = payload.get("exp", 0)
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        plan = payload.get("plan", "unknown")
        user_id = payload.get("user_id", "unknown")
        log(f"Plan: {plan} | User ID: {user_id} | Expires: {exp_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    except Exception as e:
        log(f"Warning: could not decode JWT payload: {e}")
        exp_dt = None
        plan = "unknown"
        user_id = "unknown"

    existing = {}
    if SECRETS_FILE.exists():
        try:
            existing = json.loads(SECRETS_FILE.read_text())
        except Exception:
            pass

    existing.update({
        "auth_token": token,
        "plan": plan,
        "user_id": str(user_id),
        "token_expires": exp_dt.isoformat() if exp_dt else None,
        "token_refreshed_at": datetime.now(tz=timezone.utc).isoformat(),
        "login_method": "browser_evaluate"
    })

    SECRETS_FILE.parent.mkdir(exist_ok=True)
    SECRETS_FILE.write_text(json.dumps(existing, indent=2))
    log(f"Token saved ✅ ({len(token)} chars) → {SECRETS_FILE}")
    return True


def start_browser():
    """Start the bala OpenClaw browser profile via openclaw CLI."""
    log("Starting bala browser profile...")
    result = subprocess.run(
        ["openclaw", "browser", "start", "--profile", "bala"],
        capture_output=True, text=True, timeout=15
    )
    time.sleep(3)
    return result.returncode == 0


def stop_browser():
    """Stop the bala browser profile."""
    log("Stopping bala browser profile...")
    subprocess.run(
        ["openclaw", "browser", "stop", "--profile", "bala"],
        capture_output=True, text=True, timeout=10
    )


def cdp_request(method, params=None, target_id=None):
    """Make a CDP (Chrome DevTools Protocol) request."""
    if target_id:
        url = f"{CDP_URL}/json"
    else:
        url = f"{CDP_URL}/json"

    payload = json.dumps({"method": method, "params": params or {}}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"CDP request failed: {e}")
        return None


def get_open_tabs():
    """Get list of open browser tabs via CDP."""
    try:
        url = f"{CDP_URL}/json"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"Failed to get tabs: {e}")
        return []


def open_tab(url):
    """Open a new tab via CDP."""
    try:
        req_url = f"{CDP_URL}/json/new?{url}"
        with urllib.request.urlopen(req_url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"Failed to open tab: {e}")
        return None


def evaluate_js(ws_debugger_url, js_code):
    """Run JavaScript in a tab using CDP WebSocket."""
    import websocket

    result_holder = {}

    def on_message(ws, message):
        data = json.loads(message)
        if data.get("id") == 1:
            result_holder["result"] = data.get("result", {}).get("result", {}).get("value")
            ws.close()

    def on_open(ws):
        payload = json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js_code, "returnByValue": True}
        })
        ws.send(payload)

    ws_url = ws_debugger_url.replace("127.0.0.1", "localhost")
    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_open=on_open)
    ws.run_forever(ping_timeout=10)
    return result_holder.get("result")


def extract_token_from_html(html):
    """Extract auth_token from TradingView page HTML."""
    match = re.search(r'"auth_token":"([^"]+)"', html)
    if match:
        return match.group(1)
    return None


def refresh_token():
    """Main token refresh flow."""
    log("=== TradingView Token Refresh ===")

    browser_started_here = False

    # Check if browser already running
    try:
        tabs = get_open_tabs()
        if not tabs:
            raise Exception("No tabs")
    except Exception:
        if not start_browser():
            log("ERROR: Failed to start browser")
            return False
        browser_started_here = True
        time.sleep(3)

    for attempt in range(1, MAX_RETRIES + 1):
        log(f"Attempt {attempt}/{MAX_RETRIES}")

        try:
            # Open TradingView chart tab
            tab = open_tab(TV_CHART_URL)
            if not tab:
                log("Failed to open tab, retrying...")
                time.sleep(2)
                continue

            ws_url = tab.get("webSocketDebuggerUrl", "")
            log(f"Tab opened: {tab.get('url', '')}")

            # Wait for page to load
            log(f"Waiting {WAIT_LOAD_SEC}s for page load...")
            time.sleep(WAIT_LOAD_SEC)

            # Extract auth token via JS
            js = "document.documentElement.innerHTML.match(/\"auth_token\":\"([^\"]+)\"/)?.[1] || 'NOT_FOUND'"
            token = evaluate_js(ws_url, js)

            if not token or token == "NOT_FOUND":
                log("Token not found in page, retrying...")
                time.sleep(3)
                continue

            log(f"Token extracted: {token[:40]}...")

            # Decode JWT to check expiry
            import base64
            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.b64decode(payload_b64))
            exp = payload.get("exp", 0)
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            plan = payload.get("plan", "unknown")
            user_id = payload.get("user_id", "unknown")

            log(f"Plan: {plan} | User ID: {user_id} | Expires: {exp_dt.strftime('%Y-%m-%d %H:%M UTC')}")

            # Load existing secrets
            existing = {}
            if SECRETS_FILE.exists():
                with open(SECRETS_FILE) as f:
                    existing = json.load(f)

            # Update token
            existing.update({
                "auth_token": token,
                "plan": plan,
                "user_id": str(user_id),
                "token_expires": exp_dt.isoformat(),
                "token_refreshed_at": datetime.now(tz=timezone.utc).isoformat(),
                "login_method": "google"
            })

            SECRETS_FILE.parent.mkdir(exist_ok=True)
            with open(SECRETS_FILE, "w") as f:
                json.dump(existing, f, indent=2)

            log(f"Token saved to {SECRETS_FILE}")

            # Stop browser if we started it
            if browser_started_here:
                stop_browser()

            log("=== Token refresh complete ✅ ===")
            return True

        except Exception as e:
            log(f"Error on attempt {attempt}: {e}")
            time.sleep(3)

    log("ERROR: All attempts failed ❌")
    if browser_started_here:
        stop_browser()
    return False


if __name__ == "__main__":
    # Allow direct token injection:
    #   python scripts/refresh_tv_token.py --token "eyJhbGci..."
    if len(sys.argv) == 3 and sys.argv[1] == "--token":
        success = save_token_direct(sys.argv[2])
    else:
        success = refresh_token()
    sys.exit(0 if success else 1)
