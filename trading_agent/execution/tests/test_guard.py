"""Verification suite for the execution-safety gate (guard.py).

The four required invariants, each asserting a hard guarantee of the gate
(not a performance band):
  a) a live order with no ALLOW_TRADING routes to paper,
  b) an order breaching a risk limit is blocked,
  c) a live order without the correct typed confirmation is rejected,
  d) a fully-valid confirmed live order passes the gate to a stub adapter.

Adapted from Lewis Jackson's execution-safety test suite (MIT-style).

No live order is ever transmitted: the "live" adapter is a local simulating
stub and tests control ALLOW_TRADING via monkeypatch, never the real shell.
"""

import sys
from pathlib import Path

import pytest

# Path setup so the test can import the package without installing it.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from trading_agent.execution.guard import (  # noqa: E402
    IBKRLiveAdapter,
    Order,
    PaperAdapter,
    RiskProfile,
    StubLiveAdapter,
    guard_order,
)


def _profile() -> RiskProfile:
    return RiskProfile(
        account_equity=2_000.0,
        max_risk_per_trade_pct=1.5,  # max €30 at risk on €2K
        max_daily_loss_pct=10.0,     # ARCH v1.0: 10% daily loss circuit breaker
        current_open_risk_pct=0.0,
        max_position_notional=800.0,  # ¼ size start (per multi-position 1-3 design)
        min_stop_atr_mult=1.0,
        symbol_allowlist=["SPY", "PTLE", "MIMI", "ILLR", "AAPL", "TSLA"],
    )


def _good_order() -> Order:
    # 100 SPY @ 6, stop 5.90 => €10 risk = 0.5% of equity. Notional €600.
    # Stop 0.10 away, ATR 0.08 => 1.25x ATR. Passes every limit.
    return Order(
        symbol="SPY",
        side="sell",
        qty=100,
        order_type="market",
        price=6.00,
        stop=5.90,
        atr=0.08,
    )


@pytest.fixture
def audit(tmp_path) -> Path:
    return tmp_path / "audit.jsonl"


# (a) ----------------------------------------------------------------------- #
def test_live_without_allow_trading_routes_to_paper(monkeypatch, audit):
    monkeypatch.delenv("ALLOW_TRADING", raising=False)
    res = guard_order(
        _good_order(),
        _profile(),
        live=True,
        confirmation="CONFIRM SELL 100 SPY @ market",
        audit_path=audit,
    )
    assert res["routed"] == "paper", res
    assert "ALLOW_TRADING" in res["reason"]
    assert audit.exists()


# (b) ----------------------------------------------------------------------- #
def test_risk_limit_breach_is_blocked(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    # Stop 0.60 away on 100 qty => €60 risk = 3% of equity, over the 1.5% cap.
    bad = Order(
        symbol="SPY",
        side="sell",
        qty=100,
        order_type="market",
        price=6.00,
        stop=5.40,
        atr=0.08,
    )
    res = guard_order(
        bad,
        _profile(),
        live=True,
        confirmation=bad.confirmation_token(),
        audit_path=audit,
    )
    assert res["routed"] == "blocked", res
    assert any("per-trade cap" in b for b in res["breaches"]), res["breaches"]


def test_missing_stop_is_blocked(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    bad = Order(symbol="SPY", side="buy", qty=10, price=6.00, stop=None, atr=0.08)
    res = guard_order(bad, _profile(), live=False, audit_path=audit)
    assert res["routed"] == "blocked"
    assert any("stop" in b.lower() for b in res["breaches"])


def test_symbol_not_on_allowlist_is_blocked(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    bad = Order(symbol="GME", side="buy", qty=10, price=6.00, stop=5.95, atr=0.08)
    res = guard_order(bad, _profile(), live=False, audit_path=audit)
    assert res["routed"] == "blocked"
    assert any("allowlist" in b.lower() for b in res["breaches"])


def test_notional_over_cap_is_blocked(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    # 1000 shares @ 100 = €100,000 notional, well over the €800 cap.
    bad = Order(symbol="SPY", side="buy", qty=1000, price=100.0, stop=99.0, atr=0.5)
    res = guard_order(bad, _profile(), live=False, audit_path=audit)
    assert res["routed"] == "blocked"
    assert any("notional" in b.lower() for b in res["breaches"])


def test_stop_too_tight_vs_atr_is_blocked(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    # Stop 0.02 away, ATR 0.08 => 0.25x ATR, below 1.0x minimum.
    bad = Order(symbol="SPY", side="buy", qty=100, price=6.00, stop=5.98, atr=0.08)
    res = guard_order(bad, _profile(), live=False, audit_path=audit)
    assert res["routed"] == "blocked"
    assert any("atr" in b.lower() for b in res["breaches"])


# (c) ----------------------------------------------------------------------- #
def test_live_with_wrong_confirmation_is_rejected(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    res = guard_order(
        _good_order(),
        _profile(),
        live=True,
        confirmation="yes do it",
        audit_path=audit,
    )
    assert res["routed"] == "blocked", res
    assert res["expected_confirmation"] == "CONFIRM SELL 100 SPY @ market"


def test_live_with_no_confirmation_is_rejected(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    res = guard_order(
        _good_order(), _profile(), live=True, confirmation=None, audit_path=audit
    )
    assert res["routed"] == "blocked"


# (d) ----------------------------------------------------------------------- #
def test_valid_confirmed_live_order_passes_to_stub_adapter(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    res = guard_order(
        _good_order(),
        _profile(),
        live=True,
        confirmation="CONFIRM SELL 100 SPY @ market",
        live_adapter=StubLiveAdapter(),
        audit_path=audit,
    )
    assert res["routed"] == "live", res
    assert res["fill"]["broker"] == "stub-live"
    assert res["fill"]["ok"] is True


# extra invariants ---------------------------------------------------------- #
def test_default_is_paper(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    res = guard_order(
        _good_order(), _profile(), audit_path=audit
    )  # live defaults False
    assert res["routed"] == "paper"


def test_every_decision_is_audited(monkeypatch, audit):
    monkeypatch.setenv("ALLOW_TRADING", "1")
    guard_order(_good_order(), _profile(), live=False, audit_path=audit)
    guard_order(
        _good_order(),
        _profile(),
        live=True,
        confirmation="CONFIRM SELL 100 SPY @ market",
        audit_path=audit,
    )
    lines = [l for l in audit.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


def test_ibkr_live_adapter_falls_back_gracefully_on_relay_offline(audit):
    """IBKR adapter with no relay running returns ok=False, doesn't crash."""
    monkey = pytest.MonkeyPatch()
    monkey.setenv("ALLOW_TRADING", "1")
    adapter = IBKRLiveAdapter(relay_url="http://127.0.0.1:1/nope", timeout=0.5)
    res = guard_order(
        _good_order(),
        _profile(),
        live=True,
        confirmation="CONFIRM SELL 100 SPY @ market",
        live_adapter=adapter,
        audit_path=audit,
    )
    # Even if the adapter fails, the gate still records an audit entry.
    assert res["routed"] == "live", res
    assert res["fill"]["broker"] == "ibkr"
    assert res["fill"]["ok"] is False
    monkey.undo()
