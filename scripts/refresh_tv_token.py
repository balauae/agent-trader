#!/usr/bin/env python3
"""
TradingView Auth Token Refresher
=================================
Launches Chrome with the user's profile + remote debugging, opens TradingView,
extracts the JWT auth token via CDP, and saves to .secrets/tradingview.json.

Run manually:    python scripts/refresh_tv_token.py
Direct inject:   python scripts/refresh_tv_token.py --token "eyJhbGci..."

No Playwright, no complex deps — just Chrome + CDP over HTTP.
"""

import json
import base64
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SECRETS_FILE = REPO_ROOT / ".secrets" / "tradingview.json"
TV_CHART_URL = "https://www.tradingview.com/chart/"
CHROME_BIN = "/usr/bin/google-chrome"
USER_DATA_DIR = os.path.expanduser("~/.openclaw/browser/bala/user-data")
CDP_PORT = 18801
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
MAX_RETRIES = 3


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def save_token(token: str, method: str = "cdp") -> bool:
    """Save a JWT token to .secrets/tradingview.json."""
    if not token or not token.startswith("eyJ"):
        log("ERROR: Invalid token (expected JWT starting with eyJ)")
        return False
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        exp_dt = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
        plan = payload.get("plan", "?")
        user_id = payload.get("user_id", "?")
        log(f"Plan: {plan} | User: {user_id} | Expires: {exp_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    except Exception as e:
        log(f"JWT decode warning: {e}")
        exp_dt = None
        plan = user_id = "unknown"

    existing = {}
    if SECRETS_FILE.exists():
        try: existing = json.loads(SECRETS_FILE.read_text())
        except Exception: pass

    existing.update({
        "auth_token": token,
        "plan": plan,
        "user_id": str(user_id),
        "token_expires": exp_dt.isoformat() if exp_dt else None,
        "token_refreshed_at": datetime.now(tz=timezone.utc).isoformat(),
        "login_method": method,
    })
    SECRETS_FILE.parent.mkdir(exist_ok=True)
    SECRETS_FILE.write_text(json.dumps(existing, indent=2))
    log(f"Token saved ({len(token)} chars)")
    return True


def cdp_get(path: str, timeout: int = 10):
    """GET request to CDP HTTP endpoint."""
    with urllib.request.urlopen(f"{CDP_URL}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def cdp_ws_eval(ws_url: str, js: str, timeout: int = 15) -> str | None:
    """Evaluate JS in a tab via CDP WebSocket. Returns the string result."""
    import websocket
    result = {}

    def on_message(ws, message):
        data = json.loads(message)
        if data.get("id") == 1:
            result["value"] = data.get("result", {}).get("result", {}).get("value")
            ws.close()

    def on_open(ws):
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True},
        }))

    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_open=on_open)
    ws.run_forever(ping_timeout=timeout)
    return result.get("value")


def get_display() -> str:
    """Auto-detect X display from /tmp/.X11-unix/."""
    try:
        sockets = [f for f in os.listdir("/tmp/.X11-unix/") if f.startswith("X")]
        if sockets:
            return f":{sockets[0][1:]}"
    except Exception:
        pass
    return ":0"


def refresh_token() -> bool:
    log("=== TradingView Token Refresh ===")

    chrome_proc = None
    we_started = False

    # 1. Check if CDP is already available
    try:
        info = cdp_get("/json/version")
        log(f"CDP available: {info.get('Browser', '?')}")
    except Exception:
        # 2. Need to launch Chrome with CDP
        log("Launching Chrome with --remote-debugging-port...")
        pkill_result = subprocess.run(["pkill", "-f", "google-chrome"], capture_output=True)
        if pkill_result.returncode == 0:
            log("Killed existing Chrome")
            time.sleep(2)

        display = get_display()
        env = os.environ.copy()
        env["DISPLAY"] = display
        log(f"DISPLAY={display}")

        chrome_proc = subprocess.Popen(
            [CHROME_BIN, f"--remote-debugging-port={CDP_PORT}", "--remote-allow-origins=*",
             f"--user-data-dir={USER_DATA_DIR}", "--no-first-run", TV_CHART_URL],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
        )
        we_started = True
        log(f"Chrome PID: {chrome_proc.pid}")

        # Wait for CDP
        for i in range(20):
            time.sleep(1)
            try:
                cdp_get("/json/version")
                log(f"CDP ready after {i+1}s")
                break
            except Exception:
                pass
        else:
            log("ERROR: CDP not available after 20s")
            chrome_proc.terminate()
            return False

    # 3. Find or open a TradingView tab
    for attempt in range(1, MAX_RETRIES + 1):
        log(f"Attempt {attempt}/{MAX_RETRIES}")
        try:
            tabs = cdp_get("/json")
            tv_tab = next((t for t in tabs if "tradingview.com" in (t.get("url") or "")), None)

            if tv_tab:
                log(f"Found existing TV tab: {tv_tab['url'][:60]}")
                ws_url = tv_tab.get("webSocketDebuggerUrl", "")
            else:
                log("Opening TradingView tab...")
                # Navigate the first tab to TradingView
                if tabs:
                    ws_url = tabs[0].get("webSocketDebuggerUrl", "")
                    cdp_ws_eval(ws_url, f"window.location.href = '{TV_CHART_URL}'")
                    log("Navigating...")
                else:
                    log("No tabs found")
                    continue

            log("Waiting 10s for page to render...")
            time.sleep(10)

            # Re-fetch tabs to get updated WS URL after navigation
            tabs = cdp_get("/json")
            tv_tab = next((t for t in tabs if "tradingview.com" in (t.get("url") or "")), None)
            if not tv_tab:
                log("TV tab not found after navigation")
                continue
            ws_url = tv_tab.get("webSocketDebuggerUrl", "")

            # Extract token
            log("Extracting auth_token...")
            js = 'document.documentElement.innerHTML.match(/"auth_token":"([^"]+)"/)?.[1] || "NOT_FOUND"'
            token = cdp_ws_eval(ws_url, js)

            if not token or token == "NOT_FOUND":
                log("Token not found in page HTML")
                time.sleep(3)
                continue

            log(f"Token: {token[:40]}...")
            if save_token(token):
                log("=== Token refresh complete ===")
                if we_started and chrome_proc:
                    chrome_proc.terminate()
                    log("Chrome closed")
                return True

        except Exception as e:
            log(f"Error: {e}")
            time.sleep(3)

    log("ERROR: All attempts failed")
    if we_started and chrome_proc:
        chrome_proc.terminate()
        log("Chrome closed")
    return False


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--token":
        success = save_token(sys.argv[2], "manual")
    else:
        # Ensure websocket-client is available
        try:
            import websocket  # noqa: F401
        except ImportError:
            print("Installing websocket-client...")
            subprocess.run([sys.executable, "-m", "pip", "install", "websocket-client"], check=True)
        success = refresh_token()
    sys.exit(0 if success else 1)
