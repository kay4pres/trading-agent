"""
Kay's Day Trade Dashboard — Flask Backend
=======================================
Serves the live dashboard, runs scanner, handles decisions.
"""

import os, json, sys, threading, time, traceback
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any
from flask import Flask, jsonify, request, render_template, send_from_directory
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

app = Flask(__name__, static_folder=str(Path(__file__).parent / 'static'))
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

# Z: share path — NAS Z: drive maps to \\10.8.0.10\Home\backups
# which is the same NAS filesystem as /volume1/Docker/data.
# Added as final fallback when Docker volume mount is misconfigured.
NAS_Z_SHARE_DIR = Path(r'Z:\trading-agent-source\data\watchlists')


def load_premarket_watchlist():
    """
    Load today's premarket watchlist if it exists.
    Checks multiple paths: Docker /app/data mount (NAS), and the local
    E:\\Me\\TradingAgent\\data path (used by Mavis cron on Kay's machine).
    """
    today = date.today().strftime('%Y%m%d')
    candidates = [
        # Docker /app/data/watchlists/ (NAS mount — used by Portainer/NAS deployment)
        PREMARKET_DIR / f'watchlist_{today}.csv',
        # Fallback: same path as Mavis cron on Kay's host machine
        DATA_DIR / 'watchlists' / f'watchlist_{today}.csv',
        # Explicit Kay host path (E:\Me\TradingAgent\data — used when docker-compose
        # resolves ./data relative to E:\Me\TradingAgent\)
        Path(r'E:\Me\TradingAgent\data\watchlists') / f'watchlist_{today}.csv',
        # Also check root-level watchlist CSV (written by some scanner runs)
        DATA_DIR / f'watchlist_{today}.csv',
        # Z: share (NAS Z: drive) — Richard's premarket_screener syncs here
        # so the container can see it when the Docker volume mount is misconfigured
        NAS_Z_SHARE_DIR / f'watchlist_{today}.csv',
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
                            'symbol':      sym,
                            'short_name': row.get('short_name', sym),
                            'price':       float(row.get('price') or 0),
                            'gap_pct':     float(row.get('gap_pct') or 0),
                            'rel_vol':     float(row.get('rel_vol') or 0),
                            'float_m':     float(row.get('float_m') or 0),
                            'total_score': float(row.get('total_score') or 0),
                            'p4_catalyst': float(row.get('p4_catalyst') or 0),
                            'news_summary': row.get('news_summary', ''),
                            'risk_flags': [],
                            # Deserialize P1-P5 scores from CSV (written by premarket_screener.save_watchlist)
                            'pillars':     json.loads(row.get('pillars_json', '{}')) or {},
                            'source':      'premarket',
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
    'mount_status': 'unknown',  # 'ok' | 'missing_data_dir' | 'missing_watchlist'
}

# ── Thread handle for liveness monitoring ──────────────────────────────────────
_scanner_thread: threading.Thread | None = None  # set after .start(), used by /api/scan/liveness


def _check_mount_status() -> str:
    """
    Check if the data directory and watchlist are accessible.
    Returns a status string that surfaces Docker volume mount issues.
    Also checks the Z: share fallback as a last resort.
    """
    import os
    if not DATA_DIR.exists():
        return "missing_data_dir"
    watchlist_dir = DATA_DIR / 'watchlists'
    if not watchlist_dir.exists():
        return "missing_watchlist_dir"
    today_str = date.today().strftime('%Y%m%d')
    csv_path = watchlist_dir / f'watchlist_{today_str}.csv'
    if not csv_path.exists():
        # Fallback: check Z: share (Richard's sync destination)
        z_csv = NAS_Z_SHARE_DIR / f'watchlist_{today_str}.csv'
        if z_csv.exists():
            print(f"[dashboard] Watchlist found in Z: share: {z_csv}")
            return "ok"
        return "missing_today_watchlist"
    return "ok"


# Startup check — log mount status so container logs are diagnostic
_mount_status = _check_mount_status()
_today_str = date.today().strftime('%Y%m%d')
_z_csv_startup = NAS_Z_SHARE_DIR / f'watchlist_{_today_str}.csv'
if _mount_status != "ok":
    print(f"[dashboard] ⚠ DATA_DIR mount issue: {_mount_status}")
    print(f"[dashboard]   DATA_DIR        = {DATA_DIR} (exists={DATA_DIR.exists()})")
    print(f"[dashboard]   PREMARKET_DIR   = {PREMARKET_DIR} (exists={PREMARKET_DIR.exists() if PREMARKET_DIR.exists() else False})")
    print(f"[dashboard]   Z: share CSV    = {_z_csv_startup} (exists={_z_csv_startup.exists()})")
    print(f"[dashboard]   NOTE: Richard's Mavis cron writes to E:\\Me\\TradingAgent\\data\\watchlists/")
    print(f"[dashboard]   premarket_screener syncs to Z: share (Z:\\trading-agent-source\\data\\watchlists/)")
    print(f"[dashboard]   Docker container reads from both Docker volume + Z: share fallback")
else:
    print(f"[dashboard] ✓ DATA_DIR mount OK: {DATA_DIR}")


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

def _load_watchlist_csv() -> List[Dict[str, Any]]:
    """
    Load gap stocks from Richard's premarket watchlist CSV.
    This is the primary fallback when TV Premium API is unavailable inside the container.
    Checks both the Docker /app/data mount and Kay's host path.
    """
    today_str = date.today().strftime('%Y%m%d')
    candidates = [
        DATA_DIR / 'watchlists' / f'watchlist_{today_str}.csv',
        PREMARKET_DIR / f'watchlist_{today_str}.csv',
        Path(r'E:\Me\TradingAgent\data\watchlists') / f'watchlist_{today_str}.csv',
        DATA_DIR / f'watchlist_{today_str}.csv',
        # Z: share — Richard's premarket_screener syncs here
        NAS_Z_SHARE_DIR / f'watchlist_{today_str}.csv',
    ]
    found_any = any(p.exists() for p in candidates)
    if not found_any:
        print(f"[scanner] ⚠ No watchlist CSV found for today ({today_str}). Checked:")
        for p in candidates:
            print(f"         - {p} (exists={p.exists()})")
        print(f"         DATA_DIR={DATA_DIR}  PREMARKET_DIR={PREMARKET_DIR}")
        print(f"         ⚠ Docker volume mount may be misconfigured — container can't see watchlist CSV.")
        print(f"         ⚠ Richard's Mavis cron writes to E:\\Me\\TradingAgent\\data\\watchlists/ on Kay's local machine.")
        print(f"         ⚠ Fix: mount Kay's E:\\Me\\TradingAgent\\data to /app/data in Portainer container config.")

    for path in candidates:
        if path.exists():
            try:
                import csv as csv_mod
                rows = []
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv_mod.DictReader(f)
                    for row in reader:
                        sym = row.get('symbol', '').strip() or row.get('Symbol', '').strip()
                        if not sym:
                            continue
                        try:
                            rows.append({
                                'symbol':       sym,
                                'short_name':   row.get('short_name', sym),
                                'price':        float(row.get('price') or 0),
                                'gap_pct':      float(row.get('gap_pct') or 0),
                                'rel_vol':      float(row.get('rel_vol') or 0),
                                'float_m':      float(row.get('float_m') or 0),
                                'total_score':  float(row.get('total_score') or 0),
                                'p4_catalyst':  float(row.get('p4_catalyst') or 0),
                                'news_summary':  row.get('news_summary', ''),
                                'risk_flags':   [],
                                # Deserialize P1-P5 scores from CSV (written by premarket_screener.save_watchlist).
                                # Handle: valid JSON string (fixed), Python dict string repr (legacy CSV bug),
                                # already-a-dict (unlikely but safe), or empty.
                                _pj_raw = row.get('pillars_json', '{}')
                                try:
                                    _pillars_val = json.loads(_pj_raw)
                                except Exception:
                                    # Legacy CSV bug: DictWriter wrote Python repr instead of JSON.
                                    # Attempt ast.literal_eval as last resort.
                                    try:
                                        import ast
                                        _pillars_val = ast.literal_eval(_pj_raw)
                                    except Exception:
                                        _pillars_val = {}
                                'pillars': _pillars_val or {},
                                'source':       'premarket_csv',
                                'decided':       False,
                                'decision':      None,
                                'scan_time':     today_str,
                            })
                        except (ValueError, TypeError):
                            continue
                if rows:
                    rows.sort(key=lambda x: x['total_score'], reverse=True)
                    print(f"[scanner] Loaded {len(rows)} signals from watchlist CSV: {path.name}")
                    return rows
            except Exception as e:
                print(f"[scanner] Failed to read watchlist CSV {path}: {e}")
    return []


def run_scan(min_score=2.5, symbols=None):
    """
    Run the Five Pillars scanner on all symbols.
    Data source priority:
      1. TradingView Premium API (real-time) — if TV session mounted in container
      2. Richard's premarket watchlist CSV (from Mavis cron on host machine)
      3. yfinance with DEFAULT_UNIVERSE (last resort)
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

    # ── Step 2: Fallback to premarket watchlist CSV (from Richard's cron) ─────
    # This is the key fallback for the Docker container — Richard's watchlist
    # is written to E:\Me\TradingAgent\data\watchlists\ by the Mavis cron.
    watchlist_signals: List[Dict[str, Any]] = []
    if not tv_rows and symbols is None:
        watchlist_signals = _load_watchlist_csv()

    # ── Step 3: Last resort — yfinance with DEFAULT_UNIVERSE ─────────────────
    if not tv_rows and not watchlist_signals:
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
            # Still return watchlist signals even if yfinance fails
            if watchlist_signals:
                return [r for r in watchlist_signals if r['total_score'] >= min_score]
            return []

    # ── Step 4: Score each symbol ──────────────────────────────────────────────
    results: List[Dict[str, Any]] = []

    # 4a: Score TV rows directly (price/gap already enriched from TV)
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

    # 4b: Score yfinance fallback symbols (DEFAULT_UNIVERSE path)
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

    # 4c: Score watchlist CSV signals with Five Pillars (live scoring, not just CSV append)
    # Fetch batch quotes + info for all watchlist symbols to avoid N individual calls
    csv_symbols = [s['symbol'] for s in watchlist_signals
                   if s['symbol'] not in [r['symbol'] for r in results]]
    csv_quotes_raw: Dict[str, Any] = {}
    if csv_symbols:
        try:
            raw_quotes = get_batch_quotes(csv_symbols)
            for q in (raw_quotes if isinstance(raw_quotes, list) else []):
                sym = q.get('symbol', '')
                if sym:
                    csv_quotes_raw[sym] = q
        except Exception as e:
            print(f"[scanner] CSV batch quotes failed: {e}")

    scored_csv_count = 0
    for sig in watchlist_signals:
        sym = sig['symbol']
        if sym in [r['symbol'] for r in results]:
            continue  # already scored via TV or yfinance path
        # Score with live data if available, else fall back to CSV data
        q = csv_quotes_raw.get(sym)
        if q and q.get('price'):
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
            scored = {
                'symbol':       sym,
                'short_name':   sig.get('short_name', ''),
                'price':        round(q.get('price', sig.get('price', 0)), 2),
                'gap_pct':      round(pillars['gap_pct'], 1),
                'rel_vol':      round(pillars['rel_vol'], 1),
                'float_m':      pillars.get('float_m'),
                'total_score':  round(total, 1),
                'pillars':      pillars['pillars'],
                'p4_catalyst': round(catalyst['P4_catalyst'], 2),
                'news_summary':  catalyst['news_summary'],
                'news_count':    catalyst['news_count'],
                'news_provider': catalyst.get('news_provider', 'none'),
                'risk_flags':    pillars.get('risk_flags', []),
                'scan_time':    today_str,
                'decided':      False,
                'decision':     None,
                'source':       'csv_live',
            }
            if scored['total_score'] >= min_score:
                results.append(scored)
                scored_csv_count += 1
        else:
            # ── CSV-data fallback scoring ─────────────────────────────────────
            # When live quotes fail (thinly traded / delisted symbols),
            # compute pillar scores directly from CSV fields so dashboard shows data.
            # P1: price $2-$20, P2: gap, P3: rel_vol, P5: float from CSV.
            # P4: catalyst not available from CSV alone — skip or use CSV news_summary.
            csv_price   = sig.get('price', 0)
            csv_gap_pct = sig.get('gap_pct', 0)
            csv_rv      = sig.get('rel_vol', 0)
            csv_float   = sig.get('float_m', 0)

            p1_score = 1.0 if 2 <= csv_price <= 20 else 0.0
            p2_score = 1.0 if csv_gap_pct >= 10 else (0.5 if csv_gap_pct >= 5 else 0.0)
            p3_score = 1.0 if csv_rv >= 5 else (0.5 if csv_rv >= 3 else 0.0)
            p5_score = 1.0 if 0 < csv_float < 20 else (0.5 if csv_float == 0 else 0.0)
            # P4: use CSV's p4_catalyst if available, else default to 0.5 (unknown)
            p4_score = sig.get('p4_catalyst', 0.5)
            csv_total = round(p1_score + p2_score + p3_score + p5_score + p4_score, 1)

            pillars_out = {
                'P1_price':   p1_score,
                'P2_gap':     p2_score,
                'P3_relvol':  p3_score,
                'P4_catalyst': p4_score,
                'P5_float':   p5_score,
            }
            csv_risk = []
            if csv_gap_pct > 50:
                csv_risk.append(f"HALT_RISK gap={csv_gap_pct:.0f}%")
            if csv_float == 0:
                csv_risk.append("UNKNOWN_FLOAT")

            scored = {
                'symbol':       sym,
                'short_name':   sig.get('short_name', ''),
                'price':        round(csv_price, 2),
                'gap_pct':      round(csv_gap_pct, 1),
                'rel_vol':      round(csv_rv, 1),
                'float_m':      csv_float,
                'total_score':  csv_total,
                'pillars':      pillars_out,
                'p4_catalyst': round(p4_score, 2),
                'news_summary':  sig.get('news_summary', ''),
                'news_count':    0,
                'news_provider': 'csv_fallback',
                'risk_flags':    csv_risk,
                'scan_time':    today_str,
                'decided':      False,
                'decision':     None,
                'source':       'csv_fallback',
            }
            if csv_total >= min_score:
                results.append(scored)
                scored_csv_count += 1
    if scored_csv_count:
        print(f"[scanner] Live-scored {scored_csv_count} CSV signals with Five Pillars")

    # Sort by score
    results.sort(key=lambda x: x['total_score'], reverse=True)
    return [r for r in results if r['total_score'] >= min_score]


# Track symbols we've already alerted today (avoid spamming same signal)
_alerted_today: set = set()
_last_alert_date: str = ''


# Heartbeat counter — incremented every iteration, logged every 60 (≈ once per hour)
_scan_heartbeat = 0

def scan_thread():
    """
    Background scanner — runs every 60s during market hours.
    PERSISTENT OUTER TRY/EXCEPT: the daemon thread MUST NOT silently die.
    Any uncaught exception is logged with full traceback and the loop restarts.
    """
    global _alerted_today, _last_alert_date, _scan_heartbeat
    while True:
        try:  # ── PERSISTENT OUTER GUARD: catches everything, never lets thread die ──
            if market_status():
                today = berlin_now().strftime('%Y-%m-%d')
                if today != _last_alert_date:
                    _alerted_today = set()
                    _last_alert_date = today
                    # Load premarket watchlist from Richard's morning scan
                    premarket = load_premarket_watchlist()
                    if premarket:
                        state['watchlist'] = premarket
                        state['signals']   = premarket
                        print(f"[scanner] Loaded {len(premarket)} premarket signals for {today}")

                try:
                    signals = run_scan(min_score=2.5)
                    state['signals']    = signals
                    state['watchlist']  = signals
                    state['last_scan']  = berlin_now().strftime('%H:%M')
                    state['market_open'] = True
                    state['mount_status'] = _check_mount_status()

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

                    # Write signals_live.json so Bull/Bear runner can pick up cron scan results.
                    # Bull/Bear reads signals_live.json as primary input (event-driven pipeline
                    # falls back to it when no streaming events fire, e.g. no Alpaca WS).
                    try:
                        signals_live_path = DATA_DIR / 'signals_live.json'
                        signals_live_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(signals_live_path, 'w', encoding='utf-8') as f:
                            json.dump(signals, f, indent=2, default=str)
                        print(f"[scanner] wrote {len(signals)} signals to signals_live.json")
                    except Exception as ew:
                        print(f"[scanner] signals_live.json write failed: {ew}")

                    # Sync with live_event_loop pipeline
                    load_trading_engine_state()
                except Exception as e:
                    print(f"[scanner] scan error: {e}")

            _scan_heartbeat += 1
            if _scan_heartbeat % 60 == 0:
                print(f"[scanner] heartbeat #{_scan_heartbeat} — alive at {berlin_now().strftime('%H:%M')}, market_open={market_status()}")

        except Exception as e:
            # CRITICAL: outer guard — catches ANYTHING that escapes the inner try
            # including KeyboardInterrupt, OSErrors, etc. that would silently kill the thread
            print(f"[scanner] FATAL — thread would have died. Restarting. Error: {e}")
            traceback.print_exc()
            time.sleep(5)  # brief backoff before retry

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
    """Serve the dashboard HTML from static folder."""
    static_dir = Path(__file__).parent / 'static'
    return send_from_directory(static_dir, 'dashboard.html')


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
        'mount_status': state['mount_status'],
    })


@app.route('/api/mount-status')
def api_mount_status():
    """Return Docker volume mount diagnostic — helps debug watchlist CSV not found issues."""
    status = _check_mount_status()
    state['mount_status'] = status
    today_str = date.today().strftime('%Y%m%d')
    z_csv = NAS_Z_SHARE_DIR / f'watchlist_{today_str}.csv'
    return jsonify({
        'status': status,
        'data_dir': str(DATA_DIR),
        'data_dir_exists': DATA_DIR.exists(),
        'watchlist_dir': str(PREMARKET_DIR),
        'watchlist_dir_exists': PREMARKET_DIR.exists(),
        'today_csv': str(PREMARKET_DIR / f'watchlist_{today_str}.csv'),
        'today_csv_exists': (PREMARKET_DIR / f'watchlist_{today_str}.csv').exists(),
        'z_share_csv': str(z_csv),
        'z_share_csv_exists': z_csv.exists(),
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


@app.route('/api/scan/liveness')
def api_scan_liveness():
    """
    Check if the scanner thread is alive and healthy.
    Used by pipeline-check cron and Kay to diagnose frozen scanners.
    Also wakes up the scanner if it was dead by starting a fresh thread.
    """
    global _scanner_thread
    alive = _scanner_thread is not None and _scanner_thread.is_alive()
    last_scan = state.get('last_scan')
    heartbeat = _scan_heartbeat if '_scan_heartbeat' in globals() else -1
    market = market_status()

    # If thread is dead, restart it and warn
    if not alive:
        print(f"[dashboard] ⚠️ Scanner thread was dead! Restarting at {berlin_now().strftime('%H:%M:%S')}")
        _scanner_thread = threading.Thread(target=scan_thread, daemon=True)
        _scanner_thread.start()
        alive = True  # it's alive now

    return jsonify({
        'alive':       alive,
        'last_scan':   last_scan,
        'heartbeat':   heartbeat,
        'market_open': market,
        'timestamp':   berlin_now().isoformat(),
    })


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
# PM-AGENT WEBHOOK — fires when /pm check/status is sent via Telegram
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/debug/load-watchlist', methods=['POST'])
def api_debug_load_watchlist():
    """
    Debug endpoint: write watchlist CSV directly into the container and reload.
    POST /api/debug/load-watchlist
    Body: {"symbols": [{"symbol":"ICU","price":4.86,"gap_pct":32.4,"rel_vol":6.6,"float_m":4.0,"total_score":2.5,"news_summary":"..."}]}
    Writes to /app/data/watchlists/watchlist_YYYYMMDD.csv and reloads state.
    """
    import csv as csv_mod, io
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'error': 'invalid json'}), 400

    symbols = data.get('symbols', [])
    if not symbols:
        return jsonify({'error': 'no symbols provided'}), 400

    today_str = berlin_now().strftime('%Y%m%d')
    watchlist_dir = DATA_DIR / 'watchlists'
    watchlist_dir.mkdir(parents=True, exist_ok=True)
    csv_path = watchlist_dir / f'watchlist_{today_str}.csv'
    latest_path = DATA_DIR / 'watchlist_latest.csv'

    # Write CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv_mod.DictWriter(f, fieldnames=[
            'symbol','short_name','price','gap_pct','rel_vol','float_m',
            'total_score','p4_catalyst','news_summary'
        ])
        writer.writeheader()
        for s in symbols:
            writer.writerow({
                'symbol':       s.get('symbol', ''),
                'short_name':   s.get('short_name', ''),
                'price':        s.get('price', 0),
                'gap_pct':      s.get('gap_pct', 0),
                'rel_vol':      s.get('rel_vol', 0),
                'float_m':     s.get('float_m', 0),
                'total_score':  s.get('total_score', 0),
                'p4_catalyst':  s.get('p4_catalyst', 0),
                'news_summary': s.get('news_summary', ''),
            })

    # Also write watchlist_latest.csv
    with open(latest_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv_mod.DictWriter(f, fieldnames=[
            'symbol','short_name','price','gap_pct','rel_vol','float_m',
            'total_score','p4_catalyst','news_summary'
        ])
        writer.writeheader()
        for s in symbols:
            writer.writerow({
                'symbol':       s.get('symbol', ''),
                'short_name':   s.get('short_name', ''),
                'price':        s.get('price', 0),
                'gap_pct':      s.get('gap_pct', 0),
                'rel_vol':      s.get('rel_vol', 0),
                'float_m':     s.get('float_m', 0),
                'total_score':  s.get('total_score', 0),
                'p4_catalyst':  s.get('p4_catalyst', 0),
                'news_summary': s.get('news_summary', ''),
            })

    # Reload state
    premarket = load_premarket_watchlist()
    if premarket:
        state['watchlist'] = premarket
        state['signals']   = premarket
    state['last_scan'] = berlin_now().strftime('%H:%M')
    print(f"[debug] Loaded {len(symbols)} watchlist symbols from debug endpoint")
    return jsonify({'ok': True, 'loaded': len(symbols), 'path': str(csv_path)})


@app.route('/pm-webhook', methods=['POST'])
def pm_webhook():
    """
    Called by telegram_command_listener.py when Kay sends /pm check or /pm status.
    Writes a trigger file that PM-Agent's polling loop picks up.
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    cmd = data.get('command', 'check')
    triggered_by = data.get('triggered_by', 'telegram')

    import json, time
    trigger_file = DATA_DIR / '.pm_trigger'
    trigger_file.write_text(json.dumps({
        'command': cmd,
        'triggered_by': triggered_by,
        'triggered_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }))
    print(f"[PM-Webhook] PM-Agent triggered: /pm {cmd} by {triggered_by}")
    return jsonify({'ok': True, 'triggered': cmd}), 200


@app.route('/api/pm-poll', methods=['GET'])
def api_pm_poll():
    """
    PM-Agent polls this endpoint to check if it needs to run.
    Returns the trigger file contents and clears it (one-shot).
    GET /api/pm-poll → {command, triggered_by, triggered_at} or {empty: true}
    """
    import json
    trigger_file = DATA_DIR / '.pm_trigger'
    if trigger_file.exists():
        try:
            content = json.loads(trigger_file.read_text())
            trigger_file.unlink()  # clear after reading — one-shot
            return jsonify(content)
        except Exception:
            return jsonify({'empty': True})
    return jsonify({'empty': True})


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Load saved decisions
    state['decisions'] = load_decisions()

    # Load premarket watchlist from Richard's CSV first (before running scan)
    print("Loading premarket watchlist...")
    premarket = load_premarket_watchlist()
    if premarket:
        state['watchlist'] = premarket
        state['signals']   = premarket
        print(f"[dashboard] Initial watchlist: {len(premarket)} symbols loaded from CSV")
    else:
        print("[dashboard] No premarket CSV found — running scan...")
        state['signals']   = run_scan(min_score=2.5)
        state['watchlist'] = state['signals']

    state['last_scan'] = berlin_now().strftime('%H:%M')
    state['mount_status'] = _check_mount_status()

    # Start background scanner thread
    global _scanner_thread
    _scanner_thread = threading.Thread(target=scan_thread, daemon=True)
    _scanner_thread.start()
    print(f"[dashboard] Scanner thread started — thread.is_alive()={_scanner_thread.is_alive()}")

    # Start Telegram polling thread (listens for button presses)
    start_polling(callback_handler=on_telegram_button)

    print(f"Dashboard starting at http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=False)
