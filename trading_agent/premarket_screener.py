"""
premarket_screener.py
===================
Richard's pre-market watchlist builder.
Runs at 14:00 Berlin — ranked watchlist ready by 14:25.

Data flow:
  Fincept (yfinance) ──► Five Pillars + Ch2 Risk Rules ──► Ranked Watchlist
  TradingView CSV (Kay) ──► same pipeline
  Finnhub / AlphaVantage ──► P4 Catalyst check (via news_providers.py)
"""

import os, sys
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import json

# ── Local imports ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from fincept_connector   import get_batch_quotes, get_historical, get_info
from news_providers      import get_company_news, score_catalyst
from tradingview_connector import fetch_ross_universe, tv_to_signal_rows

# ── Config ────────────────────────────────────────────────────────────────────
# Docker: TRADING_DATA_DIR=/app/data → /app/data/watchlists
# Local:  falls back to E:\Me\TradingAgent\data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
if _DATA_ROOT:
    DATA_DIR = Path(_DATA_ROOT)
else:
    DATA_DIR = Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(exist_ok=True)
WATCHLIST_DIR = DATA_DIR / 'watchlists'
WATCHLIST_DIR.mkdir(exist_ok=True)

TODAY = date.today()
WATCHLIST_FILE = WATCHLIST_DIR / f"watchlist_{TODAY.strftime('%Y%m%d')}.csv"
POSITIONS_FILE = DATA_DIR / 'positions.json'

# ── Docker volume sync ─────────────────────────────────────────────────────────
# The Docker container mounts /volume1/Docker/data (NAS) as /app/data.
# Richard's Mavis cron runs on Kay's Windows machine.
# We sync directly to the Docker volume SMB share so the container sees it.
#
# The Docker volume on NAS:  \\10.8.0.10\Docker\data  → container: /app/data
# (CONFIRMED: Get-SmbShare on 10.8.0.10 exposes \\10.8.0.10\Docker as a share.
#  /volume1/Docker/data maps to this share — verified 2026-07-07.)
#
# NOTE: Z: share (\\10.8.0.10\Home\backups) is a DIFFERENT directory on the NAS.
# It is NOT the same as /volume1/Docker/ — do NOT use Z: for Docker volume sync.
_DOCKER_VOLUME_SMB = Path(r'\\10.8.0.10\Docker\data\watchlists')
_NAS_Z_SHARE_DIR   = Path(r'Z:\trading-agent-source\data\watchlists')  # legacy, keep for reference

def _sync_to_docker_volume():
    """Copy today's watchlist to the Docker volume SMB share so the container reads it."""
    try:
        _DOCKER_VOLUME_SMB.mkdir(parents=True, exist_ok=True)
        today_str = TODAY.strftime('%Y%m%d')
        for fname in [f'watchlist_{today_str}.csv', 'watchlist_latest.csv']:
            src = WATCHLIST_DIR / fname
            dst = _DOCKER_VOLUME_SMB / fname
            if src.exists():
                import shutil
                shutil.copy2(src, dst)
                print(f"  📡 synced {fname} -> Docker volume (\\10.8.0.10\\Docker\\data)")
    except Exception as e:
        print(f"  ⚠ Docker volume sync failed (container won't see watchlist): {e}")
        # Fallback: also try Z: share (legacy, different NAS path — may not work in container)
        try:
            _NAS_Z_SHARE_DIR.mkdir(parents=True, exist_ok=True)
            for fname in [f'watchlist_{today_str}.csv', 'watchlist_latest.csv']:
                src = WATCHLIST_DIR / fname
                dst = _NAS_Z_SHARE_DIR / fname
                if src.exists():
                    import shutil
                    shutil.copy2(src, dst)
                    print(f"  📡 fallback synced {fname} -> Z: share (container may not see it)")
        except Exception as e2:
            print(f"  ⚠ Z: share fallback also failed: {e2}")

# ── Positions Guard ────────────────────────────────────────────────────────────
def get_open_symbols():
    """Return set of symbols currently in an open position."""
    if not POSITIONS_FILE.exists():
        return set()
    try:
        with open(POSITIONS_FILE) as f:
            state = json.load(f)
        return {
            sym for sym, pos in state.get("positions", {}).items()
            if pos.get("status") == "OPEN"
        }
    except Exception:
        return set()

# ── Default universe (top movers watchlist) ───────────────────────────────────
# These are the stocks Richard checks each morning when no TradingView export
DEFAULT_UNIVERSE = [
    'SOFI', 'GPRO', 'SONO', 'PLTR', 'AMD', 'NVDA', 'TSLA', 'AAPL',
    'NIO', 'LCID', 'RIVN', 'NKLA', 'SPCM', 'WULF', 'MARU', 'MAXN',
    'ENVB', 'OPGN', 'BNGO', 'MULN', 'GRAB', 'SE', 'BABA', 'JD',
]


# ═══════════════════════════════════════════════════════════════════════════════
# FIVE PILLARS + COURSE 2 RISK RULES
# ═══════════════════════════════════════════════════════════════════════════════

def check_pillars(quote: Dict, info: Dict) -> Dict[str, Any]:
    """
    Evaluate Five Pillars + Course 2 risk checks.
    Returns dict with pillar scores and reject reasons.
    """
    price       = quote.get('price', 0)
    prev_close  = quote.get('previous_close', price)
    gap_pct     = ((price - prev_close) / prev_close * 100) if prev_close else 0
    volume      = quote.get('volume', 0)
    high        = quote.get('high', price)
    low         = quote.get('low', price)
    avg_volume  = info.get('averageVolume', 0)
    rel_vol     = volume / avg_volume if avg_volume else 0
    float_shares= info.get('floatShares', 0)
    market_cap  = info.get('marketCap', 0)
    short_name  = info.get('shortName', '')

    score     = 0
    pillars   = {}
    rejects   = []

    # ── P1: Price $2–$20 ────────────────────────────────────────────────────
    if 2 <= price <= 20:
        pillars['P1_price'] = 1
        score += 1
    elif price < 2:
        pillars['P1_price'] = 0
        rejects.append(f"P1 FAIL: price ${price:.2f} < $2")
    else:
        pillars['P1_price'] = 0
        rejects.append(f"P1 FAIL: price ${price:.2f} > $20")

    # ── P2: Gap ≥10% ────────────────────────────────────────────────────────
    if gap_pct >= 10:
        pillars['P2_gap'] = 1
        score += 1
    elif gap_pct >= 5:
        pillars['P2_gap'] = 0.5
        score += 0.5
        rejects.append(f"P2 WARN: gap {gap_pct:.1f}% (threshold 10%)")
    else:
        pillars['P2_gap'] = 0
        rejects.append(f"P2 FAIL: gap {gap_pct:.1f}% < 10%")

    # ── P3: Relative Volume ≥5× ────────────────────────────────────────────
    if rel_vol >= 5:
        pillars['P3_relvol'] = 1
        score += 1
    elif rel_vol >= 3:
        pillars['P3_relvol'] = 0.5
        score += 0.5
    else:
        pillars['P3_relvol'] = 0
        rejects.append(f"P3 FAIL: relvol {rel_vol:.1f}× < 5×")

    # ── P4: Catalyst (news) — checked separately via get_news() ──────────────
    pillars['P4_catalyst'] = None  # populated after news fetch

    # ── P5: Float <20M ──────────────────────────────────────────────────────
    if float_shares > 0 and float_shares < 20_000_000:
        pillars['P5_float'] = 1
        score += 1
    elif float_shares == 0:
        pillars['P5_float'] = 0.5  # unknown
        rejects.append(f"P5 WARN: float unknown (Alpha Vantage not set)")
    else:
        pillars['P5_float'] = 0
        rejects.append(f"P5 FAIL: float {float_shares/1e6:.1f}M > 20M")

    # ── Course 2 Risk Checks ─────────────────────────────────────────────────
    risk_flags = []

    # Risk 1: Wide spread (high intraday range = volatile)
    if high and low and price:
        intraday_range = (high - low) / low * 100
        if intraday_range > 20:
            risk_flags.append(f"WIDE_RANGE {intraday_range:.1f}%")

    # Risk 2: Float = 0 (unknown) — borderline
    if float_shares == 0:
        risk_flags.append("UNKNOWN_FLOAT")

    # Risk 3: High market cap = lower volatility (not necessarily bad, just noting)
    if market_cap > 10_000_000_000:
        risk_flags.append("LARGE_CAP")  # not a reject, just informational

    # Risk 4: Gap >50% = halt risk (Ch2: up big with no news = danger)
    if gap_pct > 50:
        risk_flags.append(f"HALT_RISK gap={gap_pct:.0f}%")

    return {
        'score':        score,
        'pillars':      pillars,
        'rejects':      rejects,
        'risk_flags':   risk_flags,
        'gap_pct':      round(gap_pct, 2),
        'rel_vol':      round(rel_vol, 1),
        'float_m':      round(float_shares / 1e6, 1) if float_shares else None,
        'short_name':   short_name,
    }


def check_catalyst(symbol: str, news_list: List[Dict]) -> Dict[str, Any]:
    """
    Evaluate P4: News catalyst.
    Always fetches fresh via get_company_news() so recent_count is computed
    correctly and AV quota is respected (sentinel inside get_company_news).
    """
    try:
        news_result = get_company_news(symbol, count=10)
    except Exception:
        news_result = {
            'articles': [], 'recent_count': 0, 'top_headline': 'No news',
            'provider': 'none', 'sentiment_score': 0, 'bullish_pct': 0
        }
    return score_catalyst(news_result)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCREENER
# ═══════════════════════════════════════════════════════════════════════════════

def load_tradingview_csv(path: Path) -> List[Dict[str, Any]]:
    """
    Parse TradingView scanner export CSV.
    Returns list of dicts with normalized field names.
    TradingView CSV format: Symbol, Description, Price, Price change % 1 day,
    Relative volume 1 day, Volume 1 day, Market cap, etc.
    """
    import csv
    rows = []
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get('Symbol', '').strip()
                if not sym:
                    continue
                # Normalize TradingView column names
                price_str = row.get('Price', '0').replace(',', '')
                gap_str   = row.get('Price change %, 1 day', '0').replace(',', '')
                rv_str    = row.get('Relative volume, 1 day', '0').replace(',', '')
                vol_str   = row.get('Volume, 1 day', '0').replace(',', '')
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    price = 0
                try:
                    gap = float(gap_str)
                except (ValueError, TypeError):
                    gap = 0
                try:
                    rv = float(rv_str)
                except (ValueError, TypeError):
                    rv = 0
                try:
                    vol = float(vol_str)
                except (ValueError, TypeError):
                    vol = 0
                rows.append({
                    'symbol':       sym.upper(),
                    'short_name':   row.get('Description', ''),
                    'price':        price,
                    'gap_pct':      round(gap, 2),
                    'rel_vol':      round(rv, 1),
                    'volume':       int(vol),
                    'tv_row':       row,  # full raw row for reference
                })
    except Exception as e:
        print(f"  ⚠️  Could not read TradingView CSV: {e}")
    return rows


def _find_latest_tv_csv(today: date = None) -> Optional[Path]:
    """
    Find the most recent TradingView CSV export in the incoming folder.
    Only accepts files dated TODAY or yesterday (stale = >1 day old).
    """
    today = today or date.today()
    incoming = Path(r'E:\Me\TradingAgent\data\incoming')
    if not incoming.exists():
        return None

    # Try date-stamped files first (preferred format: Marvis-Kay_2026-06-29.csv)
    csvs_dated = list(incoming.glob("*_????-??-??.csv"))
    for csv in csvs_dated:
        # Extract date from filename: Marvis-Kay_2026-06-29.csv → 2026-06-29
        name = csv.stem
        date_str = None
        for part in reversed(name.split('_')):
            if len(part) == 10 and part[4] == '-' and part[7] == '-':
                date_str = part
                break
        if date_str:
            try:
                file_date = date.fromisoformat(date_str)
                delta = (today - file_date).days
                if 0 <= delta <= 1:  # today or yesterday only
                    print(f"  [CSV] Auto-detected fresh TV export: {csv.name} ({delta} day(s) old)")
                    return csv
            except ValueError:
                pass

    # Fallback: any CSV modified within last 24h
    cutoff = datetime.now().timestamp() - 86400
    csvs_any = list(incoming.glob("*.csv"))
    recent = [c for c in csvs_any if c.stat().st_mtime >= cutoff]
    if recent:
        latest = max(recent, key=lambda p: p.stat().st_mtime)
        print(f"  [CSV] Using recent CSV (modified today): {latest.name}")
        return latest

    return None


def run_screener(
    symbols: Optional[List[str]] = None,
    tv_export_path: Optional[Path] = None,
    use_finviz: bool = False,
    min_score: float = 2.0,
    use_tv_api: bool = True,
) -> List[Dict[str, Any]]:
    """
    Main screener entry point.

    Data priority (highest first):
      1. Explicit symbols list (--symbols arg) — always respected, skips stale CSV
      2. TradingView Premium API (live, real-time) — if use_tv_api=True
      3. TradingView CSV export (incoming folder or --tv-csv override)
      4. DEFAULT_UNIVERSE fallback (last resort)

    Returns:
        ranked list of signal dicts
    """
    today_str = datetime.now().strftime('%Y-%m-%d %H:%M Berlin')

    # ── Step 1: Determine universe ──────────────────────────────────────────
    tv_rows = []      # list of dicts from TV source (CSV or API)
    symbol_list = []  # flat list of ticker strings

    # Priority 1: Explicit symbol list (never overridden by stale CSV)
    if symbols:
        symbol_list = symbols
        print(f"  📊 Using explicit symbol list ({len(symbols)} symbols)")

    # Priority 2: TradingView Premium API (live, real-time)
    elif use_tv_api:
        tv_df = fetch_ross_universe()
        if not tv_df.empty:
            tv_rows = tv_to_signal_rows(tv_df)
            symbol_list = [r['symbol'] for r in tv_rows]
            print(f"  📊 TV Premium API: {len(tv_rows)} real-time setups")

    # Priority 3: CSV export (only when no explicit symbols AND TV API failed)
    if not symbol_list and not tv_rows:
        if tv_export_path and tv_export_path.exists():
            print(f"  📊 Loading from TV export: {tv_export_path.name}")
            tv_rows = load_tradingview_csv(tv_export_path)
            symbol_list = [r['symbol'] for r in tv_rows]
        else:
            auto_path = _find_latest_tv_csv()
            if auto_path:
                print(f"  📊 Auto-detected TV export: {auto_path.name}")
                tv_rows = load_tradingview_csv(auto_path)
                symbol_list = [r['symbol'] for r in tv_rows]

    # Priority 4: Default universe (last resort)
    if not tv_rows and not symbol_list:
        symbol_list = DEFAULT_UNIVERSE
        print("  📊 Using default universe")

    print(f"  Scanning {len(symbol_list)} symbols...")

    # ── Step 2: Batch quote all symbols ──────────────────────────────────────
    quotes = {}
    try:
        raw_quotes = get_batch_quotes(symbol_list)
        for q in raw_quotes:
            sym = q.get('symbol', '')
            if sym:
                quotes[sym] = q
        print(f"  ✅ Got {len(quotes)} quotes")
    except Exception as e:
        print(f"  ❌ Quote fetch failed: {e}")
        return []

    # ── Step 3: Build a TV lookup dict for enriched data ────────────────────
    tv_lookup = {r['symbol']: r for r in tv_rows}

    # ── Step 4: Info + news + scoring for each symbol ────────────────────────
    results = []
    for sym in symbol_list:
        tv_data = tv_lookup.get(sym, {})
        quote   = quotes.get(sym)

        if not quote or quote.get('price', 0) == 0:
            continue

        # Use TV-enriched data where available, fall back to yfinance
        if tv_data:
            price   = tv_data.get('price',   quote.get('price', 0))
            gap_pct = tv_data.get('gap_pct', 0)
            rel_vol = tv_data.get('rel_vol', 0)
            volume  = tv_data.get('volume',  quote.get('volume', 0))
        else:
            prev_close = quote.get('previous_close', quote.get('price', 0))
            price      = quote.get('price', 0)
            gap_pct    = ((price - prev_close) / prev_close * 100) if prev_close else 0
            avg_vol    = quote.get('average_volume', 0)
            rel_vol    = quote.get('volume', 0) / avg_vol if avg_vol else 0
            volume     = quote.get('volume', 0)

        # Build a quote-like dict for check_pillars (it expects these keys)
        enriched_quote = {
            'price':          price,
            'previous_close': quote.get('previous_close', price),
            'volume':         volume,
            'high':           quote.get('high', price),
            'low':            quote.get('low',  price),
        }

        try:
            info = get_info(sym)
        except Exception:
            info = {}

        # News — Finnhub → AlphaVantage → yfinance (fresh fetch, recent_count computed)
        try:
            news_result = get_company_news(sym, count=10)
        except Exception:
            news_result = {'articles': [], 'recent_count': 0, 'top_headline': '',
                           'provider': 'none', 'sentiment_score': 0, 'bullish_pct': 0}

        pillars  = check_pillars(enriched_quote, info)
        catalyst = check_catalyst(sym, [])  # always fetches fresh internally

        # Override with TV data where it is more reliable
        if tv_data:
            pillars['gap_pct'] = tv_data.get('gap_pct', pillars['gap_pct'])
            pillars['rel_vol'] = tv_data.get('rel_vol', pillars['rel_vol'])

        # Recompute P2 (gap) and P3 (RV) from TV data if available
        p2_score = 1.0 if pillars['gap_pct'] >= 10 else (0.5 if pillars['gap_pct'] >= 5 else 0)
        p3_score = 1.0 if pillars['rel_vol'] >= 5 else (0.5 if pillars['rel_vol'] >= 3 else 0)

        p4_score   = catalyst['P4_catalyst']
        total_score = round(p2_score + p3_score + p4_score, 1)

        if total_score < min_score:
            continue

        results.append({
            'symbol':       sym,
            'short_name':   tv_data.get('short_name', pillars.get('short_name', '')),
            'price':        round(price, 2),
            'gap_pct':      round(pillars['gap_pct'], 2),
            'rel_vol':      round(pillars['rel_vol'], 1),
            'float_m':      pillars.get('float_m'),
            'total_score':  total_score,
            'p2_gap':       round(pillars['gap_pct'], 1),
            'p3_rv':        round(pillars['rel_vol'], 1),
            'p4_catalyst':  round(p4_score, 2),
            'news_summary': catalyst['news_summary'],
            'news_count':   catalyst.get('news_count', 0),
            'sentiment':    catalyst.get('sentiment', 0),
            'news_provider': catalyst.get('news_provider', 'none'),
            'pillars':      pillars['pillars'],
            'risk_flags':   pillars['risk_flags'],
            'rejects':      pillars['rejects'],
            'scan_time':    today_str,
        })

    # ── Step 5: Filter held stocks, then rank by total score ──────────────────
    held = get_open_symbols()
    if held:
        before = len(results)
        results = [r for r in results if r['symbol'] not in held]
        print(f"  [SKIP] Already in position: {held} — filtered {before - len(results)} signal(s)")

    results.sort(key=lambda x: x['total_score'], reverse=True)
    print(f"\n  🎯 {len(results)} signals (score ≥ {min_score})")
    return results


def format_watchlist_row(r: Dict) -> str:
    """Format a single row for display/CSV."""
    flags  = ', '.join(r['risk_flags']) if r['risk_flags'] else ''
    p4_lbl = f"P4={r.get('p4_catalyst', 0):.2f}"
    news   = r['news_summary'][:55] if r['news_summary'] else '—'
    return (
        f"  {r['symbol']:<6} ${r['price']:<5} gap={r['gap_pct']:>+5.1f}% "
        f"rv={r['rel_vol']:.1f}× {p4_lbl} score={r['total_score']:.1f} "
        f"{flags} | {news}"
    )


def save_watchlist(results: List[Dict], path: Path):
    """Save ranked watchlist to CSV."""
    import csv
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'symbol','short_name','price','gap_pct','rel_vol','float_m',
            'total_score','p2_gap','p3_rv','p4_catalyst',
            'news_summary','news_count','sentiment','news_provider',
            'risk_flags','rejects','scan_time'
        ])
        w.writeheader()
        for r in results:
            row = {k: v for k, v in r.items() if k not in ('pillars',)}
            w.writerow(row)
    print(f"  💾 Saved: {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Richard's Pre-Market Screener")
    parser.add_argument('--symbols', nargs='+', help='Ticker symbols to scan')
    parser.add_argument('--tv-csv', type=Path, help='Path to TradingView scanner CSV')
    parser.add_argument('--min-score', type=float, default=2.0, help='Min score threshold (default 2.0)')
    parser.add_argument('--save', action='store_true', help='Save watchlist CSV')
    parser.add_argument('--no-tv-api', action='store_true', help='Skip TV Premium API, use CSV/fallback only')
    args = parser.parse_args()

    print("=" * 60)
    print(f"Richard's Pre-Market Screener — {datetime.now().strftime('%Y-%m-%d %H:%M Berlin')}")
    print("=" * 60)

    results = run_screener(
        symbols        = args.symbols,
        tv_export_path = args.tv_csv,
        min_score      = args.min_score,
        use_tv_api    = not args.no_tv_api,
    )

    if results:
        print(f"\n📋 TOP SIGNALS:")
        print("-" * 60)
        for r in results:
            print(format_watchlist_row(r))
        if args.save:
            save_watchlist(results, WATCHLIST_FILE)
            print(f"  💾 {WATCHLIST_FILE.name}")
            # Also write a stable "latest" alias for live_event_loop.py
            save_watchlist(results, WATCHLIST_DIR / "watchlist_latest.csv")
            print(f"  💾 watchlist_latest.csv")
            # Sync directly to Docker volume SMB share so the container reads it
            _sync_to_docker_volume()
    else:
        print("\n  No signals found above threshold.")
        print("  Try lowering --min-score or check data sources.")
