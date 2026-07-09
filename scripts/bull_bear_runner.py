r"""
bull_bear_runner.py
===================
Reads pending signals — primary: signals_live.json (event-driven queue),
fallback: latest signals_YYYYMMDD_HHMM.json (timestamped scanner output).
Runs Bull/Bear debate, writes results to bull_bear_results.json.

Uses the LLM API key from vault/llm_api_key.enc (DPAPI encrypted).
On first run, if the vault key is missing, prompts for it.
Can run standalone — no Mavis daemon session required.

Usage:
    py -3 scripts\bull_bear_runner.py
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths — UTA/Docker: TRADING_DATA_DIR env var; Local: E:\Me\TradingAgent\data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR   = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
SIGNAL_IN  = DATA_DIR / "signals_live.json"
DEBATE_OUT = DATA_DIR / "bull_bear_results.json"
VAULT_DIR  = Path(r"E:\Me\TradingAgent\vault")
AGENT_DIR  = Path(__file__).parent.parent / "trading_agent"
VAULT_KEY    = VAULT_DIR / "llm_api_key.enc"
VAULT_CONFIG = VAULT_DIR / "llm_config.yaml"
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(AGENT_DIR))
from bull_bear_prompts import (
    BullBearSignal, build_bull_prompt, build_bear_prompt,
    build_rm_prompt, extract_score, extract_verdict
)
from trading_agent.cost_logger import log_debate


# ── Vault: read DPAPI-encrypted API key ───────────────────────────────────────

def _decrypt_vault_key(encoded_b64: str) -> str:
    """Decrypt a base64-encoded DPAPI blob via PowerShell subprocess. Returns plaintext."""
    # Write the b64 blob to a temp file, have PowerShell decrypt to another temp file.
    import tempfile, secrets
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


def get_vault_api_key() -> str | None:
    """Decrypt the vault LLM key. Returns None if not yet stored."""
    if not VAULT_KEY.exists():
        return None
    try:
        encoded = VAULT_KEY.read_text(encoding="utf-8").strip()
        return _decrypt_vault_key(encoded)
    except Exception:
        return None


def ensure_api_key() -> str:
    """Get the vault API key. If missing, prompt Kay via InputBox then store it."""
    key = get_vault_api_key()
    if key:
        return key

    print("[Vault] LLM API key not found — prompting for first-time setup...")

    ps = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        "$key = [Microsoft.VisualBasic.Interaction]::InputBox("
        "'Enter your MiniMax API key (for Bull/Bear debate):',"
        "'Trading Agent — LLM API Key', ''); "
        "if ([string]::IsNullOrWhiteSpace($key)) { exit 1 }; "
        "$enc = [System.Security.Cryptography.ProtectedData]::Protect("
        "[System.Text.Encoding]::UTF8.GetBytes($key), $null, "
        "[System.Security.Cryptography.DataProtectionScope]::CurrentUser); "
        "[Convert]::ToBase64String($enc)"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            "No key entered or setup failed. "
            "Run: powershell -File E:\\Me\\TradingAgent\\vault\\store_llm_key.ps1"
        )

    VAULT_KEY.parent.mkdir(parents=True, exist_ok=True)
    VAULT_KEY.write_text(result.stdout.strip(), encoding="utf-8")
    print(f"[Vault] Key stored securely at {VAULT_KEY}")
    # Return the freshly decrypted key directly — no recursive call needed
    return _decrypt_vault_key(result.stdout.strip())


# ── Config: build LLM config with vault key ────────────────────────────────────

def build_llm_config(api_key: str) -> Path:
    """Write a temp config YAML with the vault API key injected."""
    import yaml

    config = {
        "provider": {
            "minimax": {
                "npm": "@ai-sdk/openai",
                "options": {
                    "baseURL": "https://api.minimax.io/v1",
                    "apiKey": api_key,
                },
            }
        },
        "defaultModel": "minimax/MiniMax-M2.7",
    }

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    yaml.safe_dump(config, tmp, allow_unicode=True, sort_keys=False)
    tmp.close()
    return Path(tmp.name)


# ── LLM call ───────────────────────────────────────────────────────────────────

_temp_config: Path | None = None

def llm_call(model: str, system: str, prompt: str, max_tokens: int = 400) -> str:
    """Call LLM via llm_call.py with the vault API key."""
    global _temp_config
    if _temp_config is None:
        api_key = ensure_api_key()
        _temp_config = build_llm_config(api_key)
        print(f"[Vault] Using LLM config: {_temp_config}")

    result = subprocess.run(
        [sys.executable, str(LLM_CALLER),
         "--config", str(_temp_config),
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

    # Log cost (llm_call.py doesn't return usage → uses fallback estimates)
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