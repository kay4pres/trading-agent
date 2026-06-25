r"""
telegram_sender.py
==================
Sends alert messages and trade signals to Kay via @Marvless01_bot.
Supports inline keyboard buttons for APPROVE / DENY / SKIP on signals.

Token: E:\Me\TradingAgent\config\telegram_token.enc (PowerShell SecureString, DPAPI)
Chat ID: -5581171035 (Kay's Trading Team group)

Usage:
    from telegram_sender import send_alert, send_signal_with_buttons
    send_signal_with_buttons(symbol="SOFI", action="BUY", price=17.31, ...)
"""

import json, subprocess, sys, os, time, threading
from pathlib import Path
from typing import Optional, Dict, Any

TOKEN_PATH  = Path(r'E:\Me\TradingAgent\config\telegram_token.enc')
CHAT_ID     = '-5581171035'   # Kay's Trading Team group
API_BASE    = 'https://api.telegram.org'

# In-memory store: message_id → signal dict (for button callback resolution)
_pending_signals: Dict[int, Dict[str, Any]] = {}

# Last update_id processed (avoids duplicate processing)
_last_update_id = 0


def _get_token() -> Optional[str]:
    """Decrypt PowerShell SecureString via PowerShell subprocess."""
    ps = (
        f"$b = Get-Content '{TOKEN_PATH}' -Raw; "
        f"$s = ConvertTo-SecureString $b; "
        f"[System.Runtime.InteropServices.Marshal]::PtrToStringAuto("
        f"[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"
    )
    try:
        result = subprocess.run(
            ['powershell', '-Command', ps],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _api_request(method: str, payload: dict) -> Optional[dict]:
    """Make a Telegram Bot API call. Returns parsed JSON or None on failure."""
    token = _get_token()
    if not token:
        print("[telegram_sender] ERROR: could not decrypt token")
        return None
    url = f"{API_BASE}/bot{token}/{method}"
    try:
        import urllib.request
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[telegram_sender] API error ({method}): {e}")
        return None


def send_message(text: str, parse_mode: str = 'Markdown') -> bool:
    """Send a plain text message to Kay's Telegram chat."""
    result = _api_request('sendMessage', {
        'chat_id':    CHAT_ID,
        'text':       text,
        'parse_mode': parse_mode,
    })
    return result is not None and result.get('ok', False)


def send_signal_with_buttons(
    symbol: str,
    action: str,
    price: float,
    gap: float,
    score: float,
    rel_vol: float = 0.0,
    float_m: float = 0.0,
    notes: str = '',
    risk_flags: list = None,
) -> Optional[Dict[str, Any]]:
    """
    Send a trade signal with inline APPROVE / DENY / SKIP buttons.
    Uses HTML parse_mode for reliable bold/italic rendering.
    Stores the signal in _pending_signals keyed by message_id for callback resolution.
    """
    emoji_action = "🟢" if action.upper() == "BUY" else "🔴"
    risk_str = ""
    if risk_flags:
        risk_str = f"\n⚠️ {' | '.join(risk_flags)}"

    text = (
        f"{emoji_action} <b>{action} SIGNAL</b>\n"
        f"─────────────────────\n"
        f"<b>Symbol:</b> {symbol}\n"
        f"<b>Price:</b>  ${price:.2f}\n"
        f"<b>Gap:</b>   {gap:+.1f}%\n"
        f"<b>RV:</b>    {rel_vol:.1f}x\n"
        f"<b>Float:</b> {float_m:.0f}M\n"
        f"<b>Score:</b> {score:.1f}/5{risk_str}\n"
    )
    if notes:
        text += f"📝 {notes}"

    # Inline keyboard: one row of three buttons
    payload = {
        'chat_id':     CHAT_ID,
        'text':        text,
        'parse_mode':  'HTML',
        'reply_markup': json.dumps({
            'inline_keyboard': [[
                {'text': '✅ APPROVE', 'callback_data': f'approve:{symbol}:{price}:{score}'},
                {'text': '❌ DENY',   'callback_data': f'deny:{symbol}:{price}:{score}'},
                {'text': '⏭️ SKIP',   'callback_data': f'skip:{symbol}:{price}:{score}'},
            ]]
        }),
    }

    result = _api_request('sendMessage', payload)
    if result and result.get('ok'):
        msg_id = result['result']['message_id']
        sig_data = {
            'symbol':    symbol,
            'action':    action,
            'price':    price,
            'score':    score,
            'gap':      gap,
            'rel_vol':  rel_vol,
            'float_m':  float_m,
            'notes':    notes,
            'risk_flags': risk_flags or [],
        }
        _pending_signals[msg_id] = sig_data
        print(f"[telegram_sender] Signal sent: {symbol} msg_id={msg_id}")
        return result['result']
    return None


def send_alert(message: str) -> bool:
    """High-level alert: sends a formatted message to Kay."""
    header = "📊 *Kay's Trading Agent*\n"
    return send_message(header + message)


def send_signal(symbol: str, action: str, price: float, gap: float,
                score: float, notes: str = '') -> bool:
    """Format and send a trade signal (legacy — no buttons)."""
    emoji = "🟢" if action.upper() == "BUY" else "🔴"
    msg = (
        f"{emoji} *{action} SIGNAL*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Symbol:* {symbol}\n"
        f"*Price:* ${price:.2f}\n"
        f"*Gap:*   {gap:+.1f}%\n"
        f"*Score:* {score:.1f}/5\n"
    )
    if notes:
        msg += f"\n📝 {notes}"
    return send_message(msg)


def send_watchlist(symbols: list, scan_time: str) -> bool:
    """Send the premarket watchlist summary."""
    lines = [f"📋 *Pre-Market Watchlist*\n_Scanned: {scan_time}_"]
    for s in symbols[:5]:  # top 5
        lines.append(
            f"  {s['symbol']:<6} gap={s['gap_pct']:+.1f}% "
            f"rv={s['rel_vol']:.1f}x score={s['total_score']:.1f}"
        )
    return send_message('\n'.join(lines))


def edit_message_buttons(chat_id: str, message_id: int, action: str, symbol: str, price: float):
    """Replace inline buttons with the decision that was made."""
    emoji_map = {'approve': '✅', 'deny': '❌', 'skip': '⏭️'}
    label_map  = {'approve': 'APPROVED', 'deny': 'DENIED', 'skip': 'SKIPPED'}
    emoji = emoji_map.get(action, '❓')
    label = label_map.get(action, action.upper())

    new_text = (
        f"{emoji} <b>{label}</b>\n"
        f"─────────────────────\n"
        f"Symbol: <b>{symbol}</b> @ ${price:.2f}\n"
        f"<i>Tap buttons above for new signals</i>"
    )
    _api_request('editMessageText', {
        'chat_id':    chat_id,
        'message_id': message_id,
        'text':       new_text,
        'parse_mode': 'HTML',
    })
    # Clear the reply markup (remove buttons)
    _api_request('editMessageReplyMarkup', {
        'chat_id':    chat_id,
        'message_id': message_id,
        'reply_markup': json.dumps({'inline_keyboard': []}),
    })


def answer_callback(callback_id: str, text: str, show_alert: bool = True):
    """Send a toast / alert popup to the user after a button press."""
    _api_request('answerCallbackQuery', {
        'callback_query_id': callback_id,
        'text':              text,
        'show_alert':        show_alert,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# POLLING LOOP  (runs as a background thread)
# ═══════════════════════════════════════════════════════════════════════════════

# Subclass-safe event: set by app.py when it wants to stop the loop
_stop_polling = threading.Event()


def poll_callbacks(callback_handler=None):
    """
    Background thread: polls Telegram for callback_query updates every 5s.
    Calls `callback_handler(action, symbol, price, score, callback_id, chat_id, message_id)`
    when a button is pressed.
    """
    global _last_update_id
    while not _stop_polling.wait(5):
        try:
            updates = _api_request('getUpdates', {
                'offset':      _last_update_id + 1,
                'timeout':     25,
            })
            if not (updates and updates.get('ok')):
                continue

            for upd in updates.get('result', []):
                _last_update_id = upd.get('update_id', _last_update_id)

                # Look for callback_query (button press)
                cq = upd.get('callback_query', {})
                if not cq:
                    continue

                callback_id = cq.get('id', '')
                msg = cq.get('message', {})
                chat_id     = str(msg.get('chat', {}).get('id', ''))
                message_id  = msg.get('message_id', 0)
                data        = cq.get('data', '')

                if not data:
                    continue

                # Parse callback_data: "approve:SOFI:17.31:4.5"
                parts = data.split(':')
                if len(parts) != 4:
                    continue
                action, symbol, price_str, score_str = parts
                price = float(price_str)
                score = float(score_str)

                sig = _pending_signals.get(message_id, {})
                sig.setdefault('symbol', symbol)
                sig.setdefault('price', price)
                sig.setdefault('score', score)

                print(f"[telegram] Button pressed: {action.upper()} {symbol} (msg={message_id})")

                # Remove from pending
                _pending_signals.pop(message_id, None)

                # Toast confirmation to user
                label_map = {'approve': f'✅ Approved {symbol} at ${price}', 
                             'deny':    f'❌ Denied {symbol}', 
                             'skip':    f'⏭️ Skipped {symbol}'}
                toast = label_map.get(action, f'{action} {symbol}')
                answer_callback(callback_id, toast, show_alert=True)

                # Update message to show decision
                edit_message_buttons(chat_id, message_id, action, symbol, price)

                # Call user handler if provided (app.py wires this to /api/decision)
                if callback_handler:
                    callback_handler(action.upper(), symbol, price, score, chat_id, message_id)

        except Exception as e:
            print(f"[telegram poll] error: {e}")
            time.sleep(5)


def start_polling(callback_handler=None):
    """Start the polling thread. Call once at app startup."""
    t = threading.Thread(target=poll_callbacks, args=(callback_handler,), daemon=True)
    t.start()
    print("[telegram] Polling thread started — listening for button presses")


def stop_polling():
    _stop_polling.set()
