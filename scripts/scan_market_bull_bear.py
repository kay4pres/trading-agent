r"""
scan_market_bull_bear.py
=======================
Called by the Mavis scan-market cron session (which has the real LLM API key).

This script:
  1. Reads pending signals — primary: signals_live.json (event-driven queue),
     fallback: latest signals_YYYYMMDD_HHMM.json (timestamped scanner output)
  2. Runs Bull/Bear/Research Manager debate using the Mavis session's LLM
  3. Writes results to bull_bear_results.json

The debate runs inside this session — NOT in a subprocess — so it uses the
real API key from the Mavis daemon, not a placeholder config.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths
# Docker volume UNC share (SMB): \\10.8.0.10\Docker\data  → /app/data in container
# Kay's local path: E:\Me\TradingAgent\data
# When called from Mavis cron on Kay's host, use the Docker volume UNC so
# results are visible to the container dashboard AND Kay's local machine.
_DOCKER_VOLUME_UNC = Path(r'\\10.8.0.10\Docker\data')
_LOCAL_DATA_DIR    = Path(r'E:\Me\TradingAgent\data')

_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
if _DATA_ROOT:
    DATA_DIR = Path(_DATA_ROOT)
elif _DOCKER_VOLUME_UNC.exists():
    # Use Docker volume UNC — shared between container and Kay's host
    DATA_DIR = _DOCKER_VOLUME_UNC
else:
    # Fallback to local path
    DATA_DIR = _LOCAL_DATA_DIR
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
    Call the LLM for Bull/Bear debate.
    Priority:
      1. Mavis daemon inline LLM (when running from Mavis cron on Kay's machine)
      2. Kay's vault DPAPI key (when vault key is accessible on host)
      3. Container MINIMAX_API_KEY env var (Docker deployment)
    Returns (text, usage_dict). usage_dict may be None if not available.
    """
    # ── Try Mavis daemon LLM via IPC socket ─────────────────────────────────
    # When run from Mavis's scan-market cron, the Mavis daemon is on the same host.
    # Use the daemon's LLM endpoint if available (avoids vault key dependency).
    try:
        import socket, threading

        def _try_daemon_llm() -> tuple[str, dict] | None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                sock.connect(("127.0.0.1", 15321))
                req = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "llm.chat",
                    "params": {
                        "model": "MiniMax-M2.7",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 400,
                        "temperature": 0.3,
                    }
                }).encode() + b'\n'
                sock.sendall(req)
                sock.shutdown(socket.SHUT_WR)
                chunks = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                resp = json.loads(b"".join(chunks).decode())
                if "result" in resp:
                    text = resp["result"].get("content", "")
                    usage = resp["result"].get("usage", None)
                    return text, usage
            except Exception:
                pass
            finally:
                sock.close()
            return None

        result = _try_daemon_llm()
        if result:
            print(f"[BullBear] {label} → Mavis daemon LLM")
            return result
    except Exception:
        pass

    # ── Try Kay's vault key (when running on Kay's Windows host) ─────────────
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
            print(f"[BullBear] {label} → llm_call.py")
            return result.stdout.strip(), None
        if "401" not in result.stderr and "token" not in result.stderr.lower():
            raise RuntimeError(result.stderr.strip())
    except Exception:
        pass

    # ── Fallback: direct HTTP call using vault key ────────────────────────────
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
    """Direct HTTP call using MiniMax API. Returns (text, usage_dict)."""
    import yaml, httpx

    VAULT_DIR = Path(r"E:\Me\TradingAgent\vault")
    VAULT_KEY = VAULT_DIR / "llm_api_key.enc"

    # 1. Try MINIMAX_API_KEY env var first (set in Docker container vault)
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    base_url = "https://api.minimax.io/v1"

    # 2. If not in env, try Kay's vault (DPAPI-encrypted)
    if not api_key:
        vault_cfg_path = VAULT_DIR / "llm_config.yaml"
        if vault_cfg_path.exists():
            vault_cfg = yaml.safe_load(vault_cfg_path.read_text(encoding="utf-8"))
            base_url = vault_cfg.get("provider", {}).get("minimax", {}).get("options", {}).get(
                "baseURL", "https://api.minimax.io/v1"
            )
        if VAULT_KEY.exists():
            try:
                encoded = VAULT_KEY.read_text(encoding="utf-8").strip()
                api_key = _decrypt_vault_key(encoded)
            except Exception:
                api_key = ""

    if not api_key or api_key == "sk-xxx":
        raise RuntimeError(
            "No LLM API key — set MINIMAX_API_KEY env var, "
            "or run vault/store_llm_key.ps1 to store Kay's key"
        )

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


def _load_signals() -> list:
    """
    Load signals from the pipeline.
    Priority:
      1. signals_live.json  — event-driven queue from live_event_loop.py
      2. Latest signals_YYYYMMDD_HHMM.json — timestamped scan output from
         intraday_scanner.py (Mavis cron or dashboard scan_thread)
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
    print(f"[ScanMarket] signals_live.json not found — falling back to {latest.name}")

    with open(latest, encoding="utf-8") as f:
        scan_data = json.load(f)

    # intraday_scanner.py writes { run_time, gap_stocks, total_signals, ranked_signals }
    ranked = scan_data.get("ranked_signals", [])
    # Convert scanner format → Bull/Bear format (ticker → symbol)
    converted = []
    for s in ranked:
        converted.append({
            "symbol":              s.get("ticker", s.get("symbol", "?")),
            "price":               s.get("price", 0),
            "today_close":         s.get("price", 0),
            "yesterday_close":      s.get("price", 0) / (1 + (s.get("gap_pct", 0) / 100)),
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
            "news":                f"Scanner pullback signal (score={s.get('score',0)}, "
                                    f"gap={s.get('gap_pct',0)}%, "
                                    f"ATR ratio={s.get('pullback_atr_ratio',0):.1f})",
            "debated":             False,
        })
    return converted


def main():
    print(f"[ScanMarket BullBear] {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')} — "
          f"Checking for pending signals...")

    signals = _load_signals()
    if not signals:
        print("[ScanMarket BullBear] No signals found (signals_live.json absent, "
              "no timestamped scan files today)")
        return

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
        # Append to existing results (try Docker volume first, then local fallback)
        existing = []
        for results_path in [DEBATE_OUT, _LOCAL_DATA_DIR / "bull_bear_results.json"]:
            if results_path.exists():
                try:
                    with open(results_path, encoding="utf-8") as f:
                        existing = json.load(f).get("debates", [])
                    print(f"[ScanMarket BullBear] Loaded {len(existing)} existing results from {results_path}")
                    break
                except Exception:
                    pass

        all_results = existing + results
        DEBATE_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBATE_OUT, "w", encoding="utf-8") as f:
            json.dump({"debates": all_results}, f, indent=2, default=str)
        print(f"[ScanMarket BullBear] Wrote {len(all_results)} results → {DEBATE_OUT}")

        # Also sync to local path so Kay's host can see it
        local_debate_out = _LOCAL_DATA_DIR / "bull_bear_results.json"
        try:
            local_debate_out.parent.mkdir(parents=True, exist_ok=True)
            with open(local_debate_out, "w", encoding="utf-8") as f:
                json.dump({"debates": all_results}, f, indent=2, default=str)
            print(f"[ScanMarket BullBear] Synced to local: {local_debate_out}")
        except Exception as e:
            print(f"[ScanMarket BullBear] Local sync failed (non-critical): {e}")

        # Mark signals as debated in signals_live.json if it exists
        debated = {r["signal"]["symbol"] for r in results}
        for sig_path in [SIGNAL_IN, _LOCAL_DATA_DIR / "signals_live.json"]:
            if sig_path.exists():
                try:
                    with open(sig_path, encoding="utf-8") as f:
                        sigs = json.load(f)
                    sigs = sigs if isinstance(sigs, list) else [sigs]
                    for sig in sigs:
                        if sig.get("symbol", "").upper() in {s.upper() for s in debated}:
                            sig["debated"] = True
                    with open(sig_path, "w", encoding="utf-8") as f:
                        json.dump(sigs, f, indent=2, default=str)
                except Exception:
                    pass

        print(f"[ScanMarket BullBear] Done — {len(results)} new result(s)")
    else:
        print("[ScanMarket BullBear] No debates completed")


if __name__ == "__main__":
    main()