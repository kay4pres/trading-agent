"""
watchlist_bull_bear.py
Parse watchlist_latest.csv, run Bull/Bear debate for each symbol,
write results to bull_bear_results.json.
"""

import base64, json, os, re, secrets, subprocess, sys, tempfile, time, csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import StringIO

# ── Paths ──────────────────────────────────────────────────────────────────────
VAULT_DIR  = Path(r"E:\Me\TradingAgent\vault")
DATA_DIR   = Path(r"E:\Me\TradingAgent\data")
DEBATE_OUT = DATA_DIR / "bull_bear_results.json"
WATCHLIST  = Path(r"E:\Me\TradingAgent\data\watchlists\watchlist_latest.csv")
AGENT_DIR  = Path(r"E:\Me\TradingAgent\trading_agent")
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(AGENT_DIR))
from bull_bear_prompts import BullBearSignal, build_bull_prompt, build_bear_prompt, build_rm_prompt, extract_score, extract_verdict

# ── Vault: DPAPI decrypt ───────────────────────────────────────────────────────

def _decrypt_vault_key(encoded_b64: str) -> str:
    token = secrets.token_hex(4)
    in_path  = Path(tempfile.gettempdir()) / f"vault_in_{token}.txt"
    out_path = Path(tempfile.gettempdir()) / f"vault_out_{token}.txt"
    in_path.write_text(encoded_b64, encoding="utf-8")
    ps = (
        f"Add-Type -AssemblyName System.Security; "
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

def get_api_key() -> str:
    VAULT_KEY = VAULT_DIR / "llm_api_key.enc"
    if not VAULT_KEY.exists():
        raise RuntimeError("No LLM API key in vault")
    # The vault file stores raw DPAPI-encrypted bytes
    raw_bytes = VAULT_KEY.read_bytes()
    # Decode as base64 then decrypt
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
    return _decrypt_vault_key(b64_str)

# ── Parse watchlist CSV ────────────────────────────────────────────────────────

def parse_watchlist() -> list:
    raw = WATCHLIST.read_text(encoding="utf-8")
    reader = csv.DictReader(StringIO(raw))
    signals = []
    for row in reader:
        sym = row.get("symbol", "").strip()
        if not sym or sym == "symbol":
            continue
        try:
            price   = float(row.get("price", 0) or 0)
            gap_pct = float(row.get("gap_pct", 0) or 0)
            rel_vol = float(row.get("rel_vol", 0) or 0)
            float_m = float(row.get("float_m", 0) or 0)
            score   = float(row.get("total_score", 0) or 0)
            news_sum = row.get("news_summary", "No recent news")
        except Exception:
            continue
        yesterday_close = round(price / (1 + gap_pct/100), 2) if gap_pct != 0 else price
        target = round(price + 0.20, 2)
        stop   = round(price - 0.10, 2)
        signals.append({
            "symbol": sym,
            "price": price,
            "today_close": price,
            "yesterday_close": yesterday_close,
            "gap_pct": gap_pct,
            "float_m": float_m,
            "rel_vol": rel_vol,
            "rsi": 50.0,
            "news": f"Gap {gap_pct}%, RelVol {rel_vol}x, Score {score}/5 — {news_sum}",
            "score": score,
            "target": target,
            "stop": stop,
            "qty": 100,
            "intraday_high": 0.0,
            "pullback_dollar": 0.0,
            "pullback_atr_ratio": 0.0,
            "debated": False,
        })
    return signals

# ── LLM call ───────────────────────────────────────────────────────────────────

def llm_call(system: str, prompt: str, max_tokens: int = 300) -> str:
    import yaml, httpx
    api_key = get_api_key()
    base_url = "https://api.minimax.io/v1"
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
                "max_tokens": max_tokens,
                "temperature": 0.3,
            }
        )
    if resp.status_code != 200:
        raise RuntimeError(f"LLM call failed: {resp.status_code} {resp.text}")
    return resp.json()["choices"][0]["message"]["content"].strip()

# ── Debate ─────────────────────────────────────────────────────────────────────

def run_debate(sig: dict) -> dict:
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
        system="You are Bull — a rigorous Ross Cameron day trading analyst.",
        prompt=build_bull_prompt(s),
        max_tokens=300,
    )

    print(f"[BullBear] {s.symbol} — Bear...")
    bear_resp = llm_call(
        system="You are Bear — a skeptical Ross Cameron risk manager.",
        prompt=build_bear_prompt(s),
        max_tokens=300,
    )

    print(f"[BullBear] {s.symbol} — Research Manager...")
    rm_resp = llm_call(
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

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[WatchlistBullBear] {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')} — "
          f"Parsing watchlist and running debates...")

    signals = parse_watchlist()
    if not signals:
        print("[WatchlistBullBear] No symbols in watchlist")
        return

    print(f"[WatchlistBullBear] {len(signals)} symbol(s) to debate")
    results = []

    for sig in signals:
        sym = sig["symbol"]
        try:
            result = run_debate(sig)
            results.append(result)
            print(f"[WatchlistBullBear] {sym} → {result['verdict']} "
                  f"(conviction {result['conviction']}/10)")
            time.sleep(1)
        except Exception as e:
            print(f"[WatchlistBullBear] {sym} failed: {e}")

    if results:
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

        print(f"[WatchlistBullBear] Done — {len(results)} result(s) → {DEBATE_OUT}")

        # Check for APPROVE signals
        approves = [r for r in results if r["verdict"] == "APPROVE"]
        if approves:
            print(f"[APPROVE] {len(approves)} signal(s) approved:")
            for a in approves:
                print(f"  {a['symbol']} — conviction {a['conviction']}/10")
        else:
            print("[WatchlistBullBear] No APPROVE signals found")
    else:
        print("[WatchlistBullBear] No debates completed")

if __name__ == "__main__":
    main()
