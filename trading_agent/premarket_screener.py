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

import sys
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import json

# ── Local imports ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from fincept_connector   import get_batch_quotes, get_historical, get_info
from news_providers      import get_company_news, score_catalyst

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR      = Path(r'E:\Me\TradingAgent\data')
WATCHLIST_DIR = Path(r'E:\Me\TradingAgent\data\watchlists')
WATCHLIST_DIR.mkdir(exist_ok=True)

TODAY = date.today()
WATCHLIST_FILE = WATCHLIST_DIR / f"watchlist_{TODAY.strftime('%Y%m%d')}.csv"

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
    Evaluate P4: News catalyst (delegate to news_providers.score_catalyst).
    news_list is ignored — we now use get_company_news() directly.
    """
    if not news_list:
        # No news provided — try fetching directly
        try:
            news_result = get_company_news(symbol, count=10)
        except Exception:
            news_result = {'articles': [], 'recent_count': 0, 'top_headline': 'No news', 'provider': 'none'}
    else:
        # Wrap the provided list in the format score_catalyst expects
        news_result = {
            'articles':    news_list,
            'recent_count': len(news_list),
            'top_headline': (news_list[0].get('title') or news_list[0].get('summary', ''))[:80],
            'provider':    'yfinance',
        }
    return score_catalyst(news_result)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCREENER
# ═══════════════════════════════════════════════════════════════════════════════

def load_tradingview_csv(path: Path) -> List[str]:
    """Extract tickers from TradingView scanner export CSV."""
    import csv
    symbols = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get('Ticker', row.get('Symbol', '')).strip()
                if sym:
                    symbols.append(sym.upper())
    except Exception as e:
        print(f"  ⚠️  Could not read TradingView CSV: {e}")
    return symbols


def run_screener(
    symbols: Optional[List[str]] = None,
    tv_export_path: Optional[Path] = None,
    use_finviz: bool = False,
    min_score: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Main screener entry point.

    Args:
        symbols:        explicit list of tickers to scan
        tv_export_path: path to TradingView scanner CSV
        use_finviz:    (reserved) use Finviz web scraper as primary
        min_score:     minimum Five Pillars score to include (default 2.0)

    Returns:
        ranked list of signals dicts
    """
    today_str = datetime.now().strftime('%Y-%m-%d %H:%M Berlin')

    # ── Step 1: Determine universe ──────────────────────────────────────────
    if tv_export_path and tv_export_path.exists():
        print(f"  📊 Loading from TradingView export: {tv_export_path.name}")
        universe = load_tradingview_csv(tv_export_path)
    elif symbols:
        universe = symbols
    else:
        print("  📊 Using default universe (no TV export found)")
        universe = DEFAULT_UNIVERSE

    print(f"  Scanning {len(universe)} symbols...")

    # ── Step 2: Batch quote all symbols ──────────────────────────────────────
    quotes = {}
    try:
        raw_quotes = get_batch_quotes(universe)
        for q in raw_quotes:
            sym = q.get('symbol', '')
            if sym:
                quotes[sym] = q
        print(f"  ✅ Got {len(quotes)} quotes")
    except Exception as e:
        print(f"  ❌ Quote fetch failed: {e}")
        return []

    # ── Step 3: Info + news for each (parallel-ish, batch where possible) ────
    results = []
    for sym in universe:
        quote = quotes.get(sym)
        if not quote or quote.get('price', 0) == 0:
            continue

        try:
            info = get_info(sym)
        except Exception:
            info = {}

        # News (top 10 articles — Finnhub → AlphaVantage → yfinance)
        try:
            news_result = get_company_news(sym, count=10)
        except Exception:
            news_result = {'articles': [], 'recent_count': 0, 'top_headline': '', 'provider': 'none'}

        pillars = check_pillars(quote, info)
        catalyst = check_catalyst(sym, news_result.get('articles', []))

        # Add P4 score
        pillars['P4_catalyst']  = catalyst['P4_catalyst']
        pillars['news_summary'] = catalyst['news_summary']
        total_score = pillars['score'] + catalyst['P4_catalyst']

        if total_score < min_score:
            continue

        results.append({
            'symbol':       sym,
            'short_name':   pillars.get('short_name', ''),
            'price':        round(quote.get('price', 0), 2),
            'gap_pct':      pillars['gap_pct'],
            'rel_vol':      pillars['rel_vol'],
            'float_m':      pillars.get('float_m'),
            'total_score':  round(total_score, 1),
            'pillars':      pillars['pillars'],
            'news_summary': catalyst['news_summary'],
            'risk_flags':   pillars['risk_flags'],
            'rejects':      pillars['rejects'],
            'scan_time':    today_str,
        })

    # ── Step 4: Rank by total score ─────────────────────────────────────────
    results.sort(key=lambda x: x['total_score'], reverse=True)

    print(f"\n  🎯 {len(results)} signals (score ≥ {min_score})")
    return results


def format_watchlist_row(r: Dict) -> str:
    """Format a single row for display/CSV."""
    flags = ', '.join(r['risk_flags']) if r['risk_flags'] else ''
    news = r['news_summary'][:60] if r['news_summary'] else '—'
    return (
        f"  {r['symbol']:<6} ${r['price']:<6} gap={r['gap_pct']:>+5.1f}% "
        f"rv={r['rel_vol']:.1f}× score={r['total_score']:.1f} "
        f"{flags} | {news}"
    )


def save_watchlist(results: List[Dict], path: Path):
    """Save ranked watchlist to CSV."""
    import csv
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'symbol','short_name','price','gap_pct','rel_vol','float_m',
            'total_score','pillars','news_summary','risk_flags','rejects','scan_time'
        ])
        w.writeheader()
        for r in results:
            row = {k: v for k, v in r.items()}
            row['pillars']   = json.dumps(row['pillars'])
            row['risk_flags']= json.dumps(row['risk_flags'])
            row['rejects']   = json.dumps(row['rejects'])
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
    args = parser.parse_args()

    print("=" * 60)
    print(f"Richard's Pre-Market Screener — {datetime.now().strftime('%Y-%m-%d %H:%M Berlin')}")
    print("=" * 60)

    results = run_screener(
        symbols      = args.symbols,
        tv_export_path = args.tv_csv,
        min_score    = args.min_score,
    )

    if results:
        print(f"\n📋 TOP SIGNALS:")
        print("-" * 60)
        for r in results:
            print(format_watchlist_row(r))
        if args.save:
            save_watchlist(results, WATCHLIST_FILE)
    else:
        print("\n  No signals found above threshold.")
        print("  Try lowering --min-score or check data sources.")
