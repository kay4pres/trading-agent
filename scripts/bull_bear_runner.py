r"""
bull_bear_runner.py
====================
Called by the Mavis scan-market cron (which has the real LLM API key).
Reads pending signals from signals_live.json, runs Bull/Bear debate,
writes results to bull_bear_results.json.

Usage:
    py -3 scripts\bull_bear_runner.py

Mavis cron integration:
    Add to scan-market cron prompt:
    "Also run: py -3 E:\Me\TradingAgent\scripts\bull_bear_runner.py"
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────────
DATA_DIR    = Path(r"E:\Me\TradingAgent\data")
SIGNAL_IN   = DATA_DIR / "signals_live.json"
DEBATE_OUT  = DATA_DIR / "bull_bear_results.json"
LLM_CALLER  = Path(r"C:\Users\Kay\.mavis\.builtin-skills\llm-call\scripts\llm_call.py")
AGENT_DIR   = Path(r"E:\Me\TradingAgent\trading_agent")
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(AGENT_DIR))
from bull_bear_prompts import (
    BullBearSignal, build_bull_prompt, build_bear_prompt,
    build_rm_prompt, extract_score, extract_verdict
)


def llm_call(model: str, system: str, prompt: str, max_tokens: int = 400) -> str:
    """Call LLM via the built-in llm_call.py script."""
    result = subprocess.run(
        [sys.executable, str(LLM_CALLER),
         "--model", model,
         "--system", system,
         "--max-tokens", str(max_tokens),
         "--prompt", prompt],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"LLM call failed: {result.stderr.strip()}")
    return result.stdout.strip()


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


def main():
    print(f"[BullBear] {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')} — "
          f"Checking for pending signals...")

    if not SIGNAL_IN.exists():
        print("[BullBear] No signals_live.json found — nothing to debate")
        return

    with open(SIGNAL_IN, encoding="utf-8") as f:
        signals = json.load(f)
    if not isinstance(signals, list):
        signals = [signals]

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

        # Mark signals as debated
        debated = {r["signal"]["symbol"] for r in results}
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