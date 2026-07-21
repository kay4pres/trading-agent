"""Execution safety gate.

Adapted from Lewis Jackson's execution-safety skill (MIT-style) for the
trading-agent project. The 4-step pipeline is preserved verbatim:

    1. Mode check    — live needs ALLOW_TRADING=1 in env AND live=True on the
                       call, else routes to paper. Default = paper.
    2. Hard risk limits — any breach blocks the order (paper or live).
    3. Typed confirmation — live orders need exact token, e.g.
                            "CONFIRM SELL 100 SPY @ market". Never auto-confirmed.
    4. Audit log     — every decision (approved / paper / blocked) is appended
                       as one JSON line to the audit log with audit_id + ts.

The two-lock pattern (env flag + per-call) is industry-proven (tastytrade's
ALLOW_TRADING=1 + per-order confirm:true) and is what makes the gate
friction-by-design: paper is the default because the cost of an accidental
live order is asymmetric.

Broker adapters: PaperAdapter (default sink, no network) and StubLiveAdapter
(simulated live) are drop-in from upstream. IBKRLiveAdapter is new — it
calls our local IBGW relay over HTTP and is the path for real money.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

# Where the immutable decision log lives. Override with EXECUTION_SAFETY_AUDIT.
AUDIT_PATH = Path(
    os.environ.get(
        "EXECUTION_SAFETY_AUDIT",
        str(Path(__file__).resolve().parent.parent.parent / "data" / "execution_audit.jsonl"),
    )
)

# The one environment flag that arms live trading. Hard on purpose: a human has
# to set it in the shell; the agent cannot flip it mid-run.
ALLOW_TRADING_ENV = "ALLOW_TRADING"


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class RiskProfile:
    """Hard limits the gate enforces. Breach any one of these and the order is
    blocked outright — these are not suggestions and the agent cannot soften
    them. All percentages are of account equity unless noted.

    Defaults are sized for a small (€2K) EU day-trading account per
    ARCHITECTURE_v1.0.md §3 phased rollout. Adjust as the account grows.
    """

    account_equity: float = 2_000.0
    # Reject if this order risks more than this fraction of equity.
    max_risk_per_trade_pct: float = 1.5
    # Reject if projected total open risk would exceed the day's stop.
    max_daily_loss_pct: float = 10.0  # ARCH v1.0: 10% daily loss circuit breaker
    # Risk currently live across open positions (caller supplies the running
    # tally; the gate adds this order's risk to it).
    current_open_risk_pct: float = 0.0
    # Reject if notional (price * qty) exceeds this cash cap.
    max_position_notional: float = 800.0  # ¼ size start (per multi-position 1-3 design)
    # Every order must carry a stop, and it must be at least this many ATRs away.
    min_stop_atr_mult: float = 1.0
    # Only symbols on this list may trade. Empty list = nothing allowed (fail
    # closed), which is the safe default if a profile is misconfigured.
    symbol_allowlist: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str | Path) -> "RiskProfile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


@dataclass
class Order:
    """A proposed order. `risk_amount` is the cash at risk if the stop is hit;
    if omitted it is derived from |price - stop| * qty."""

    symbol: str
    side: str  # "buy" | "sell"
    qty: float
    order_type: str = "market"  # "market" | "limit"
    price: float = 0.0  # reference / limit price
    stop: Optional[float] = None  # protective stop price
    atr: Optional[float] = None  # current ATR for the stop-distance check
    risk_amount: Optional[float] = None  # cash at risk; derived if None

    def notional(self) -> float:
        return abs(self.price * self.qty)

    def derived_risk_amount(self) -> Optional[float]:
        if self.risk_amount is not None:
            return self.risk_amount
        if self.stop is not None and self.price:
            return abs(self.price - self.stop) * self.qty
        return None

    def confirmation_token(self) -> str:
        """The exact phrase a human must echo back to authorise a live order.
        Deterministic so the caller can compute and display it, then require it
        verbatim. Example: 'CONFIRM SELL 100 SPY @ market'."""
        qty = int(self.qty) if float(self.qty).is_integer() else self.qty
        venue = "market" if self.order_type == "market" else f"limit {self.price:g}"
        return f"CONFIRM {self.side.upper()} {qty} {self.symbol.upper()} @ {venue}"


# --------------------------------------------------------------------------- #
# Broker adapter interface
# --------------------------------------------------------------------------- #
class BrokerAdapter:
    """Broker-agnostic seam. Real adapters wrap our IBGW relay (HTTP) or
    alpaca-py / ccxt and are imported behind try/except so this module has
    zero hard broker deps. The gate never calls place() until an order has
    passed every check.
    """

    name = "base"

    def place(self, order: Order, *, live: bool) -> dict[str, Any]:
        raise NotImplementedError


class PaperAdapter(BrokerAdapter):
    """Default sink. Simulates a fill locally; touches nothing external."""

    name = "paper"

    def place(self, order: Order, *, live: bool) -> dict[str, Any]:
        return {
            "ok": True,
            "broker": self.name,
            "order_id": f"paper_{uuid.uuid4().hex[:12]}",
            "status": "filled",
            "message": "Paper order filled (simulated).",
        }


class StubLiveAdapter(BrokerAdapter):
    """Stand-in for a real broker. Proves the gate hands a cleared order to a
    live adapter — but still simulates, so tests never transmit. Swap this for
    IBKRLiveAdapter (real) or alpaca-py / ccxt to trade actual capital."""

    name = "stub-live"

    def place(self, order: Order, *, live: bool) -> dict[str, Any]:
        return {
            "ok": True,
            "broker": self.name,
            "order_id": f"live_{uuid.uuid4().hex[:12]}",
            "status": "accepted",
            "message": (
                "Live order routed to stub adapter (simulated — connect IBKRLiveAdapter "
                "or a real broker SDK to trade actual capital)."
            ),
        }


class IBKRLiveAdapter(BrokerAdapter):
    """Real broker adapter. Calls our local IBGW relay (ibgw_relay.py) over HTTP
    to place the order on the IBKR paper or live account.

    The relay URL defaults to http://127.0.0.1:5000/order, override via
    IBGW_RELAY_URL env var. Returns a dict with broker=ibkr, order_id, status,
    and message. Errors are caught and returned as ok=False so the gate can
    audit them."""

    name = "ibkr"

    def __init__(self, relay_url: Optional[str] = None, timeout: float = 5.0):
        self.relay_url = relay_url or os.environ.get(
            "IBGW_RELAY_URL", "http://127.0.0.1:5000/order"
        )
        self.timeout = timeout

    def place(self, order: Order, *, live: bool) -> dict[str, Any]:
        payload = {
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "type": order.order_type,
            "price": order.price,
            "stop": order.stop,
            "live": live,
        }
        try:
            import urllib.request
            req = urllib.request.Request(
                self.relay_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                result.setdefault("broker", self.name)
                result.setdefault("ok", True)
                return result
        except Exception as e:
            return {
                "ok": False,
                "broker": self.name,
                "order_id": None,
                "status": "error",
                "message": f"IBGW relay error: {type(e).__name__}: {e}",
            }


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
def audit_log_path() -> Path:
    """Resolve the audit log path (env override or default)."""
    return Path(
        os.environ.get(
            "EXECUTION_SAFETY_AUDIT", str(AUDIT_PATH)
        )
    )


def _write_audit(record: dict[str, Any], audit_path: Path) -> str:
    audit_id = f"aud_{uuid.uuid4().hex[:12]}"
    record = {"audit_id": audit_id, "ts": time.time(), **record}
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return audit_id


# --------------------------------------------------------------------------- #
# Hard risk limits
# --------------------------------------------------------------------------- #
def check_risk_limits(order: Order, profile: RiskProfile) -> list[str]:
    """Return a list of breach reasons. Empty list = passes every hard limit."""
    breaches: list[str] = []

    # 1. Symbol allowlist (fail closed on empty list).
    if order.symbol.upper() not in {s.upper() for s in profile.symbol_allowlist}:
        breaches.append(
            f"{order.symbol} is not on the allowlist {profile.symbol_allowlist}."
        )

    # 2. Stop must be attached.
    risk_amt = order.derived_risk_amount()
    if order.stop is None:
        breaches.append("No protective stop attached.")
    elif order.atr is not None and order.price:
        # 3. Stop must be at least min_stop_atr_mult ATRs from entry.
        stop_dist = abs(order.price - order.stop)
        min_dist = profile.min_stop_atr_mult * order.atr
        if stop_dist < min_dist:
            breaches.append(
                f"Stop is {stop_dist:.4g} away ({stop_dist / order.atr:.2f}x ATR); "
                f"minimum is {profile.min_stop_atr_mult:g}x ATR ({min_dist:.4g})."
            )

    # 4. Risk-per-trade cap.
    if risk_amt is not None and profile.account_equity > 0:
        risk_pct = 100.0 * risk_amt / profile.account_equity
        if risk_pct > profile.max_risk_per_trade_pct:
            breaches.append(
                f"Risk {risk_pct:.2f}% of equity exceeds the "
                f"{profile.max_risk_per_trade_pct:g}% per-trade cap."
            )
        # 5. Projected open risk vs daily stop.
        projected = profile.current_open_risk_pct + risk_pct
        if projected > profile.max_daily_loss_pct:
            breaches.append(
                f"Projected open risk {projected:.2f}% exceeds the "
                f"{profile.max_daily_loss_pct:g}% daily stop."
            )

    # 6. Notional position cap.
    if order.notional() > profile.max_position_notional:
        breaches.append(
            f"Notional {order.notional():.2f} exceeds the max position "
            f"{profile.max_position_notional:.2f}."
        )

    return breaches


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #
def guard_order(
    order: Order,
    profile: RiskProfile,
    *,
    live: bool = False,
    confirmation: Optional[str] = None,
    paper_adapter: Optional[BrokerAdapter] = None,
    live_adapter: Optional[BrokerAdapter] = None,
    audit_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Run every order through the safety pipeline and return the decision.

    Pipeline (in order; first failure wins):
      1. Mode check    — live needs ALLOW_TRADING=1 in the env AND live=True,
                         else the order is routed to paper. Default = paper.
      2. Risk limits   — any hard-limit breach blocks the order (paper too:
                         a bad order is bad whether or not capital is real).
      3. Confirmation  — a live order needs the exact typed token; mismatch
                         rejects. Never auto-confirmed.
      4. Place         — cleared order goes to the chosen adapter.

    Returns {"routed": "live"|"paper"|"blocked", "reason", "audit_id", ...}.
    """
    paper_adapter = paper_adapter or PaperAdapter()
    live_adapter = live_adapter or StubLiveAdapter()
    audit_path = audit_path or audit_log_path()

    env_armed = os.environ.get(ALLOW_TRADING_ENV) == "1"
    wants_live = bool(live)
    # Live only when BOTH locks are open. Otherwise we fall back to paper.
    live_mode = wants_live and env_armed

    base = {
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "order_type": order.order_type,
        "requested_live": wants_live,
        "env_armed": env_armed,
        "live_mode": live_mode,
    }

    def finish(
        routed: str, reason: str, extra: Optional[dict] = None
    ) -> dict[str, Any]:
        record = {"decision": routed, "reason": reason, **base, **(extra or {})}
        audit_id = _write_audit(record, audit_path)
        return {
            "routed": routed,
            "reason": reason,
            "audit_id": audit_id,
            **(extra or {}),
        }

    # 2. Hard risk limits — checked before anything is placed, paper or live.
    breaches = check_risk_limits(order, profile)
    if breaches:
        return finish("blocked", "; ".join(breaches), {"breaches": breaches})

    # 1 + 3. Mode + typed confirmation for the live path.
    if live_mode:
        expected = order.confirmation_token()
        if confirmation != expected:
            return finish(
                "blocked",
                f"Live order requires exact confirmation '{expected}'. "
                f"Got {confirmation!r}.",
                {"expected_confirmation": expected},
            )
        fill = live_adapter.place(order, live=True)
        return finish("live", fill.get("message", "Live order routed."), {"fill": fill})

    # Default path: paper. Explain why if the caller asked for live.
    if wants_live and not env_armed:
        reason = (
            f"Live requested but {ALLOW_TRADING_ENV}=1 is not set — "
            "routed to paper. Set it in the shell to arm live trading."
        )
    else:
        reason = "Routed to paper (default mode)."
    fill = paper_adapter.place(order, live=False)
    return finish("paper", reason, {"fill": fill})


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Safety gate between an AI agent and a real broker.",
        formatter_class=argparse.ArgumentDefaultsFormatter,
    )
    p.add_argument("--symbol", required=True)
    p.add_argument("--side", required=True, choices=["buy", "sell"])
    p.add_argument("--qty", required=True, type=float)
    p.add_argument(
        "--type", dest="order_type", default="market", choices=["market", "limit"]
    )
    p.add_argument("--price", type=float, default=0.0)
    p.add_argument("--stop", type=float, default=None)
    p.add_argument("--atr", type=float, default=None)
    p.add_argument("--risk-amount", type=float, default=None)
    p.add_argument(
        "--profile",
        default=None,
        help="Path to a RiskProfile JSON file. Defaults applied if omitted.",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Request the live path (still needs ALLOW_TRADING=1).",
    )
    p.add_argument(
        "--confirm",
        default=None,
        help="Exact typed confirmation token for a live order.",
    )
    p.add_argument(
        "--show-token",
        action="store_true",
        help="Print the required confirmation token and exit.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    order = Order(
        symbol=args.symbol,
        side=args.side,
        qty=args.qty,
        order_type=args.order_type,
        price=args.price,
        stop=args.stop,
        atr=args.atr,
        risk_amount=args.risk_amount,
    )
    if args.show_token:
        print(order.confirmation_token())
        return 0

    profile = RiskProfile.from_json(args.profile) if args.profile else RiskProfile()
    result = guard_order(order, profile, live=args.live, confirmation=args.confirm)
    print(json.dumps(result, indent=2))
    return 0 if result["routed"] != "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
