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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

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
    'positions':     [],   # open positions from live_event_loop
    'trades':       [],   # closed trades from live_event_loop
    'bull_bear':     [],  # recent Bull/Bear verdicts
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


def load_trading_engine_state():
    """
    Load positions and Bull/Bear results from the live_event_loop pipeline.
    Called every minute by scan_thread to keep dashboard in sync.
    """
    global state

    # ── Positions ──────────────────────────────────────────────────────────────
    positions_file = DATA_DIR / 'positions.json'
    if positions_file.exists():
        try:
            with open(positions_file, 'r') as f:
                data = json.load(f)

            open_pos = []
            closed = []
            for sym, pos in data.get('positions', {}).items():
                if pos.get('status') == 'OPEN':
                    open_pos.append({'symbol': sym, **pos})
            for trade in data.get('history', []):
                closed.append(trade)

            # Compute live P&L for open positions
            if open_pos:
                syms = [p['symbol'] for p in open_pos]
                try:
                    quotes = get_batch_quotes(syms)
                    price_map = {q.get('symbol'): q.get('price', 0) for q in (quotes if isinstance(quotes, list) else [])}
                except Exception:
                    price_map = {}

                for p in open_pos:
                    live = price_map.get(p['symbol'], p.get('entry_price', 0))
                    p['live_price'] = round(live, 4)
                    p['live_pnl'] = round((live - p.get('entry_price', 0)) * p.get('quantity', 100), 2)
            else:
                price_map = {}

            state['positions'] = open_pos
            state['trades']   = closed[-10:]  # last 10 closed
            total_pnl = sum(t.get('pnl', 0) for t in closed)
            state['pnl'] = round(total_pnl, 2)

        except Exception as e:
            print(f"[dashboard] positions error: {e}")

    # ── Bull/Bear results ───────────────────────────────────────────────────
    bb_file = DATA_DIR / 'bull_bear_results.json'
    if bb_file.exists():
        try:
            with open(bb_file, 'r') as f:
                bb_data = json.load(f)
            debates = bb_data.get('debates', [])
            # Keep last 5, strip full LLM text (too long for UI)
            trimmed = []
            for d in debates[-5:]:
                trimmed.append({
                    'symbol':      d.get('symbol', '?'),
                    'verdict':     d.get('verdict', '?'),
                    'conviction':  d.get('conviction', 0),
                    'debated_at':  d.get('debated_at', ''),
                    'bull_short':  (d.get('bull', '') or '')[:120],
                    'bear_short':  (d.get('bear', '') or '')[:120],
                    'rm_short':    (d.get('research_manager', '') or '')[:200],
                })
            state['bull_bear'] = trimmed
        except Exception as e:
            print(f"[dashboard] bull_bear error: {e}")


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
                    state['signals']   = premarket  # renderWatchlist reads state.signals
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

                # Sync with live_event_loop pipeline
                load_trading_engine_state()
            except Exception as e:
                print(f"[scanner] error: {e}")
        else:
            state['market_open'] = berlin_now().strftime('%H:%M') >= '14:00'
        time.sleep(60)  # 1 min — also syncs positions/Bull-Bear


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

def on_telegram_button(action: str, symbol: str = None, price: float = None, score: float = None,
                       chat_id: str = None, message_id: int = None):
    """
    Called by the Telegram polling thread when Kay taps a button.
    Records the decision directly in state (no HTTP round-trip).
    APPROVE also calls Trader's open_position() to create a real tracked position.

    Handles two call signatures:
    - Signal buttons (6 args): action, symbol, price, score, chat_id, message_id
    - Tollgate buttons (4 args): action, run_id, chat_id, message_id  [symbol/price/score=None]
    """
    global state

    # ── Tollgate buttons: TOLLGATE_PROCEED | TOLLGATE_ESCALATE | TOLLGATE_ABORT ─
    if action.startswith('TOLLGATE_'):
        run_id = symbol  # symbol param carries run_id for tollgate calls
        decision = action.replace('TOLLGATE_', '').lower()
        tollgate_file = DATA_DIR / 'tollgate_decisions.json'
        try:
            if tollgate_file.exists():
                decisions = json.loads(tollgate_file.read_text(encoding='utf-8'))
            else:
                decisions = {}
            decisions[run_id] = {
                'decision': decision,
                'chat_id': str(chat_id or ''),
            }
            tollgate_file.write_text(json.dumps(decisions, indent=2, default=str), encoding='utf-8')
            print(f"[telegram] Tollgate decision written: /{decision} for run {run_id}")
        except Exception as e:
            print(f"[telegram] Failed to write tollgate decision: {e}")
        return

    # ── Signal buttons ───────────────────────────────────────────────────
    # Guard against None values from tollgate-style calls leaking through
    if symbol is None or price is None or score is None:
        print(f"[telegram] on_telegram_button skipped: missing signal fields (action={action})")
        return

    # ── APPROVE: open position in Trader ───────────────────────────────────
    if action == 'APPROVE':
        from trading_agent.trader_agent import open_position as trader_open
        target = round(price + 0.20, 2)
        stop   = round(price - 0.10, 2)
        trader_open(
            symbol=symbol,
            direction='long',
            entry_price=price,
            quantity=100,
            target=target,
            stop=stop,
            signal_score=score,
            rules_applied=['P1', 'P2', 'P3', 'P4', 'P5'],
            signal_type='First Pullback (dashboard APPROVE)'
        )
        print(f"[telegram] Position opened: {symbol} LONG 100 @ ${price}")

    # ── Record decision ────────────────────────────────────────────────────
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
        'positions':    state['positions'],
        'trades':      state['trades'],
        'bull_bear':   state['bull_bear'],
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
    """Select a symbol to view details — bar fetch has 10s timeout to prevent UI freeze."""
    sig = next((s for s in state['signals'] if s['symbol'] == symbol), None)
    if sig:
        bars = []
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(get_historical, symbol, '1d', '5m')
                raw_bars = future.result(timeout=10)  # 10s max — prevents UI freeze
            bars = raw_bars[-78:] if raw_bars and len(raw_bars) > 78 else (raw_bars or [])
        except FuturesTimeoutError:
            bars = []
            print(f"[WARN] get_historical timed out for {symbol}")
        except Exception as e:
            print(f"[WARN] get_historical failed for {symbol}: {e}")
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
# TRADINGVIEW WEBHOOK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/webhook/tradingview', methods=['POST'])
def webhook_tradingview():
    """
    Receive TradingView Pine Script alert → create a pending signal.

    TradingView sends JSON like:
    {
        "symbol":    "AAPL",
        "price":     "150.25",
        "action":    "buy",      # "buy" or "sell"
        "qty":       "100",      # optional, defaults to 100
        "target":    "150.75",   # optional
        "stop":      "149.75",   # optional
        "tv_alert":  "First Pullback AAPL",  # optional description
        "score":     "4.5",      # optional, Kay's manual confidence
    }

    Mode B (Kay-driven): adds to signals_live.json → Kay approves via dashboard/Telegram.
    Mode C (auto): run Bull/Bear inline → auto-open if conviction >= threshold.

    Returns 200 always (TradingView expects ACK within 5s).
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'ok': False, 'error': 'invalid JSON'}), 400

    symbol = (data.get('symbol') or '').upper().strip()
    if not symbol:
        return jsonify({'ok': False, 'error': 'no symbol'}), 400

    # ── Dedup: already in open position? ──────────────────────────────────
    positions_file = DATA_DIR / 'positions.json'
    if positions_file.exists():
        try:
            with open(positions_file) as f:
                pos_data = json.load(f)
            if symbol in pos_data.get('positions', {}):
                print(f"[Webhook TV] {symbol} already in position — ignoring")
                return jsonify({'ok': True, 'action': 'ignored', 'reason': 'already_held'}), 200
        except Exception:
            pass

    # ── Dedup: already debated / pending? ─────────────────────────────────
    signal_file = DATA_DIR / 'signals_live.json'
    if signal_file.exists():
        try:
            with open(signal_file) as f:
                existing = json.load(f)
            existing_list = existing if isinstance(existing, list) else [existing]
            for sig in existing_list:
                if sig.get('symbol', '').upper() == symbol and not sig.get('decided'):
                    print(f"[Webhook TV] {symbol} already pending — ignoring")
                    return jsonify({'ok': True, 'action': 'ignored', 'reason': 'already_pending'}), 200
        except Exception:
            pass

    # ── Parse fields ───────────────────────────────────────────────────────
    try:
        price = float(data.get('price', 0))
    except (TypeError, ValueError):
        price = 0.0

    try:
        qty = int(data.get('qty', 100))
    except (TypeError, ValueError):
        qty = 100

    target_raw = data.get('target')
    stop_raw   = data.get('stop')
    target = float(target_raw) if target_raw else round(price + 0.20, 2)
    stop   = float(stop_raw)   if stop_raw   else round(price - 0.10, 2)

    score = float(data.get('score', 4.5))

    tv_alert_desc = data.get('tv_alert', 'TradingView Pine Alert')

    # ── Build signal ──────────────────────────────────────────────────────
    signal = {
        'symbol':         symbol,
        'price':         price,
        'yesterday_close': price,    # TV alert doesn't carry yesterday close
        'gap_pct':       0.0,       # TV alert fires on chart pattern, not gap
        'float_m':       0.0,
        'rel_vol':       0.0,
        'rsi':           50.0,
        'news':          tv_alert_desc,
        'score':         score,
        'p1': 'manual', 'p2': 'manual', 'p3': 'manual', 'p4': 'manual', 'p5': 'manual',
        'target':        target,
        'stop':          stop,
        'qty':           qty,
        'debated':       False,
        'decided':       False,
        'source':        'tv_webhook',
        'tv_alert':      tv_alert_desc,
        'created_at':    berlin_now().isoformat(),
    }

    # ── Append to signals_live.json ───────────────────────────────────────
    signals = []
    if signal_file.exists():
        try:
            with open(signal_file, encoding='utf-8') as f:
                signals = json.load(f)
            signals = signals if isinstance(signals, list) else [signals]
        except Exception:
            signals = []

    signals.append(signal)
    signal_file.parent.mkdir(parents=True, exist_ok=True)
    with open(signal_file, 'w', encoding='utf-8') as f:
        json.dump(signals, f, indent=2, default=str)

    # ── Notify Kay ────────────────────────────────────────────────────────
    rr = (target - price) / (price - stop) if price != stop else 0
    msg = (
        f"📺 TV Alert — {symbol}\n"
        f"Price: ${price} | Qty: {qty}\n"
        f"Target: ${target} | Stop: ${stop}\n"
        f"R:R = {rr:.1f}:1 | Score: {score}/5\n"
        f"Alert: {tv_alert_desc}\n"
        f"\n"
        f"✅ Approve: /approve {symbol}\n"
        f"❌ Deny:    /deny {symbol}"
    )
    try:
        send_alert(msg)
    except Exception as e:
        print(f"[Webhook TV] Telegram error: {e}")

    print(f"[Webhook TV] {symbol} added from TV — awaiting Kay approval")
    return jsonify({'ok': True, 'action': 'queued', 'symbol': symbol}), 200


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
