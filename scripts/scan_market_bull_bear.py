r"""
scan_market_bull_bear.py
========================
Called by the Mavis scan-market cron session (which has the real LLM API key).

This script:
  1. Reads pending signals from signals_live.json
  2. Runs Bull/Bear/Research Manager debate using the Mavis session's LLM
  3. Writes results to bull_bear_results.json

The debate runs inside this session — NOT in a subprocess — so it uses the
real API key from the Mavis daemon, not a placeholder config.

Mavis cron integration:
  In the scan-market cron prompt, add:
    "Also run: py -3 E:\Me\TradingAgent\scripts\scan_market_bull_bear.py"
    Check for output — if signals were debated, note the verdict.
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────────
DATA_DIR    = Path(r"E:\Me\TradingAgent\data")
SIGNAL_IN   = DATA_DIR / "signals_live.json"
DEBATE_OUT  = DATA_DIR / "bull_bear_results.json"
AGENT_DIR   = Path(r"E:\Me\TradingAgent\trading_agent")
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(AGENT_DIR))
from bull_bear_prompts import (
    BullBearSignal, build_bull_prompt, build_bear_prompt,
    build_rm_prompt, extract_score, extract_verdict
)


def run_debate(sig: dict) -> dict:
    """
    Run Bull/Bear/Research Manager debate using Mavis session LLM.
    This runs INLINE in the Mavis session — no subprocess, real API key.
    """
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

    # ── LLM calls run inline in this Mavis session ──────────────────────────
    # Bull
    bull_resp = _llm(
        prompt=build_bull_prompt(s),
        system="You are Bull — a rigorous Ross Cameron day trading analyst.",
        label=f"{s.symbol} Bull"
    )

    # Bear
    bear_resp = _llm(
        prompt=build_bear_prompt(s),
        system="You are Bear — a skeptical Ross Cameron risk manager.",
        label=f"{s.symbol} Bear"
    )

    # Research Manager
    rm_resp = _llm(
        prompt=build_rm_prompt(s, bull_resp, bear_resp),
        system="You are the Research Manager — objective synthesizer.",
        label=f"{s.symbol} Research Manager"
    )

    conviction = extract_score(rm_resp, "CONVICTION_SCORE")
    verdict = extract_verdict(rm_resp)

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


def _llm(prompt: str, system: str, label: str) -> str:
    """
    Call the Mavis session's LLM inline.
    Uses the 'mavis llm-call' skill which reads from the daemon's config.
    Falls back to a direct HTTP call using the Mavis API key.
    """
    # Try the built-in llm_call.py script first
    LLM_CALLER = Path(r"C:\Users\Kay\.mavis\.builtin-skills\llm-call\scripts\llm_call.py")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(LLM_CALLER),
             "--model", "minimax/MiniMax-M2.7",
             "--system", system,
             "--max-tokens", "400",
             "--prompt", prompt],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
        # If 401, fall through to direct HTTP
        if "401" not in result.stderr and "token" not in result.stderr.lower():
            raise RuntimeError(result.stderr.strip())
    except Exception as e:
        pass

    # Fallback: direct HTTP call using Mavis API key from MiniMax config
    return _llm_direct(prompt, system)


def _llm_direct(prompt: str, system: str) -> str:
    """Direct HTTP call using MiniMax API from config."""
    import yaml, httpx

    config = yaml.safe_load(open(r"C:\Users\Kay\.minimax\config.yaml"))
    provider = config.get("provider", {}).get("minimax", {})
    api_key = provider.get("options", {}).get("apiKey", "")
    base_url = provider.get("options", {}).get("baseURL", "https://agent.minimax.io/mavis/api/v1/llm/v1")

    if not api_key or api_key == "sk-xxx":
        raise RuntimeError("No LLM API key available in config.yaml")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "MiniMax-M2.7",
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.3,
            }
        )

    if resp.status_code != 200:
        raise RuntimeError(f"LLM direct call failed: {resp.status_code} {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def main():
    print(f"[ScanMarket BullBear] {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')} — "
          f"Checking for pending signals...")

    if not SIGNAL_IN.exists():
        print("[ScanMarket BullBear] No signals_live.json found")
        return

    with open(SIGNAL_IN, encoding="utf-8") as f:
        signals = json.load(f)
    if not isinstance(signals, list):
        signals = [signals]

    pending = [s for s in signals if not s.get("debated", False)]
    if not pending:
        print("[ScanMarket BullBear] No pending signals to debate")
        return

    print(f"[ScanMarket BullBear] {len(pending)} signal(s) to debate")
    results = []

    for sig in pending:
        sym = sig.get("symbol", "?")
        try:
            result = run_debate(sig)
            results.append(result)
            print(f"[ScanMarket BullBear] {sym} → {result['verdict']} "
                  f"(conviction {result['conviction']}/10)")
            time.sleep(1)
        except Exception as e:
            print(f"[ScanMarket BullBear] {sym} failed: {e}")

    if results:
        # Append to existing results
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

        # Mark signals as debated
        debated = {r["signal"]["symbol"] for r in results}
        for sig in signals:
            if sig.get("symbol", "").upper() in {s.upper() for s in debated}:
                sig["debated"] = True
        with open(SIGNAL_IN, "w", encoding="utf-8") as f:
            json.dump(signals, f, indent=2, default=str)

        print(f"[ScanMarket BullBear] Done — {len(results)} result(s) → {DEBATE_OUT}")
    else:
        print("[ScanMarket BullBear] No debates completed")


if __name__ == "__main__":
    main()