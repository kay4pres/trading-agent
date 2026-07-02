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
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths — UTA/Docker: TRADING_DATA_DIR env var; Local: E:\Me\TradingAgent\data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR   = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
SIGNAL_IN  = DATA_DIR / "signals_live.json"
DEBATE_OUT = DATA_DIR / "bull_bear_results.json"
AGENT_DIR  = Path(__file__).parent.parent / "trading_agent"
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(AGENT_DIR))
from bull_bear_prompts import (
    BullBearSignal, build_bull_prompt, build_bear_prompt,
    build_rm_prompt, extract_score, extract_verdict
)
from cost_logger import log_debate


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
    bull_resp, bull_usage = _llm(
        prompt=build_bull_prompt(s),
        system="You are Bull — a rigorous Ross Cameron day trading analyst.",
        label=f"{s.symbol} Bull"
    )

    # Bear
    bear_resp, bear_usage = _llm(
        prompt=build_bear_prompt(s),
        system="You are Bear — a skeptical Ross Cameron risk manager.",
        label=f"{s.symbol} Bear"
    )

    # Research Manager
    rm_resp, rm_usage = _llm(
        prompt=build_rm_prompt(s, bull_resp, bear_resp),
        system="You are the Research Manager — objective synthesizer.",
        label=f"{s.symbol} Research Manager"
    )

    conviction = extract_score(rm_resp, "CONVICTION_SCORE")
    verdict = extract_verdict(rm_resp)

    # ── Log cost ─────────────────────────────────────────────────────────────
    total_cost = log_debate(
        symbol=s.symbol,
        calls=[
            {"role": "Bull",            "usage": bull_usage},
            {"role": "Bear",            "usage": bear_usage},
            {"role": "Research Manager","usage": rm_usage},
        ],
        source="scan-market",
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


def _llm(prompt: str, system: str, label: str) -> tuple[str, dict | None]:
    """
    Call the Mavis session's LLM inline.
    Returns (text, usage_dict). usage_dict may be None if not available.

    Uses the 'mavis llm-call' skill which reads from the daemon's config.
    Falls back to a direct HTTP call using the Mavis API key (returns usage).
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
            return result.stdout.strip(), None  # no usage from llm_call.py path
        if "401" not in result.stderr and "token" not in result.stderr.lower():
            raise RuntimeError(result.stderr.strip())
    except Exception:
        pass

    # Fallback: direct HTTP call — returns (text, usage_dict)
    return _llm_direct(prompt, system)


def _decrypt_vault_key(encoded_b64: str) -> str:
    """Decrypt a base64-encoded DPAPI blob via PowerShell subprocess. Returns plaintext."""
    import tempfile, secrets, subprocess
    token = secrets.token_hex(4)
    in_path  = Path(tempfile.gettempdir()) / f"vault_in_{token}.txt"
    out_path = Path(tempfile.gettempdir()) / f"vault_out_{token}.txt"
    in_path.write_text(encoded_b64, encoding="utf-8")
    ps = (
        f"$b64 = Get-Content '{in_path}' -Raw; "
        f"$encrypted = [Convert]::FromBase64String($b64.Trim()); "
        f"$decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect("
        f"$encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser); "
        f"[System.IO.File]::WriteAllBytes('{out_path}', $decrypted)"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(f"DPAPI decrypt failed: {r.stderr}")
    plaintext = out_path.read_bytes().decode("utf-8")
    in_path.unlink(missing_ok=True)
    out_path.unlink(missing_ok=True)
    return plaintext


def _llm_direct(prompt: str, system: str) -> tuple[str, dict | None]:
    """Direct HTTP call using MiniMax API from vault. Returns (text, usage_dict)."""
    import yaml, httpx

    VAULT_DIR = Path(r"E:\Me\TradingAgent\vault")
    VAULT_KEY = VAULT_DIR / "llm_api_key.enc"

    # 1. Get base URL from vault config
    vault_cfg_path = VAULT_DIR / "llm_config.yaml"
    if vault_cfg_path.exists():
        vault_cfg = yaml.safe_load(vault_cfg_path.read_text(encoding="utf-8"))
        base_url = vault_cfg.get("provider", {}).get("minimax", {}).get("options", {}).get(
            "baseURL", "https://api.minimax.io/v1"
        )
    else:
        base_url = "https://api.minimax.io/v1"

    # 2. Decrypt API key from vault via DPAPI
    if not VAULT_KEY.exists():
        raise RuntimeError("No LLM API key in vault — run vault/store_llm_key.ps1 to store it")
    encoded = VAULT_KEY.read_text(encoding="utf-8").strip()
    api_key = _decrypt_vault_key(encoded)

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
    usage = data.get("usage", None)
    text  = data["choices"][0]["message"]["content"].strip()
    return text, usage


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