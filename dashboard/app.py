"""
Kay's Day Trade Dashboard — Flask Backend
=======================================
Serves the live dashboard, runs scanner, handles decisions.
"""

import os, json, sys, threading, time
from pathlib import Path
from datetime import datetime, date
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

# ── Local imports ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from trading_agent.fincept_connector import get_batch_quotes, get_info, get_historical
from trading_agent.premarket_screener import check_pillars, DEFAULT_UNIVERSE
from trading_agent.news_providers import get_company_news, score_catalyst
from trading_agent.tradingview_connector import fetch_ross_universe, tv_to_signal_rows
from trading_agent.telegram_sender import (
    send_alert, send_signal_with_buttons, start_polling, _pending_signals
)

app = Flask(__name__, template_folder='static', static_folder='static')
CORS(app)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
DATA_DIR    = BASE_DIR / 'data'
DASH_DATA   = Path(__file__).parent / 'data'
DASH_DATA.mkdir(exist_ok=True)

WATCHLIST_FILE = DASH_DATA / 'watchlist_live.json'
SIGNALS_FILE   = DASH_DATA / 'signals_live.json'
DECISIONS_FILE = DASH_DATA / 'decisions.json'
PREMARKET_DIR  = DATA_DIR / 'watchlists'


def load_premarket_watchlist():
    """Load today's premarket watchlist if it exists."""
    today = date.today().strftime('%Y%m%d')
    candidates = [
        PREMARKET_DIR / f'watchlist_{today}.csv',
        DATA_DIR / 'watchlists' / f'watchlist_{today}.csv',
    ]
    for path in candidates:
        if path.exists():
            try:
                import csv
                rows = []
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sym = row.get('symbol', '').strip()
                        if not sym:
                            continue
                        rows.append({
                            'symbol':     sym,
                            'short_name': row.get('short_name', sym),
                            'price':      float(row.get('price') or 0),
                            'gap_pct':    float(row.get('gap_pct') or 0),
                            'rel_vol':    float(row.get('rel_vol') or 0),
                            'float_m':    float(row.get('float_m') or 0),
                            'total_score': float(row.get('total_score') or 0),
                            'p4_catalyst': float(row.get('p4_catalyst') or 0),
                            'news_summary': row.get('news_summary', ''),
                            'risk_flags': [],
                            'pillars':    {},
                            'source':     'premarket',
                        })
                if rows:
                    rows.sort(key=lambda x: x['total_score'], reverse=True)
                    print(f"[dashboard] Loaded premarket watchlist: {len(rows)} stocks from {path.name}")
                    return rows
            except Exception as e:
                print(f"[dashboard] Failed to load premarket watchlist: {e}")
    return []

# ── State ─────────────────────────────────────────────────────────────────────
state = {
    'watchlist':    [],
    'signals':      [],
    'selected':     None,
    'decisions':    [],
    'pnl':          0.0,
    'last_scan':    None,
    'market_open':  False,
}


def berlin_now():
    """Return current time in Berlin (UTC+2)."""
    return datetime.now()


def market_status():
    """Check if US market is open (15:30-21:00 Berlin Mon-Fri)."""
    now = berlin_now()
    weekday = now.weekday()  # 0=Mon, 4=Fri
    hour, minute = now.hour, now.minute
    total_mins = hour * 60 + minute
    open_mins  = 15 * 60 + 30   # 15:30
    close_mins = 21 * 60         # 21:00
    return weekday < 5 and open_mins <= total_mins < close_mins


def load_decisions():
    """Load past decisions from disk."""
    if DECISIONS_FILE.exists():
        with open(DECISIONS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_decisions(decisions):
    """Save decisions to disk."""
    with open(DECISIONS_FILE, 'w') as f:
        json.dump(decisions[-100:], f, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_scan(min_score=2.5, symbols=None):
    """
    Run the Five Pillars scanner on all symbols.
    Data source: TradingView Premium API (real-time) first, fallback to yfinance.
    Returns ranked signals.
    """
    today_str = berlin_now().strftime('%Y-%m-%d %H:%M')

    # ── Step 1: Try TV Premium API ────────────────────────────────────────────
    tv_rows = []
    if symbols is None:
        tv_df = fetch_ross_universe()
        if not tv_df.empty:
            tv_rows = tv_to_signal_rows(tv_df)
            print(f"[scanner] TV Premium: {len(tv_rows)} real-time setups")

    # ── Step 2: Fallback to yfinance with explicit symbols ───────────────────
    if not tv_rows:
        if symbols is None:
            symbols = DEFAULT_UNIVERSE
        quotes_raw = {}
        try:
            raw = get_batch_quotes(symbols)
            for q in (raw if isinstance(raw, list) else []):
                sym = q.get('symbol', '')
                if sym:
                    quotes_raw[sym] = q
        except Exception as e:
            print(f"[scanner] quote error: {e}")
            return []

    # ── Step 3: Score each symbol ──────────────────────────────────────────────
    results = []

    # 3a: Score TV rows directly (price/gap already enriched from TV)
    for row in tv_rows:
        sym = row['symbol']
        price = row['price']
        prev_close = price / (1 + row['gap_pct'] / 100) if row['gap_pct'] else price
        quote = {'price': price, 'previous_close': prev_close,
                 'volume': row.get('volume', 0)}

        try:
            info = get_info(sym)
        except Exception:
            info = {}

        try:
            news_result = get_company_news(sym, count=10)
        except Exception:
            news_result = {'articles': [], 'recent_count': 0, 'top_headline': '',
                           'provider': 'none', 'sentiment_score': 0, 'bullish_pct': 0}

        pillars = check_pillars(quote, info)
        catalyst = score_catalyst(news_result)
        pillars['P4_catalyst']   = catalyst['P4_catalyst']
        pillars['news_summary']   = catalyst['news_summary']
        pillars['news_count']     = catalyst['news_count']
        pillars['news_provider']  = catalyst.get('news_provider', 'none')

        total = pillars['score'] + catalyst['P4_catalyst']

        results.append({
            'symbol':       sym,
            'short_name':   row.get('short_name', ''),
            'price':        price,
            'gap_pct':      round(pillars['gap_pct'], 1),
            'rel_vol':      round(pillars['rel_vol'], 1),
            'float_m':      pillars.get('float_m'),
            'total_score':  round(total, 1),
            'pillars':      pillars['pillars'],
            'p4_catalyst':  round(catalyst['P4_catalyst'], 2),
            'news_summary':  catalyst['news_summary'],
            'news_count':    catalyst['news_count'],
            'news_provider': catalyst.get('news_provider', 'none'),
            'risk_flags':    pillars.get('risk_flags', []),
            'pillars_detail': pillars,
            'scan_time':    today_str,
            'decided':      False,
            'decision':     None,
            'source':       'tv_api',
        })

    # 3b: Score yfinance fallback symbols
    for sym in (symbols or []):
        if tv_rows and sym in [r['symbol'] for r in tv_rows]:
            continue  # already scored via TV
        q = quotes_raw.get(sym) if not tv_rows else None
        if not tv_rows and (not q or not q.get('price')):
            continue

        if not tv_rows:
            price = q.get('price', 0)
        else:
            continue

        prev_close = q.get('previous_close', price) if not tv_rows else price

        try:
            info = get_info(sym)
        except Exception:
            info = {}

        try:
            news_result = get_company_news(sym, count=10)
        except Exception:
            news_result = {'articles': [], 'recent_count': 0, 'top_headline': '',
                           'provider': 'none', 'sentiment_score': 0, 'bullish_pct': 0}

        pillars = check_pillars(q, info)
        catalyst = score_catalyst(news_result)
        pillars['P4_catalyst']   = catalyst['P4_catalyst']
        pillars['news_summary']  = catalyst['news_summary']
        pillars['news_count']    = catalyst['news_count']
        pillars['news_provider'] = catalyst.get('news_provider', 'none')

        total = pillars['score'] + catalyst['P4_catalyst']

        results.append({
            'symbol':       sym,
            'short_name':   pillars.get('short_name', ''),
            'price':        round(q.get('price', 0), 2),
            'gap_pct':      round(pillars['gap_pct'], 1),
            'rel_vol':      round(pillars['rel_vol'], 1),
            'float_m':      pillars.get('float_m'),
            'total_score':  round(total, 1),
            'pillars':      pillars['pillars'],
            'p4_catalyst':  round(catalyst['P4_catalyst'], 2),
            'news_summary':  catalyst['news_summary'],
            'news_count':    catalyst['news_count'],
            'news_provider': catalyst.get('news_provider', 'none'),
            'risk_flags':    pillars.get('risk_flags', []),
            'pillars_detail': pillars,
            'scan_time':    today_str,
            'decided':      False,
            'decision':     None,
            'source':       'yfinance',
        })

    # Sort by score
    results.sort(key=lambda x: x['total_score'], reverse=True)
    return [r for r in results if r['total_score'] >= min_score]

    results.sort(key=lambda x: x['total_score'], reverse=True)
    return results


# Track symbols we've already alerted today (avoid spamming same signal)
_alerted_today: set = set()
_last_alert_date: str = ''


def scan_thread():
    """Background scanner — runs every 5 minutes during market hours."""
    global _alerted_today, _last_alert_date
    while True:
        if market_status():
            today = berlin_now().strftime('%Y-%m-%d')
            if today != _last_alert_date:
                _alerted_today = set()
                _last_alert_date = today
                # Load premarket watchlist from Richard's morning scan
                premarket = load_premarket_watchlist()
                if premarket:
                    state['watchlist'] = premarket
                    print(f"[scanner] Loaded {len(premarket)} premarket signals for {today}")

            try:
                signals = run_scan(min_score=2.5)
                state['signals']    = signals
                state['watchlist']  = signals
                state['last_scan']  = berlin_now().strftime('%H:%M')
                state['market_open'] = True

                # Fire Telegram alert for new top signals (score >= 3.5, not yet alerted)
                for sig in signals:
                    sym = sig['symbol']
                    if sig['total_score'] >= 3.5 and sym not in _alerted_today:
                        _alerted_today.add(sym)
                        try:
                            send_signal_with_buttons(
                                symbol    = sig['symbol'],
                                action    = 'BUY',
                                price     = sig['price'],
                                gap       = sig['gap_pct'],
                                score     = sig['total_score'],
                                rel_vol   = sig['rel_vol'],
                                float_m   = sig.get('float_m') or 0,
                                notes     = sig.get('news_summary', ''),
                                risk_flags= sig.get('risk_flags', []),
                            )
                            print(f"[scanner] Telegram alert sent for {sym} score={sig['total_score']}")
                        except Exception as te:
                            print(f"[scanner] Telegram alert failed: {te}")

                print(f"[scanner] scanned {len(signals)} signals at {state['last_scan']}")
            except Exception as e:
                print(f"[scanner] error: {e}")
        else:
            state['market_open'] = berlin_now().strftime('%H:%M') >= '14:00'
        time.sleep(300)  # 5 min


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

def on_telegram_button(action: str, symbol: str, price: float, score: float,
                       chat_id: str, message_id: int):
    """
    Called by the Telegram polling thread when Kay taps a button.
    Records the decision directly in state (no HTTP round-trip).
    """
    global state
    decision = {
        'timestamp': berlin_now().isoformat(),
        'symbol':    symbol,
        'action':   action,
        'price':    price,
        'notes':    'via Telegram button',
        'score':    score,
    }
    # Mark signal as decided
    for s in state['signals']:
        if s['symbol'] == symbol:
            s['decided']  = True
            s['decision'] = action
            break

    state['decisions'].append(decision)
    save_decisions(state['decisions'])
    print(f"[telegram] Decision recorded: {action} {symbol} @ ${price}")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Serve the dashboard HTML."""
    return render_template('dashboard.html')


@app.route('/api/state')
def api_state():
    """Return current dashboard state."""
    return jsonify({
        'watchlist':    state['watchlist'],
        'signals':      state['signals'],
        'selected':     state['selected'],
        'decisions':    state['decisions'][-20:],
        'pnl':          round(state['pnl'], 2),
        'last_scan':    state['last_scan'],
        'market_open':   state['market_open'],
        'berlin_time':  berlin_now().strftime('%H:%M'),
    })


@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Manually trigger a scan."""
    min_score = float(request.json.get('min_score', 2.5)) if request.json else 2.5
    symbols    = request.json.get('symbols') if request.json else None
    signals    = run_scan(min_score=min_score, symbols=symbols)
    state['signals']   = signals
    state['watchlist'] = signals
    state['last_scan'] = berlin_now().strftime('%H:%M')
    return jsonify({'ok': True, 'count': len(signals)})


@app.route('/api/select/<symbol>')
def api_select(symbol):
    """Select a symbol to view details."""
    sig = next((s for s in state['signals'] if s['symbol'] == symbol), None)
    if sig:
        # Get intraday bars for the selected stock
        bars = []
        try:
            raw_bars = get_historical(symbol, period='1d', interval='5m')
            bars = raw_bars[-78:] if len(raw_bars) > 78 else raw_bars  # last ~6.5h
        except Exception:
            pass
        state['selected'] = sig
        return jsonify({'ok': True, 'signal': sig, 'bars': bars})
    return jsonify({'ok': False, 'error': 'symbol not found'})


@app.route('/api/decision', methods=['POST'])
def api_decision():
    """
    Record a trade decision.
    Body: {symbol, action: 'APPROVE'|'DENY'|'SKIP', price, notes}
    """
    data = request.json
    action = data.get('action', '').upper()
    symbol = data.get('symbol', '')
    price  = data.get('price', 0)

    if action not in ('APPROVE', 'DENY', 'SKIP'):
        return jsonify({'ok': False, 'error': 'invalid action'})

    decision = {
        'timestamp':   berlin_now().isoformat(),
        'symbol':      symbol,
        'action':      action,
        'price':       price,
        'notes':       data.get('notes', ''),
        'score':       data.get('score', 0),
    }

    # Mark signal as decided
    for s in state['signals']:
        if s['symbol'] == symbol:
            s['decided']  = True
            s['decision'] = action
            break

    state['decisions'].append(decision)
    save_decisions(state['decisions'])

    # Send Telegram alert
    emoji = '✅' if action == 'APPROVE' else ('❌' if action == 'DENY' else '⏭️')
    msg = f"{emoji} **{action}** — {symbol} @ ${price}\nScore: {data.get('score', '?')}/5\nNote: {data.get('notes', '')}"
    send_alert(msg)

    return jsonify({'ok': True, 'decision': decision})


@app.route('/api/history')
def api_history():
    """Return full decision history."""
    return jsonify(state['decisions'][-50:])


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Load saved decisions
    state['decisions'] = load_decisions()

    # Run initial scan
    print("Running initial scan...")
    state['signals']   = run_scan(min_score=2.5)
    state['watchlist'] = state['signals']
    state['last_scan'] = berlin_now().strftime('%H:%M')

    # Start background scanner thread
    t = threading.Thread(target=scan_thread, daemon=True)
    t.start()

    # Start Telegram polling thread (listens for button presses)
    start_polling(callback_handler=on_telegram_button)

    print(f"Dashboard starting at http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=False)
