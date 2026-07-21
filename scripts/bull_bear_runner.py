r"""
bull_bear_runner.py
===================
Reads pending signals — primary: signals_live.json (event-driven queue),
fallback: latest signals_YYYYMMDD_HHMM.json (timestamped scanner output).
Runs Bull/Bear debate, writes results to bull_bear_results.json.

Uses MINIMAX_API_KEY from environment or /app/vault/MINIMAX_API_KEY.env.
Can run standalone — no Mavis daemon session required.

Usage:
    python -m scripts.bull_bear_runner
"""

import httpx
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths — UAT/Docker: TRADING_DATA_DIR env var; Local: E:\Me\TradingAgent\data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR   = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
SIGNAL_IN  = DATA_DIR / "signals_live.json"
DEBATE_OUT = DATA_DIR / "bull_bear_results.json"
VAULT_DIR  = Path("/app/vault")
VAULT_KEY  = VAULT_DIR / "MINIMAX_API_KEY.env"
AGENT_DIR  = Path(__file__).parent.parent / "trading_agent"
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(AGENT_DIR))
from bull_bear_prompts import (
    BullBearSignal, build_bull_prompt, build_bear_prompt,
    build_rm_prompt, extract_score, extract_verdict
)
from trading_agent.cost_logger import log_debate


# ── Vault: read API key from env or vault file ──────────────────────────────────

def get_vault_api_key() -> str:
    """Read MiniMax API key from env var or plaintext vault file."""
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if api_key:
        return api_key
    if VAULT_KEY.exists():
        return VAULT_KEY.read_text().strip()
    raise RuntimeError(
        "MINIMAX_API_KEY not set in environment and "
        f"/app/vault/MINIMAX_API_KEY.env not found. "
        "Cannot call LLM."
    )


# ── LLM call — direct httpx to MiniMax API ────────────────────────────────────

def llm_call(model: str, system: str, prompt: str, max_tokens: int = 400) -> str:
    """Call LLM directly via httpx + MiniMax chat completions API."""
    api_key = get_vault_api_key()
    response = httpx.post(
        "https://api.minimax.io/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "minimax/MiniMax-M2.7",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ── Bull/Bear debate ────────────────────────────────────────────────────────────

def run_debate(sig: dict) -> dict:
    """Run full Bull/Bear/Research Manager debate on a signal."""
    s = BullBearSignal(
        symbol=sig["symbol"],
        price=sig["price"],
        today_close=sig.get("price", sig["price"]),
        yesterday_close=sig.get("yesterday_close", sig["price"]),
        gap_pct=sig.get("gap_pct", 0.0),
        float_m=sig.get("float_m", 0.0),
        rel_vol=sig.get("rel_vol", 0.0),
        rsi=sig.get("rsi", 50.0),
        news=sig.get("news", "Live pullback event"),
        score=sig.get("score", 4.5),
        target=sig.get("target", round(sig["price"] + 0.20, 2)),
        stop=sig.get("stop", round(sig["price"] - 0.10, 2)),
        qty=sig.get("qty", 100),
        intraday_high=sig.get("intraday_high", 0.0),
        pullback_dollar=sig.get("pullback_dollar", 0.0),
        pullback_atr_ratio=sig.get("pullback_atr_ratio", 0.0),
    ).compute_rr()

    print(f"[BullBear] {s.symbol} — Bull...")
    bull_resp = llm_call(
        "minimax/MiniMax-M2.7",
        system="You are Bull — a rigorous Ross Cameron day trading analyst.",
        prompt=build_bull_prompt(s),
        max_tokens=300,
    )

    print(f"[BullBear] {s.symbol} — Bear...")
    bear_resp = llm_call(
        "minimax/MiniMax-M2.7",
        system="You are Bear — a skeptical Ross Cameron risk manager.",
        prompt=build_bear_prompt(s),
        max_tokens=300,
    )

    print(f"[BullBear] {s.symbol} — Research Manager...")
    rm_resp = llm_call(
        "minimax/MiniMax-M2.7",
        system="You are the Research Manager — objective synthesizer.",
        prompt=build_rm_prompt(s, bull_resp, bear_resp),
        max_tokens=400,
    )

    conviction = extract_score(rm_resp, "CONVICTION_SCORE")
    verdict = extract_verdict(rm_resp)

    total_cost = log_debate(
        symbol=s.symbol,
        calls=[
            {"role": "Bull",            "usage": None},
            {"role": "Bear",            "usage": None},
            {"role": "Research Manager","usage": None},
        ],
        source="standalone",
    )
    print(f"[Cost] {s.symbol} Bull/Bear debate: ${total_cost:.4f}")

    return {
        "symbol": s.symbol,
        "signal": sig,
        "bull": bull_resp,
        "bear": bear_resp,
        "research_manager": rm_resp,
        "conviction": conviction,
        "verdict": verdict,
        "debated_at": datetime.now(AMSTERDAM_TZ).isoformat(),
    }


def _signals_are_fresh() -> bool:
    """
    Return True if signals_live.json was updated in the last 5 minutes.
    Prevents debating stale data from yesterday's session when the market
    just opened and the scan_thread hasn't run yet.
    """
    if not SIGNAL_IN.exists():
        return False
    age_seconds = time.time() - SIGNAL_IN.stat().st_mtime
    if age_seconds > 300:  # 5 minutes
        print(f"[BullBear] signals_live.json is {age_seconds:.0f}s old — skipping (scan not yet fresh)")
        return False
    return True


def _load_signals() -> list:
    """
    Load signals from the pipeline.
    Priority:
      1. signals_live.json  — event-driven queue from live_event_loop.py
      2. Latest signals_YYYYMMDD_HHMM.json — timestamped scan output
    """
    # ── Primary: event-driven queue ───────────────────────────────────────────
    if SIGNAL_IN.exists():
        with open(SIGNAL_IN, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            return raw
        return [raw]

    # ── Fallback: latest timestamped scan file ────────────────────────────────
    today_str = datetime.now(AMSTERDAM_TZ).strftime('%Y%m%d')
    candidates = sorted(
        DATA_DIR.glob(f'signals_{today_str}_*.json'),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not candidates:
        return []

    latest = candidates[0]
    print(f"[BullBear] signals_live.json not found — falling back to {latest.name}")

    with open(latest, encoding="utf-8") as f:
        scan_data = json.load(f)

    ranked = scan_data.get("ranked_signals", [])
    converted = []
    for s in ranked:
        converted.append({
            "symbol":              s.get("ticker", s.get("symbol", "?")),
            "price":               s.get("price", 0),
            "today_close":         s.get("price", 0),
            "yesterday_close":     s.get("price", 0) / (1 + (s.get("gap_pct", 0) / 100)),
            "gap_pct":             s.get("gap_pct", 0),
            "float_m":             s.get("float_m", 0),
            "rel_vol":             s.get("volume_ratio", s.get("rel_vol", 0)),
            "rsi":                 s.get("rsi", 50),
            "score":               s.get("score", 0),
            "target":              round(s.get("price", 0) + 0.20, 2),
            "stop":                round(s.get("price", 0) - 0.10, 2),
            "qty":                 100,
            "intraday_high":       s.get("intraday_high", 0),
            "pullback_dollar":     s.get("pullback_dollar", 0),
            "pullback_atr_ratio":  s.get("pullback_atr_ratio", 0),
            "news":                f"Scanner signal (score={s.get('score',0)}, "
                                    f"gap={s.get('gap_pct',0)}%, "
                                    f"ATR ratio={s.get('pullback_atr_ratio',0):.1f})",
            "debated":             False,
        })
    return converted


def main():
    print(f"[BullBear] {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')} — "
          f"Checking for pending signals...")

    # Guard: don't debate stale signals (e.g. yesterday's file before first scan completes)
    if not _signals_are_fresh():
        print("[BullBear] Signals not fresh enough — skipping this run. "
              "Will retry at next cron slot.")
        return

    signals = _load_signals()
    if not signals:
        print("[BullBear] No signals found (signals_live.json absent, "
              "no timestamped scan files today)")
        return

    pending = [s for s in signals if not s.get("debated", False)]
    if not pending:
        print("[BullBear] No pending signals to debate")
        return

    print(f"[BullBear] {len(pending)} signal(s) to debate")

    results = []
    for sig in pending:
        sym = sig.get("symbol", "?")
        try:
            result = run_debate(sig)
            results.append(result)
            print(f"[BullBear] {sym} → {result['verdict']} "
                  f"(conviction {result['conviction']}/10)")
            time.sleep(1)  # Rate limit between debates
        except Exception as e:
            print(f"[BullBear] {sym} debate failed: {e}")

    if results:
        # Load existing results (don't overwrite)
        existing = []
        if DEBATE_OUT.exists():
            try:
                with open(DEBATE_OUT, encoding="utf-8") as f:
                    existing = json.load(f).get("debates", [])
            except Exception:
                existing = []

        all_results = existing + results
        DEBATE_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBATE_OUT, "w", encoding="utf-8") as f:
            json.dump({"debates": all_results}, f, indent=2, default=str)

        # Mark signals as debated in signals_live.json if it exists
        debated = {r["signal"]["symbol"] for r in results}
        if SIGNAL_IN.exists():
            for sig in signals:
                if sig.get("symbol", "").upper() in {s.upper() for s in debated}:
                    sig["debated"] = True
            with open(SIGNAL_IN, "w", encoding="utf-8") as f:
                json.dump(signals, f, indent=2, default=str)

        print(f"[BullBear] Done — {len(results)} result(s) written to {DEBATE_OUT}")

    else:
        print("[BullBear] No debates completed successfully")


if __name__ == "__main__":
    main()
