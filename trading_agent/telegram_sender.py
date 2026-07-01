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
    """
    Get Telegram bot token. Priority:
    1. TELEGRAM_BOT_TOKEN env var (Docker / NAS deployment)
    2. Vault file /app/vault/TELEGRAM_BOT_TOKEN.env (written by entrypoint.py)
    3. DPAPI vault file (Windows local deployment)
    """
    # Priority 1: env var (Docker path)
    env_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if env_token:
        return env_token

    # Priority 2: vault file written by entrypoint.py
    vault_file = Path('/app/vault/TELEGRAM_BOT_TOKEN.env')
    if vault_file.exists():
        try:
            return vault_file.read_text(encoding='utf-8').strip()
        except Exception:
            pass

    # Priority 3: DPAPI vault file (Windows local deployment)
    try:
        raw = TOKEN_PATH.read_text(encoding='utf-8')
    except Exception:
        return None
    if raw.startswith('\ufeff'):
        raw = raw[1:]
    ps = (
        f"$b = '{raw.strip()}'; "
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
        import urllib.request, socket
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, data=data,
            headers={'Content-Type': 'application/json'}
        )
        # Short timeout: fail fast so polling loops don't block for 30s
        # getUpdates with timeout=0 in payload should return instantly — this
        # caps any TCP/DNS stall at 3s rather than letting urllib default ~60s
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except socket.timeout:
        # timeout=0 in getUpdates means Telegram returns immediately — if WE
        # hit a socket timeout here, Docker network is stalling. Log once.
        print(f"[telegram] getUpdates socket timeout — Docker network may be slow")
        return None
    except urllib.error.HTTPError as e:
        print(f"[telegram] HTTP {e.code} on {method}")
        return None
    except Exception as e:
        print(f"[telegram] API error ({method}): {e}")
        return None


def send_message(text: str, parse_mode: str = 'Markdown') -> bool:
    """Send a plain text message to Kay's Telegram chat."""
    result = _api_request('sendMessage', {
        'chat_id':    CHAT_ID,
        'text':       text,
        'parse_mode': parse_mode,
    })
    return result is not None and result.get('ok', False)


def send_tollgate_message(
    query: str,
    confidence: float,
    verdict: str,
    data_gaps: list,
    run_id: str,
    domain: str = "trading",
) -> Optional[Dict[str, Any]]:
    """
    Send a tollgate decision request to Kay's Telegram group.
    Uses callback_data buttons — requires start_tollgate_listener() to be running.
    """
    verdict_emoji = {
        "PASS": "✅", "REVIEW": "⚠️", "REJECTED": "🚫",
        "TOLLGATE": "🚧", "PASS-KAY-OVERRIDE": "✅*",
    }.get(verdict, "❓")

    lines = [
        f"{verdict_emoji} <b>TOLLGATE — Evidence Gap</b>",
        f"─────────────────────",
        f"<b>Query:</b> {query}",
        f"<b>Confidence:</b> {confidence * 100:.0f}% — <i>{verdict}</i>",
        f"<b>Domain:</b> {domain}",
    ]

    if data_gaps:
        lines.append("")
        lines.append("<b>Data Gaps:</b>")
        for gap in data_gaps[:4]:
            lines.append(f"  ⚠️ {gap[:150]}")

    lines.append("")
    lines.append(f"<b>Tap a button below to decide:</b>")
    lines.append(f"<i>Run: {run_id}</i>")

    text = "\n".join(lines)

    payload = {
        'chat_id':    CHAT_ID,
        'text':       text,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps({
            'inline_keyboard': [[
                {'text': '✅ PROCEED',  'callback_data': f'tollgate:proceed:{run_id}'},
                {'text': '🔍 ESCALATE', 'callback_data': f'tollgate:escalate:{run_id}'},
                {'text': '🚫 ABORT',    'callback_data': f'tollgate:abort:{run_id}'},
            ]]
        }),
    }

    result = _api_request('sendMessage', payload)
    ok = result is not None and result.get('ok', False)
    if ok:
        print(f"[telegram_sender] Tollgate sent for run {run_id}")
    return result


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


# ═══════════════════════════════════════════════════════════════════════════════
# TOLLGATE LISTENER — background thread for button callbacks
# ═══════════════════════════════════════════════════════════════════════════════

_tollgate_listener_running = False


def _tollgate_callback_handler(cmd: str, run_id: str, chat_id: str) -> None:
    """Called by the polling loop when a tollgate button is tapped."""
    emoji_map = {'proceed': '✅', 'escalate': '🔍', 'abort': '🚫'}
    label_map = {'proceed': 'Proceeding', 'escalate': 'Escalating', 'abort': 'Aborting'}
    _write_tollgate_decision(run_id, cmd, chat_id)
    _reply_to_chat(chat_id,
        f"{emoji_map.get(cmd, '❓')} <b>{label_map.get(cmd, cmd.upper())}</b>\n"
        f"Run <code>{run_id}</code> — researcher will act now."
    )
    print(f"[telegram] Tollgate button: /{cmd} for run {run_id}")


# ── File-based IPC for researcher tollgate decisions ───────────────────────────
_TOLLGATE_FILE = Path(r'E:\Me\TradingAgent\data\tollgate_decisions.json')

def _write_tollgate_decision(run_id: str, decision: str, chat_id: str) -> None:
    """Write a tollgate decision to the shared JSON file for the researcher to read."""
    try:
        # Load existing decisions
        if _TOLLGATE_FILE.exists():
            decisions = json.loads(_TOLLGATE_FILE.read_text(encoding='utf-8'))
        else:
            decisions = {}
        # Overwrite with latest decision for this run_id
        decisions[run_id] = {
            'decision': decision,
            'chat_id': chat_id,
            'ts': _api_request('getMe', {})['result']['username'] if False else '',  # placeholder
        }
        _TOLLGATE_FILE.write_text(json.dumps(decisions, indent=2, default=str), encoding='utf-8')
    except Exception as e:
        print(f"[telegram] Failed to write tollgate decision: {e}")


def _tollgate_polling_loop() -> None:
    """
    Background thread: polls Telegram every 2s for tollgate callback_query updates.
    Uses non-blocking getUpdates — offset tracked globally via _INBOX_LAST_ID
    so it never competes with poll_inbox().
    """
    global _tollgate_listener_running, _INBOX_LAST_ID
    while _tollgate_listener_running:
        try:
            # Use offset=_INBOX_LAST_ID+1 (same state as poll_inbox)
            updates = _api_request('getUpdates', {
                'offset':  _INBOX_LAST_ID + 1,
                'timeout': 0,  # non-blocking — returns immediately
            })
            if not (updates and updates.get('ok')):
                time.sleep(2)
                continue

            for upd in updates.get('result', []):
                _INBOX_LAST_ID = upd.get('update_id', _INBOX_LAST_ID)
                cq = upd.get('callback_query', {})
                if not cq:
                    continue
                data = cq.get('data', '')
                if not data or not data.startswith('tollgate:'):
                    continue
                parts = data.split(':')
                if len(parts) != 3:
                    continue
                _, cmd, run_id = parts
                chat_id = str(cq.get('message', {}).get('chat', {}).get('id', ''))
                callback_id = cq.get('id', '')
                answer_callback(callback_id, f"Received: /{cmd} for {run_id}", show_alert=True)
                _tollgate_callback_handler(cmd, run_id, chat_id)

        except Exception as e:
            print(f"[telegram tollgate loop] error: {e}")
            time.sleep(3)
        else:
            time.sleep(2)


def start_tollgate_listener() -> None:
    """
    Start the background Telegram polling thread for tollgate button callbacks.
    Call once at startup. Thread runs until the process exits.
    Idempotent — safe to call multiple times.
    """
    global _tollgate_listener_running
    if _tollgate_listener_running:
        return
    _tollgate_listener_running = True
    t = threading.Thread(target=_tollgate_polling_loop, daemon=True)
    t.start()
    print("[telegram] Tollgate listener started — button callbacks will be processed")


def get_tollgate_decision(run_id: str, timeout: float = None) -> Optional[dict]:
    """
    Check if Kay tapped a button for the given run_id by reading data/tollgate_decisions.json.
    Returns {'decision': 'proceed'|'escalate'|'abort', 'chat_id': '...'}
    or None if no decision yet (blocks up to timeout seconds, or forever if timeout=None).
    """
    deadline = time.time() + timeout if timeout else None
    while True:
        if _TOLLGATE_FILE.exists():
            try:
                decisions = json.loads(_TOLLGATE_FILE.read_text(encoding='utf-8'))
                if run_id in decisions:
                    result = decisions.pop(run_id)
                    _TOLLGATE_FILE.write_text(json.dumps(decisions, indent=2, default=str), encoding='utf-8')
                    return result
            except Exception as e:
                print(f"[telegram] Error reading tollgate decisions: {e}")
        if deadline and time.time() >= deadline:
            return None
        time.sleep(0.5)


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


def _edit_tollgate_message(chat_id: str, message_id: int, action: str, run_id: str):
    """Replace tollgate buttons with the decision that was made."""
    emoji_map = {'proceed': '✅', 'escalate': '🔍', 'abort': '🚫'}
    label_map  = {'proceed': 'PROCEEDING', 'escalate': 'ESCALATING', 'abort': 'ABORTED'}
    emoji = emoji_map.get(action, '❓')
    label = label_map.get(action, action.upper())

    new_text = (
        f"{emoji} <b>{label}</b>\n"
        f"─────────────────────\n"
        f"<i>Kay's decision received for run {run_id}</i>\n"
        f"<i>Researcher agent will act on this shortly.</i>"
    )
    _api_request('editMessageText', {
        'chat_id':    chat_id,
        'message_id': message_id,
        'text':       new_text,
        'parse_mode': 'HTML',
    })
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

# Whitelist: accept commands only from these chat IDs
_ALLOWED_CHATS = {'8750722880', '-5581171035'}

# Path map for key storage
_KEY_PATHS = {
    'finnhub':      Path(r'E:\Me\TradingAgent\config\finnhub_key.enc'),
    'alphavantage': Path(r'E:\Me\TradingAgent\config\alphavantage_key.enc'),
}


def _store_key(provider: str, key: str) -> bool:
    """
    Store an API key securely using DPAPI.
    Pipelines plaintext → SecureString → encrypted bytes directly (no BOM, no file I/O via PS).
    """
    path = _KEY_PATHS.get(provider.lower())
    if not path:
        return False
    # Escape key for PowerShell single-quote context
    escaped = key.replace("'", "''")
    ps = f"$k='{escaped}'; ConvertTo-SecureString $k -AsPlainText -Force | ConvertFrom-SecureString"
    try:
        r = subprocess.run(
            ['powershell', '-Command', ps],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            print(f"[_store_key] PS error: {r.stderr}")
            return False
        encrypted = r.stdout
        # Write bytes directly — no BOM
        path.write_bytes(encrypted.encode('utf-8'))
        return True
    except Exception as e:
        print(f"[_store_key] exception: {e}")
        return False


def _reply_to_chat(chat_id: str, text: str):
    """Send a reply message to a specific Telegram chat."""
    _api_request('sendMessage', {
        'chat_id':    chat_id,
        'text':       text,
        'parse_mode': 'Markdown',
    })


def _call_pm_webhook(command: str, chat_id: str):
    """Fire the PM-Agent webhook via the local dashboard."""
    try:
        import requests
        requests.post(
            "http://localhost:5050/pm-webhook",
            json={"command": command, "triggered_by": chat_id},
            timeout=5,
        )
    except Exception:
        pass  # non-critical — PM-Agent falls back to polling


def _handle_approve(chat_id: str, symbol: str):
    """Handle /approve SYMBOL — open position and notify Kay."""
    signals_file = Path(r'E:\Me\TradingAgent\data\signals_live.json')
    if not signals_file.exists():
        _reply_to_chat(chat_id, f"⚠️ No signals found — nothing to approve for {symbol}")
        return

    try:
        signals = json.loads(signals_file.read_text(encoding='utf-8'))
    except Exception:
        _reply_to_chat(chat_id, f"⚠️ Could not read signals file for {symbol}")
        return

    sig = None
    for s in (signals if isinstance(signals, list) else [signals]):
        if s.get('symbol', '').upper() == symbol.upper() and not s.get('decided'):
            sig = s
            break

    if not sig:
        _reply_to_chat(chat_id, f"⚠️ No pending signal found for {symbol}")
        return

    # Try to open the position via trader_agent
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from trader_agent import open_position as trader_open
        opened = trader_open(
            symbol=sig['symbol'],
            direction='long',
            entry_price=sig['price'],
            quantity=sig.get('qty', 100),
            target=sig.get('target'),
            stop=sig.get('stop'),
            signal_score=sig.get('score', 4.5),
            rules_applied=[f"P{i}" for i in range(1, 6) if sig.get(f'p{i}')],
            signal_type=f"TV Webhook (Kay approved)",
        )
    except Exception as e:
        opened = False
        print(f"[telegram approve] trader_agent error: {e}")

    # Mark signal as decided
    _mark_signal_decided(symbol.upper(), 'APPROVED')

    if opened:
        _reply_to_chat(chat_id,
            f"✅ *APPROVED — {symbol}*\n"
            f"Position opened. Watch for exit alerts.")
    else:
        _reply_to_chat(chat_id,
            f"⚠️ {symbol} already in position or trade rejected.\n"
            f"Check positions.json.")


def _handle_deny(chat_id: str, symbol: str):
    """Handle /deny SYMBOL — skip signal and notify Kay."""
    _mark_signal_decided(symbol.upper(), 'DENIED')
    _reply_to_chat(chat_id, f"❌ *DENIED — {symbol}*\nSignal skipped.")


def _mark_signal_decided(symbol: str, decision: str):
    """Mark a signal as decided in signals_live.json."""
    signals_file = Path(r'E:\Me\TradingAgent\data\signals_live.json')
    if not signals_file.exists():
        return
    try:
        signals = json.loads(signals_file.read_text(encoding='utf-8'))
        changed = False
        for s in (signals if isinstance(signals, list) else [signals]):
            if s.get('symbol', '').upper() == symbol.upper() and not s.get('decided'):
                s['decided'] = True
                s['decision'] = decision
                changed = True
        if changed:
            signals_file.write_text(json.dumps(signals, indent=2, default=str), encoding='utf-8')
    except Exception as e:
        print(f"[telegram] Error marking {symbol} decided: {e}")


def poll_callbacks(callback_handler=None):
    """
    Background thread: polls Telegram for updates every 5s.
    - callback_query (button press) → callback_handler
    - text message /key commands from allowed chats
    Uses exponential backoff on failures so Docker network stalls don't spam logs.
    """
    global _last_update_id
    backoff = 1  # seconds, doubles on each failure up to 60s

    while not _stop_polling.wait(backoff):
        backoff = 1  # reset on successful wait (no failure)
        try:
            updates = _api_request('getUpdates', {
                'offset':  _last_update_id + 1,
                'timeout': 0,   # non-blocking — Telegram returns instantly
            })
            if not (updates and updates.get('ok')):
                continue

            backoff = 1  # reset backoff on success

            for upd in updates.get('result', []):
                _last_update_id = upd.get('update_id', _last_update_id)

                # ── Callback query (button press) ──────────────────────────────
                cq = upd.get('callback_query', {})
                if cq:
                    callback_id = cq.get('id', '')
                    msg = cq.get('message', {})
                    chat_id    = str(msg.get('chat', {}).get('id', ''))
                    message_id = msg.get('message_id', 0)
                    data       = cq.get('data', '')

                    if not data:
                        continue

                    # ── Tollgate buttons: tollgate:<action>:<run_id> ───────────
                    if data.startswith('tollgate:'):
                        parts = data.split(':')
                        if len(parts) == 3:
                            _, action, run_id = parts
                            label_map = {
                                'proceed':  'Proceeding with research — auto-accepted',
                                'escalate': 'Escalating — lead researcher will dig deeper',
                                'abort':    'Research aborted',
                            }
                            answer_callback(
                                callback_id,
                                label_map.get(action, f'Tollgate: {action}'),
                                show_alert=True,
                            )
                            _edit_tollgate_message(chat_id, message_id, action, run_id)
                            # Write to shared file so researcher can read without competing polls
                            _write_tollgate_decision(run_id, action, chat_id)
                            if callback_handler:
                                callback_handler(f'TOLLGATE_{action.upper()}', run_id, chat_id, message_id)
                            print(f"[telegram] Tollgate: {action.upper()} {run_id}")
                            continue

                    # ── Signal buttons: approve:<sym>:<price>:<score> ───────────
                    parts = data.split(':')
                    if len(parts) != 4:
                        continue
                    action, symbol, price_str, score_str = parts
                    price = float(price_str)
                    score = float(score_str)

                    _pending_signals.pop(message_id, None)
                    label_map = {'approve': f'Approved {symbol} at ${price}',
                                 'deny':    f'Denied {symbol}',
                                 'skip':    f'Skipped {symbol}'}
                    answer_callback(callback_id, label_map.get(action, f'{action} {symbol}'), show_alert=True)
                    edit_message_buttons(chat_id, message_id, action, symbol, price)
                    if callback_handler:
                        callback_handler(action.upper(), symbol, price, score, chat_id, message_id)
                    print(f"[telegram] Button: {action.upper()} {symbol}")
                    continue

                # ── Text message (/key commands) ───────────────────────────────
                msg = upd.get('message', {})
                if not msg:
                    continue

                chat_id = str(msg.get('chat', {}).get('id', ''))
                text    = (msg.get('text', '') or msg.get('caption', '')).strip()

                print(f"[telegram] Text msg from {chat_id}: {text[:60]}")

                if chat_id not in _ALLOWED_CHATS:
                    continue

                if text.startswith('/pm '):
                    parts = text.split()
                    cmd = parts[1].lower() if len(parts) >= 2 else ''
                    if cmd == 'check':
                        _reply_to_chat(chat_id, "🔍 PM-Agent pipeline check triggered")
                        _call_pm_webhook('check', chat_id)
                    elif cmd == 'status':
                        _reply_to_chat(chat_id, "📊 PM-Agent status check triggered")
                        _call_pm_webhook('status', chat_id)
                    else:
                        _reply_to_chat(chat_id, "Usage: `/pm check` | `/pm status`")
                    continue

                if not text.startswith('/key'):
                    # ── /approve SYMBOL ─────────────────────────────────────────
                    if text.startswith('/approve'):
                        # Strip @botname suffix if present (e.g. /approve@Marvless01_bot)
                        cmd = text.split()[0].split('@')[0]
                        parts = text.split()
                        if len(parts) < 2:
                            _reply_to_chat(chat_id, "Usage: `/approve SYMBOL`")
                            continue
                        symbol = parts[1].upper().strip()
                        _handle_approve(chat_id, symbol)
                        continue

                    # ── /deny SYMBOL ───────────────────────────────────────────
                    if text.startswith('/deny'):
                        cmd = text.split()[0].split('@')[0]
                        parts = text.split()
                        if len(parts) < 2:
                            _reply_to_chat(chat_id, "Usage: `/deny SYMBOL`")
                            continue
                        symbol = parts[1].upper().strip()
                        _handle_deny(chat_id, symbol)
                        continue

                    continue

                # Parse: /key finnhub YOUR_KEY_HERE
                parts = text.split(' ', 2)
                if len(parts) < 3:
                    _reply_to_chat(chat_id,
                        "Usage: `/key finnhub YOUR_API_KEY`\n"
                        "Example: `/key finnhub abc123xyz`")
                    continue

                _, provider, api_key = parts
                api_key = api_key.strip()

                if provider.lower() not in _KEY_PATHS:
                    _reply_to_chat(chat_id,
                        f"Unknown provider: `{provider}`\n"
                        "Use `finnhub` or `alphavantage`.")
                    continue

                if len(api_key) < 8:
                    _reply_to_chat(chat_id, "That doesn't look like a valid API key. Try again.")
                    continue

                ok = _store_key(provider, api_key)
                if ok:
                    _reply_to_chat(chat_id,
                        f"✅ *{provider.capitalize()}* key stored securely.\n"
                        f"File: `E:\\Me\\TradingAgent\\config\\{provider.lower()}_key.enc`\n\n"
                        f"Restarting dashboard will activate it.")
                    print(f"[telegram] Key stored: {provider}")
                else:
                    _reply_to_chat(chat_id,
                        f"❌ Failed to store {provider} key. Check logs.")

        except Exception as e:
            print(f"[telegram poll] error: {e}")
            backoff = min(backoff * 2, 60)  # double backoff on failure, cap at 60s


def start_polling(callback_handler=None):
    """Start the polling thread. Call once at app startup."""
    t = threading.Thread(target=poll_callbacks, args=(callback_handler,), daemon=True)
    t.start()
    print("[telegram] Polling thread started — listening for button presses and /key commands")


def stop_polling():
    _stop_polling.set()


# ── Inbox poller (for Mavis session to call directly) ─────────────────────────
_INBOX_LAST_ID = 0
_TOLLGATE_COMMANDS = {'proceed', 'escalate', 'abort'}


def poll_inbox(tollgate_handler=None) -> list:
    """
    Check Telegram for new messages. Returns list of message dicts.
    Safe to call from any context (Mavis session, cron, etc.).

    Args:
        tollgate_handler: Optional callback(cmd: str, run_id: str, chat_id: str).
            Called immediately when a tollgate command is received (/proceed, /escalate, /abort).
            If provided, the command is processed and acknowledged without returning in results.
    """
    global _INBOX_LAST_ID
    try:
        updates = _api_request('getUpdates', {
            'offset':  _INBOX_LAST_ID + 1,
            'timeout': 0,  # non-blocking
        })
        if not (updates and updates.get('ok')):
            return []
        results = []
        for upd in updates.get('result', []):
            uid = upd.get('update_id', 0)
            _INBOX_LAST_ID = max(_INBOX_LAST_ID, uid)

            # ── Text message ───────────────────────────────────────────────────
            if 'message' in upd:
                m = upd['message']
                chat_id = str(m.get('chat', {}).get('id', ''))
                text    = (m.get('text', '') or m.get('caption', '')).strip()

                # ── Tollgate command: /proceed <run_id>, /escalate <run_id>, /abort <run_id> ─
                if text.startswith('/') and tollgate_handler:
                    parts = text.strip().split(' ', 1)
                    cmd   = parts[0][1:]   # strip leading '/'
                    run_id = parts[1] if len(parts) > 1 else ""

                    if cmd in _TOLLGATE_COMMANDS and run_id:
                        emoji_map   = {'proceed': '✅', 'escalate': '🔍', 'abort': '🚫'}
                        label_map   = {'proceed': 'Proceeding', 'escalate': 'Escalating', 'abort': 'Aborting'}
                        # Acknowledge Kay immediately
                        _reply_to_chat(chat_id,
                            f"{emoji_map[cmd]} <b>{label_map[cmd]}</b>\n"
                            f"Run <code>{run_id}</code> — researcher will act on this now."
                        )
                        tollgate_handler(cmd, run_id, chat_id)
                        continue   # don't add to results — already handled

                # Normal message — add to results
                results.append({
                    'update_id': uid,
                    'chat_id':   chat_id,
                    'chat_name': m.get('chat', {}).get('title', '') or m.get('chat', {}).get('first_name', ''),
                    'text':      text,
                    'timestamp': m.get('date', 0),
                })

            # ── Callback query ─────────────────────────────────────────────────
            elif 'callback_query' in upd:
                cq = upd['callback_query']
                results.append({
                    'update_id': uid,
                    'chat_id':   str(cq.get('message', {}).get('chat', {}).get('id', '')),
                    'type':      'callback',
                    'data':      cq.get('data', ''),
                    'callback_id': cq.get('id', ''),
                })

        return results
    except Exception as e:
        print(f'[telegram inbox] poll error: {e}')
        return []

