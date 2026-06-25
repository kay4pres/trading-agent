r"""
telegram_sender.py
==================
Sends alert messages to Kay via @Marvless01_bot.

Token: E:\Me\TradingAgent\config\telegram_token.enc (PowerShell SecureString, DPAPI)
Chat ID: 8750722880

Usage:
    from telegram_sender import send_alert
    send_alert("SOFI BUY signal — gap +3.2%, score 4.5")
"""

import json, subprocess, sys, os
from pathlib import Path
from typing import Optional

TOKEN_PATH = Path(r'E:\Me\TradingAgent\config\telegram_token.enc')
CHAT_ID    = '-5581171035'  # Kay's Trading Team group
API_BASE   = 'https://api.telegram.org'


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


def send_message(text: str, parse_mode: str = 'Markdown') -> bool:
    """Send a text message to Kay's Telegram chat."""
    token = _get_token()
    if not token:
        print("[telegram_sender] ERROR: could not decrypt token")
        return False

    url = f"{API_BASE}/bot{token}/sendMessage"
    payload = {
        'chat_id':    CHAT_ID,
        'text':       text,
        'parse_mode': parse_mode,
    }

    try:
        import urllib.request
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get('ok'):
                return True
            print(f"[telegram_sender] API error: {result.get('description')}")
            return False
    except Exception as e:
        print(f"[telegram_sender] Error: {e}")
        return False


def send_alert(message: str) -> bool:
    """High-level alert: sends a formatted message to Kay."""
    header = "📊 *Kay's Trading Agent*\n"
    return send_message(header + message)


def send_signal(symbol: str, action: str, price: float, gap: float,
                score: float, notes: str = '') -> bool:
    """Format and send a trade signal."""
    emoji = "🟢" if action.upper() == "BUY" else "🔴"
    msg = (
        f"{emoji} *{action} SIGNAL*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Stock: *{symbol}*\n"
        f"Price: ${price:.2f}\n"
        f"Gap:   {gap:+.1f}%\n"
        f"Score: {score:.1f}/5\n"
    )
    if notes:
        msg += f"\nNote: {notes}"
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


if __name__ == '__main__':
    # Test: send a quick ping
    ok = send_alert("✅ Telegram alerts are live! Bot connected to Kay's Trading Agent.")
    print("Send result:", "OK" if ok else "FAILED")
