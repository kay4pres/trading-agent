"""
cost_logger.py
==============
Append-only token cost log for Bull/Bear debates.

MiniMax-M2 pricing (per 1M tokens, all-in average):
  - Tier 1:  $0.95/M tokens  (0 < total ≤ 1M tokens/month)
  - Tier 2:  $0.45/M tokens  (1M < total ≤ 5M tokens/month)
  - Tier 3:  $0.35/M tokens  (5M+ total tokens/month)

All debate calls use max_tokens=400, so per-call total is typically 300-800 tokens.
"""

import csv
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR   = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
COST_CSV   = DATA_DIR / "cost_log.csv"
TZ           = timezone(timedelta(hours=2))

# MiniMax-M2 price tiers (per 1M tokens)
TIER_RATES = [
    (1_000_000,   0.95),   # Tier 1: first 1M tokens
    (5_000_000,   0.45),   # Tier 2: 1M–5M tokens
    (float('inf'), 0.35),  # Tier 3: 5M+ tokens
]

# Fallback estimate when API doesn't return usage (uses llm_call.py path)
FALLBACK_PROMPT_TOKENS   = 600   # conservative estimate for input
FALLBACK_COMPLETION_TOKENS = 200  # max_tokens=400, typically uses 150-350


def _calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost in USD using tiered MiniMax-M2 pricing."""
    total = prompt_tokens + completion_tokens
    if total == 0:
        return 0.0

    cost = 0.0
    remaining = total

    for tier_limit, rate_per_m in TIER_RATES:
        tier_tokens = min(remaining, tier_limit)
        cost += (tier_tokens / 1_000_000) * rate_per_m
        remaining -= tier_tokens
        if remaining <= 0:
            break

    return round(cost, 6)


def log_llm_call(
    symbol: str,
    role: str,          # "Bull" | "Bear" | "Research Manager"
    prompt_tokens: int | None,
    completion_tokens: int | None,
    usage_dict: dict | None = None,
    model: str = "MiniMax-M2",
    source: str = "scan-market",  # "scan-market" | "webhook" | "standalone"
):
    """
    Append one row to cost_log.csv.

    If usage_dict is provided (full API response usage field), prefer it.
    Otherwise fall back to estimated token counts.
    """
    if usage_dict:
        p = usage_dict.get("prompt_tokens", 0) or usage_dict.get("input_tokens", 0)
        c = usage_dict.get("completion_tokens", 0) or usage_dict.get("output_tokens", 0)
    else:
        p, c = FALLBACK_PROMPT_TOKENS, FALLBACK_COMPLETION_TOKENS

    t = p + c
    cost = _calculate_cost(p, c)

    row = {
        "timestamp":        datetime.now(TZ).isoformat(),
        "symbol":          symbol,
        "role":            role,
        "prompt_tokens":   p,
        "completion_tokens": c,
        "total_tokens":    t,
        "cost_usd":        cost,
        "model":           model,
        "source":          source,
        "usage_dict":      json.dumps(usage_dict) if usage_dict else "",
    }

    first_write = not COST_CSV.exists()
    COST_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(COST_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if first_write:
            writer.writeHeader()
        writer.writerow(row)

    return cost


def log_debate(symbol: str, calls: list[dict], source: str = "scan-market") -> float:
    """
    Log a full Bull/Bear debate (3 LLM calls: Bull, Bear, RM).

    calls = [
        {"role": "Bull",          "usage": {...} or None},
        {"role": "Bear",          "usage": {...} or None},
        {"role": "Research Manager", "usage": {...} or None},
    ]

    Returns total cost in USD.
    """
    total = 0.0
    for call in calls:
        cost = log_llm_call(
            symbol=symbol,
            role=call["role"],
            usage_dict=call.get("usage"),
            source=source,
        )
        total += cost
    return total


def summarize_cost_log(days: int = 30) -> dict:
    """
    Return a cost summary from the last N days of the log.
    Returns dict with: total_calls, total_tokens, total_cost, by_role, by_source, by_symbol.
    """
    if not COST_CSV.exists():
        return {"error": "No cost log found"}

    cutoff = datetime.now(TZ) - timedelta(days=days)

    rows = []
    with open(COST_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                if ts < cutoff:
                    continue
                rows.append(row)
            except Exception:
                continue

    if not rows:
        return {
            "period_days": days,
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "by_role": {},
            "by_source": {},
        }

    total_calls = len(rows)
    total_tokens = sum(int(r["total_tokens"]) for r in rows)
    total_cost   = sum(float(r["cost_usd"]) for r in rows)

    by_role = {}
    by_source = {}
    by_symbol = {}

    for r in rows:
        by_role[r["role"]]   = by_role.get(r["role"], 0) + float(r["cost_usd"])
        by_source[r["source"]] = by_source.get(r["source"], 0) + float(r["cost_usd"])
        sym = r["symbol"]
        by_symbol[sym] = by_symbol.get(sym, 0) + float(r["cost_usd"])

    return {
        "period_days":   days,
        "total_calls":   total_calls,
        "total_tokens":  total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_per_call": round(total_cost / total_calls, 4) if total_calls else 0,
        "projected_monthly": round(total_cost / days * 30, 4) if days else 0,
        "by_role":       {k: round(v, 4) for k, v in by_role.items()},
        "by_source":     {k: round(v, 4) for k, v in by_source.items()},
        "by_symbol":     {k: round(v, 4) for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])},
    }


if __name__ == "__main__":
    # Quick summary
    s = summarize_cost_log(days=30)
    print(json.dumps(s, indent=2, default=str))
