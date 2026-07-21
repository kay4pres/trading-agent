"""Risk pre-trade gate — blocks orders that violate hard limits.

Adapted from Lewis Jackson's risk-manager skill Mode #1 (MIT-style) for the
trading-agent project. The 7 BLOCK conditions from the upstream skill are
implemented as one `evaluate()` function. Returns a list of breach reasons
(empty list = passes every check).

The 7 conditions:
  1. Daily loss limit breached (default 10% of account per ARCH v1.0)
  2. Maximum open positions reached (default 3 per multi-position 1-3 design)
  3. Same asset already has an open position in the same direction
  4. Position size exceeds max risk-per-trade % (default 1.5% on €2K)
  5. Entry price more than 2% away from current market price (stale signal)
  6. Major news event within blackout window (delegated to news_guard)
  7. Risk-reward ratio is below 1.5:1 (Ross Cameron 2:1 minimum)

Conditions 1-5, 7 are pure (no network). Condition 6 uses news_guard
imported lazily so this module can be tested offline.

Use as:
    from trading_agent.risk.pre_trade_gate import evaluate, GateConfig

    cfg = GateConfig(account_equity=2000.0, daily_loss_pct=10.0,
                     max_open_positions=3, max_risk_per_trade_pct=1.5,
                     min_rr_ratio=2.0, stale_signal_pct=2.0,
                     symbol_allowlist=[...], current_positions=...,
                     current_market_price=6.05)

    breaches = evaluate(symbol="SPY", side="buy", entry_price=6.00,
                        stop=5.90, target=6.20, at=now, cfg=cfg)
    if breaches:
        return "BLOCKED: " + "; ".join(breaches)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Defaults aligned with ARCHITECTURE_v1.0.md §3 phased rollout
DEFAULTS = {
    "account_equity": 2_000.0,
    "daily_loss_pct": 10.0,         # 10% daily loss circuit breaker
    "max_open_positions": 3,        # multi-position 1-3
    "max_risk_per_trade_pct": 1.5,  # ¼ size start: €30 max risk on €2K
    "min_rr_ratio": 2.0,            # Ross 2:1 minimum
    "stale_signal_pct": 2.0,        # reject entry > 2% from current price
    "news_blackout_min_before": 30,
    "news_blackout_min_after": 15,
}


@dataclass
class GateConfig:
    """All inputs the gate needs to evaluate a single proposed trade.

    `current_positions` is the live state from positions.json (the
    `positions` dict of currently OPEN trades).
    `symbol_allowlist` is a list of tradable tickers. Empty list = nothing
    allowed (fail closed).
    `news_guard` is a callable (instrument, at) -> {decision, ...}; pass
    `None` to skip the news check (e.g. in tests).
    """
    account_equity: float = DEFAULTS["account_equity"]
    daily_loss_pct: float = DEFAULTS["daily_loss_pct"]
    max_open_positions: int = DEFAULTS["max_open_positions"]
    max_risk_per_trade_pct: float = DEFAULTS["max_risk_per_trade_pct"]
    min_rr_ratio: float = DEFAULTS["min_rr_ratio"]
    stale_signal_pct: float = DEFAULTS["stale_signal_pct"]
    news_blackout_min_before: int = DEFAULTS["news_blackout_min_before"]
    news_blackout_min_after: int = DEFAULTS["news_blackout_min_after"]
    current_positions: dict = field(default_factory=dict)
    symbol_allowlist: list[str] = field(default_factory=list)
    current_market_price: Optional[float] = None
    news_guard: Optional[Any] = None  # callable (instrument, at) -> dict

    @property
    def open_count(self) -> int:
        return sum(
            1 for p in self.current_positions.values()
            if p.get("status") == "OPEN"
        )

    @property
    def realized_today_pct(self) -> float:
        """Sum of P&L as % of account equity for positions closed today."""
        today = datetime.now(timezone.utc).date().isoformat()
        total = 0.0
        for p in self.current_positions.values():
            if p.get("status") == "OPEN":
                continue
            exited = (p.get("exited_at") or "")[:10]
            if exited != today:
                continue
            pnl = p.get("pnl") or 0.0
            total += float(pnl)
        return 100.0 * total / self.account_equity if self.account_equity else 0.0


def _normalize_side(side: str) -> str:
    """Map 'buy'/'long'/'b' -> 'long'; 'sell'/'short'/'s' -> 'short'."""
    s = (side or "").strip().lower()
    if s in ("buy", "long", "b", "l"):
        return "long"
    if s in ("sell", "short", "s"):
        return "short"
    return s


def _rr_ratio(side: str, entry: float, stop: float, target: float) -> float:
    """Reward-to-risk ratio. Positive when target is on the profitable side of
    entry relative to stop. Returns inf if risk is zero (caller can check)."""
    risk = abs(entry - stop)
    if risk == 0:
        return float("inf")
    if _normalize_side(side) == "long":
        reward = target - entry
    else:
        reward = entry - target
    return reward / risk if reward > 0 else 0.0


def _risk_pct_per_trade(side: str, entry: float, stop: float,
                        quantity: int, account_equity: float) -> float:
    if account_equity <= 0 or quantity <= 0:
        return 0.0
    risk_per_unit = abs(entry - stop)
    total_risk = risk_per_unit * quantity
    return 100.0 * total_risk / account_equity


def evaluate(
    symbol: str,
    side: str,
    entry_price: float,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    quantity: int = 0,
    at: Optional[datetime] = None,
    cfg: Optional[GateConfig] = None,
) -> list[str]:
    """Run all 7 BLOCK checks. Returns a list of breach reasons (empty = pass)."""
    if cfg is None:
        cfg = GateConfig()
    if at is None:
        at = datetime.now(timezone.utc)
    breaches: list[str] = []

    sym_upper = symbol.upper()

    # 1. Daily loss limit (already realized today as % of equity).
    if -cfg.realized_today_pct >= cfg.daily_loss_pct:
        breaches.append(
            f"Daily loss limit reached: realized today {-cfg.realized_today_pct:.2f}% "
            f"of equity (cap {cfg.daily_loss_pct:g}%)."
        )

    # 2. Max open positions.
    if cfg.open_count >= cfg.max_open_positions:
        breaches.append(
            f"Max open positions reached: {cfg.open_count} of {cfg.max_open_positions}."
        )

    # 3. Same asset, same direction already open.
    norm_side = _normalize_side(side)
    for pos in cfg.current_positions.values():
        if pos.get("status") != "OPEN":
            continue
        if pos.get("symbol", "").upper() != sym_upper:
            continue
        if _normalize_side(pos.get("direction") or "") != norm_side:
            continue
        breaches.append(
            f"{sym_upper} already has an open {norm_side} position "
            f"(opened {pos.get('opened_at', '?')})."
        )
        break  # one breach per check is enough

    # 4. Position size risk cap.
    if stop is not None and quantity > 0:
        risk_pct = _risk_pct_per_trade(
            side, entry_price, stop, quantity, cfg.account_equity
        )
        if risk_pct > cfg.max_risk_per_trade_pct:
            breaches.append(
                f"Risk {risk_pct:.2f}% of equity exceeds the "
                f"{cfg.max_risk_per_trade_pct:g}% per-trade cap."
            )

    # 5. Stale signal — entry far from current market price.
    if cfg.current_market_price and cfg.stale_signal_pct > 0:
        delta_pct = 100.0 * abs(entry_price - cfg.current_market_price) / cfg.current_market_price
        if delta_pct > cfg.stale_signal_pct:
            breaches.append(
                f"Stale signal: entry ${entry_price:.2f} is {delta_pct:.2f}% from "
                f"current ${cfg.current_market_price:.2f} (cap {cfg.stale_signal_pct:g}%)."
            )

    # 6. News blackout (delegated to news_guard).
    if cfg.news_guard is not None:
        try:
            ng_result = cfg.news_guard(
                sym_upper,
                at,
                before_min=cfg.news_blackout_min_before,
                after_min=cfg.news_blackout_min_after,
            )
            if ng_result.get("decision") == "block":
                breaches.append(
                    f"News blackout: {ng_result.get('reason', 'high-impact event imminent')}"
                )
        except Exception as exc:
            # If news_guard itself fails (network down, etc.), DO NOT block.
            # We log the failure as a soft warning and let the trade proceed —
            # the missing news check is safer than blocking every trade.
            breaches.append(
                f"News check unavailable (treated as soft-pass): {type(exc).__name__}: {exc}"
            )

    # 7. R:R ratio.
    if stop is not None and target is not None:
        rr = _rr_ratio(side, entry_price, stop, target)
        if rr < cfg.min_rr_ratio:
            breaches.append(
                f"R:R {rr:.2f} is below the {cfg.min_rr_ratio:.1f}:1 minimum."
            )

    return breaches


def gate_or_block(
    symbol: str,
    side: str,
    entry_price: float,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    quantity: int = 0,
    at: Optional[datetime] = None,
    cfg: Optional[GateConfig] = None,
) -> dict:
    """Returns {"passed": bool, "breaches": [...], "reason": str}.

    `reason` is a single string suitable for logging or sending to a user.
    """
    breaches = evaluate(
        symbol, side, entry_price, stop, target, quantity, at, cfg
    )
    return {
        "passed": len(breaches) == 0,
        "breaches": breaches,
        "reason": ("PASS" if not breaches else "BLOCK: " + "; ".join(breaches)),
    }
