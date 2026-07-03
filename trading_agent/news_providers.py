r"""
news_providers.py
=================
Unified news layer for P4 catalyst check.
Tries providers in order, returns first successful result.

Providers:
  1. Finnhub  (https://finnhub.io) - free tier: 60 req/min, company news
  2. Alpha Vantage (https://www.alphavantage.co) - free tier: 25 req/day, news sentiment
  3. Fincept/yfinance fallback

Token paths (PowerShell SecureString, DPAPI):
  Finnhub:      E:\Me\TradingAgent\config\finnhub_key.enc
  AlphaVantage: E:\Me\TradingAgent\config\alphavantage_key.enc
"""

import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

FINCEPT_YF = r"C:\Program Files\FinceptTerminal\scripts\yfinance_data.py"  # Windows only — unused in Docker


def _in_docker() -> bool:
    """Detect if running inside a Docker container."""
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read().lower() or "/app" in __file__
    except Exception:
        return False
TOKEN_DIR   = Path(r"E:\Me\TradingAgent\config")


# ── Token helpers ──────────────────────────────────────────────────────────────

def _read_token(filename: str) -> Optional[str]:
    """Decrypt PowerShell SecureString via PowerShell subprocess."""
    path = TOKEN_DIR / filename
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding='utf-8')
    except Exception:
        return None
    # Strip UTF-8 BOM if present (PowerShell 5.1 adds BOM with -Encoding UTF8)
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


# ── Provider 1: Finnhub ───────────────────────────────────────────────────────

def _finnhub_news(symbol: str, count: int = 10) -> List[Dict[str, Any]]:
    """
    Get company news from Finnhub.
    Returns list of {headline, summary, source, datetime, url, sentiment}.
    """
    api_key = _read_token('finnhub_key.enc')
    if not api_key:
        return []

    today = date.today()
    from_date = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    to_date   = today.strftime('%Y-%m-%d')

    url = (
        f"https://finnhub.io/api/v1/company-news"
        f"?symbol={symbol}&from={from_date}&to={to_date}"
        f"&token={api_key}"
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if isinstance(data, dict) and 'error' in data:
                print(f"[finnhub] error: {data['error']}")
                return []
            articles = []
            for item in (data if isinstance(data, list) else [])[:count]:
                articles.append({
                    'headline':   item.get('headline', ''),
                    'summary':    item.get('summary', ''),
                    'source':     item.get('source', ''),
                    'datetime':   item.get('datetime', 0),
                    'url':        item.get('url', ''),
                    'sentiment':  item.get('sentiment', 0),
                    'category':   item.get('category', ''),
                })
            return articles
    except Exception as e:
        print(f"[finnhub] exception: {e}")
        return []


def _finnhub_sentiment(symbol: str) -> Dict[str, Any]:
    """
    Get news sentiment metrics from Finnhub.
    Returns {sentiment_score, buzz, bullish_pct, bearish_pct}.
    """
    api_key = _read_token('finnhub_key.enc')
    if not api_key:
        return {}
    url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={api_key}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


# ── Provider 2: Alpha Vantage ────────────────────────────────────────────────

def _alphavantage_news(symbol: str) -> List[Dict[str, Any]]:
    """
    Get news from Alpha Vantage.
    Returns list of {title, summary, source, url, time_published}.
    Free tier: 25 requests/day. Function: NEWS_SENTIMENT.
    """
    api_key = _read_token('alphavantage_key.enc')
    if not api_key:
        return []

    url = (
        f"https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT"
        f"&tickers={symbol}"
        f"&apikey={api_key}"
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if 'Note' in data:
                print(f"[alphavantage] rate limit: {data.get('Note')}")
                return []
            if 'Error Message' in data:
                print(f"[alphavantage] error: {data.get('Error Message')}")
                return []
            feed = data.get('feed', [])
            articles = []
            for item in feed[:10]:
                articles.append({
                    'title':       item.get('title', ''),
                    'summary':     item.get('summary', ''),
                    'source':      item.get('source', ''),
                    'url':         item.get('url', ''),
                    'time_published': item.get('time_published', ''),
                    'sentiment':   item.get('overall_sentiment_score', 0),
                    'sentiment_label': item.get('overall_sentiment_label', ''),
                    'tickers':     item.get('ticker_sentiment', []),
                })
            return articles
    except Exception as e:
        print(f"[alphavantage] exception: {e}")
        return []


# ── Provider 3: Fincept/yfinance fallback ─────────────────────────────────────

def _yfinance_news(symbol: str, count: int = 5) -> List[Dict[str, Any]]:
    """Get news via yfinance — Fincept is Windows-only, skip in Docker."""
    # Skip Fincept in Docker — it's a Windows desktop app
    if _in_docker():
        fincept_available = False
    else:
        import os
        fincept_available = os.path.exists(FINCEPT_YF)

    if fincept_available:
        try:
            result = subprocess.run(
                ['python', FINCEPT_YF, 'news', symbol, str(count)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                raw = result.stdout.strip()
                if raw.startswith('['):
                    return json.loads(raw)
        except Exception:
            pass

    # Direct yfinance fallback
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        news = t.news
        return [
            {'title': n.get('title', ''), 'summary': n.get('content', ''),
             'source': n.get('publisher', ''), 'datetime': n.get('providerPublishTime', 0)}
            for n in (news or [])[:count]
        ]
    except Exception:
        return []


# ── Unified API ───────────────────────────────────────────────────────────────

def get_company_news(symbol: str, count: int = 10) -> Dict[str, Any]:
    """
    Fetch company news from all available providers.
    Strategy:
      - Finnhub for article count + headline quality (free, comprehensive)
      - Alpha Vantage for real sentiment scores (free, limited calls)
      - yfinance as final fallback

    Returns dict with:
      - articles: list of normalized news items
      - provider: which news provider succeeded
      - sentiment_score: -1 to +1 from Alpha Vantage (best free sentiment data)
      - bullish_pct: % bullish articles
    """
    articles = []
    av_articles = []  # Alpha Vantage articles (for sentiment)

    # 1. Get articles from Finnhub (best coverage on free tier)
    articles = _finnhub_news(symbol, count)
    provider = 'finnhub'

    if not articles:
        # 2. Fall back to Alpha Vantage (has sentiment but fewer articles)
        articles = _alphavantage_news(symbol)
        av_articles = articles
        provider = 'alphavantage'

    if not articles:
        # 3. Final fallback to yfinance/Fincept
        articles = _yfinance_news(symbol, count)
        provider = 'yfinance'

    if not articles:
        return {
            'articles':       [],
            'provider':       'none',
            'sentiment_score': 0,
            'bullish_pct':   0,
            'error':         'All news providers failed',
        }

    # Count articles from today/yesterday (handles Unix timestamps in seconds)
    recent = [
        a for a in articles
        if _is_recent(a.get('datetime') or a.get('time_published'))
    ]
    recent_count = len(recent)

    # Extract sentiment — Alpha Vantage has real sentiment on free tier
    sentiment_score = 0
    bullish_count  = 0

    # Try Alpha Vantage directly for sentiment scores (free tier: real scores)
    # Only call if Finnhub returned articles (avoid burning AV quota unnecessarily)
    av_data = _alphavantage_news(symbol) if articles else []
    if av_data:
        scores = [a.get('sentiment', 0) for a in av_data
                  if isinstance(a.get('sentiment'), (int, float))]
        if scores:
            sentiment_score = sum(scores) / len(scores)
        bullish_count = sum(
            1 for a in av_data
            if a.get('sentiment_label', '') in ('Bullish', 'Somewhat-Bullish')
        )
    else:
        # Finnhub sentiment is premium-only on free tier — skip it
        pass

    return {
        'articles':         articles,
        'provider':         provider,
        'sentiment_score':  round(sentiment_score, 3),
        'bullish_pct':      round(bullish_count / max(len(articles), 1) * 100, 1),
        'recent_count':     recent_count,
        'top_headline':     articles[0].get('headline') or articles[0].get('title', ''),
    }


def _is_recent(dt_val) -> bool:
    """Check if a datetime value is from today or yesterday.
    Handles: Unix timestamp in seconds (int), Unix timestamp in ms (int),
    or ISO date string (str).
    """
    if not dt_val:
        return False
    try:
        if isinstance(dt_val, int):
            # Unix timestamp — could be seconds or milliseconds, try both
            ts = dt_val
            if ts > 1e12:  # looks like milliseconds
                dt = datetime.fromtimestamp(ts / 1000)
            else:          # treat as seconds
                dt = datetime.fromtimestamp(ts)
        elif isinstance(dt_val, str):
            # ISO date string
            dt = datetime.fromisoformat(dt_val.replace('Z', '+00:00'))
        else:
            return False
        today_str = date.today().strftime('%Y-%m-%d')
        yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        return dt.strftime('%Y-%m-%d') in (today_str, yesterday)
    except Exception:
        return False


# ── P4 Catalyst Score ─────────────────────────────────────────────────────────

def score_catalyst(news_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert news result into a P4 catalyst score (0–1).
    
    Scoring logic:
      - 1.0: recent_count >= 3 AND (sentiment > 0.2 OR bullish_pct >= 60)
      - 0.75: recent_count >= 2 AND sentiment > 0.1
      - 0.5:  recent_count >= 1 AND sentiment > 0
      - 0.25: news exists but neutral/negative sentiment
      - 0.0:  no recent news
    """
    recent_count  = news_result.get('recent_count', 0)
    sentiment     = news_result.get('sentiment_score', 0)
    bullish_pct   = news_result.get('bullish_pct', 0)
    headline      = news_result.get('top_headline', '')[:80]
    provider      = news_result.get('provider', 'none')

    if recent_count >= 3 and (sentiment > 0.2 or bullish_pct >= 60):
        score = 1.0
        label = "STRONG"
    elif recent_count >= 2 and sentiment > 0.1:
        score = 0.75
        label = "POSITIVE"
    elif recent_count >= 1 and sentiment > 0:
        score = 0.5
        label = "NEUTRAL_POSITIVE"
    elif recent_count >= 1:
        score = 0.25
        label = "NEUTRAL"
    else:
        score = 0.0
        label = "NONE"
        articles = news_result.get('articles') or []
        headline = (articles[0].get('headline') or articles[0].get('title', ''))[:80] if articles else 'No recent news'

    return {
        'P4_catalyst':    score,
        'catalyst_label': label,
        'news_summary':   headline,
        'news_count':     recent_count,
        'sentiment':      sentiment,
        'bullish_pct':    bullish_pct,
        'news_provider':  provider,
    }
