"""
Telegram command listener — non-blocking backup poller for /approve, /deny, and /pm text commands.

IMPORTANT: The dashboard (dashboard/app.py → poll_callbacks) is the PRIMARY Telegram poller.
This script is the fast non-blocking reader that also handles /pm commands.

Commands:
  /approve SYMBOL  → open position (handled by dashboard)
  /deny SYMBOL     → reject signal (handled by dashboard)
  /pm check        → trigger PM-Agent pipeline health check (this script → flag file)
  /pm status       → quick pipeline snapshot (this script → flag file)

PM-Agent watches the flag file /app/data/.pm_trigger and acts on it.

Usage:
    python trading_agent/telegram_command_listener.py
"""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram_sender import (
    _handle_approve, _handle_deny,
    _api_request, _ALLOWED_CHATS,
    send_telegram,
)

# ── PM-Agent flag file ──────────────────────────────────────────────────────────
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
PM_TRIGGER = DATA_DIR / '.pm_trigger'

print("[TelegramCmd] Non-blocking listener for /approve, /deny, and /pm commands...")
print("[TelegramCmd] Dashboard (port 5050) is the primary poller for /approve,/deny.")
print("[TelegramCmd] /pm commands fire PM-Agent pipeline check.")
print("[TelegramCmd] Press Ctrl+C to stop")

_last_update_id = 0

def trigger_pm(command: str, chat_id: str):
    """Call the dashboard's PM-Agent webhook to trigger a pipeline check."""
    try:
        import requests
        resp = requests.post(
            "http://localhost:5050/pm-webhook",
            json={"command": command, "triggered_by": chat_id},
            timeout=5,
        )
        print(f"[TelegramCmd] PM-Agent webhook: {resp.status_code} — /pm {command}")
    except Exception as e:
        print(f"[TelegramCmd] PM-Agent webhook failed: {e}")
        print("[TelegramCmd] Falling back: writing trigger file to DATA_DIR")
        payload = {
            "command": command,
            "triggered_by": chat_id,
            "triggered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        PM_TRIGGER.write_text(json.dumps(payload))

def quick_status(chat_id: str):
    """Inline quick status — respond directly to /pm status without PM-Agent."""
    import requests
    try:
        resp = requests.get("http://localhost:5050/api/state", timeout=5)
        state = resp.json()
        last = state.get('last_scan', '?')
        signals = len(state.get('signals', []))
        positions = len(state.get('positions', []))
        msg = f"📊 Pipeline Status\nLast scan: {last}\nSignals: {signals}\nOpen positions: {positions}"
    except Exception:
        msg = "⚠️ Could not reach dashboard at :5050 — PM-Agent will investigate"
    send_telegram(chat_id, msg)

backoff = 1
while True:
    try:
        # Non-blocking (timeout=0) — safe to run alongside dashboard's long-poll
        updates = _api_request('getUpdates', {
            'offset':  _last_update_id + 1,
            'timeout': 0,
        })
        if not (updates and updates.get('ok')):
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue

        backoff = 1  # reset on success

        for upd in updates.get('result', []):
            _last_update_id = max(_last_update_id, upd.get('update_id', 0))

            msg = upd.get('message', {})
            if not msg:
                continue

            chat_id = str(msg.get('chat', {}).get('id', ''))
            text    = (msg.get('text', '') or '').strip()

            if chat_id not in _ALLOWED_CHATS:
                continue

            if text.startswith('/pm '):
                parts = text.split()
                cmd = parts[1].lower() if len(parts) >= 2 else ''
                if cmd == 'check':
                    trigger_pm('check', chat_id)
                    send_telegram(chat_id, "🔍 PM-Agent triggered — pipeline health check running")
                elif cmd == 'status':
                    quick_status(chat_id)
                else:
                    send_telegram(chat_id, "Usage: /pm check | /pm status")
                continue

            if text.startswith('/approve'):
                parts = text.split()
                if len(parts) >= 2:
                    _handle_approve(chat_id, parts[1].upper())
                    print(f"[TelegramCmd] /approve {parts[1].upper()}")
                else:
                    print("[TelegramCmd] /approve — no symbol")

            elif text.startswith('/deny'):
                parts = text.split()
                if len(parts) >= 2:
                    _handle_deny(chat_id, parts[1].upper())
                    print(f"[TelegramCmd] /deny {parts[1].upper()}")
                else:
                    print("[TelegramCmd] /deny — no symbol")

        time.sleep(0.5)   # poll every 500ms — fast but not aggressive

    except Exception as e:
        print(f"[TelegramCmd] Error: {e}")
        time.sleep(min(backoff * 2, 60))
        backoff = min(backoff * 2, 60)
