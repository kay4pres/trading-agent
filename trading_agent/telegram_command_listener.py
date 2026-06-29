"""
Telegram command listener — non-blocking backup poller for /approve and /deny text commands.

IMPORTANT: The dashboard (dashboard/app.py → poll_callbacks) is the PRIMARY Telegram poller.
It handles both button presses and text commands (/approve, /deny).

This script exists as a fast non-blocking reader. It uses timeout=0 so it never
long-polls and can never cause a 409 Conflict with the dashboard.

Run alongside the dashboard if you want /approve and /deny to work even when the
dashboard is being restarted.

Usage:
    python E:/Me/TradingAgent/trading_agent/telegram_command_listener.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from telegram_sender import (
    _handle_approve, _handle_deny,
    _api_request, _ALLOWED_CHATS,
)
import time

print("[TelegramCmd] Non-blocking listener for /approve and /deny commands...")
print("[TelegramCmd] Dashboard (port 5050) is the primary poller.")
print("[TelegramCmd] Press Ctrl+C to stop")

_last_update_id = 0

while True:
    try:
        # Non-blocking (timeout=0) — safe to run alongside dashboard's long-poll
        updates = _api_request('getUpdates', {
            'offset':  _last_update_id + 1,
            'timeout': 0,
        })
        if not (updates and updates.get('ok')):
            time.sleep(1)
            continue

        for upd in updates.get('result', []):
            _last_update_id = max(_last_update_id, upd.get('update_id', _last_update_id))

            msg = upd.get('message', {})
            if not msg:
                continue

            chat_id = str(msg.get('chat', {}).get('id', ''))
            text    = (msg.get('text', '') or '').strip()

            if chat_id not in _ALLOWED_CHATS:
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
        time.sleep(3)
