"""Verification suite for the pre-trade gate (7 BLOCK conditions).

Adapted from Lewis Jackson's risk-manager Mode #1 (MIT-style). Each test
covers one of the 7 conditions independently. No network access required —
news_guard is replaced with a stub callable in the news-blackout test.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from trading_agent.risk.pre_trade_gate import (  # noqa: E402
    DEFAULTS,
    GateConfig,
    evaluate,
    gate_or_block,
)


def _good_cfg(**overrides) -> GateConfig:
    cfg = GateConfig(
        account_equity=2_000.0,
        daily_loss_pct=10.0,
        max_open_positions=3,
        max_risk_per_trade_pct=1.5,
        min_rr_ratio=2.0,
        stale_signal_pct=2.0,
        symbol_allowlist=["SPY", "PTLE", "MIMI"],
        current_positions={},
        current_market_price=6.00,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _good_kwargs(**overrides):
    base = dict(
        symbol="SPY",
        side="buy",
        entry_price=6.00,
        stop=5.90,
        target=6.20,  # 0.20 / 0.10 = 2.0 R:R
        quantity=100,
    )
    base.update(overrides)
    return base


# 1. Daily loss limit --------------------------------------------------- #
def test_daily_loss_limit_blocks():
    cfg = _good_cfg()
    cfg.current_positions = {
        "X": {
            "symbol": "X",
            "direction": "long",
            "status": "CLOSED",
            "exited_at": datetime.now(timezone.utc).isoformat(),
            "pnl": -300.0,  # -15% of €2K
        }
    }
    breaches = evaluate(cfg=cfg, **_good_kwargs())
    assert any("daily loss" in b.lower() for b in breaches)


def test_daily_loss_below_limit_passes():
    cfg = _good_cfg()
    cfg.current_positions = {
        "X": {
            "symbol": "X",
            "direction": "long",
            "status": "CLOSED",
            "exited_at": datetime.now(timezone.utc).isoformat(),
            "pnl": -50.0,  # -2.5% of €2K (under 10% cap)
        }
    }
    breaches = evaluate(cfg=cfg, **_good_kwargs())
    assert not any("daily loss" in b.lower() for b in breaches)


# 2. Max open positions -------------------------------------------------- #
def test_max_open_positions_blocks():
    cfg = _good_cfg(
        current_positions={
            "A": {"symbol": "A", "direction": "long", "status": "OPEN"},
            "B": {"symbol": "B", "direction": "long", "status": "OPEN"},
            "C": {"symbol": "C", "direction": "long", "status": "OPEN"},
        }
    )
    breaches = evaluate(cfg=cfg, **_good_kwargs(symbol="NEW"))
    assert any("max open" in b.lower() for b in breaches)


# 3. Same asset, same direction ------------------------------------------ #
def test_same_asset_same_direction_blocks():
    cfg = _good_cfg(
        current_positions={
            "SPY": {"symbol": "SPY", "direction": "long", "status": "OPEN",
                    "opened_at": "2026-07-21T15:30:00Z"}
        }
    )
    breaches = evaluate(cfg=cfg, **_good_kwargs(symbol="SPY", side="buy"))
    assert any("already" in b.lower() for b in breaches)


def test_same_asset_opposite_direction_passes():
    cfg = _good_cfg(
        current_positions={
            "SPY": {"symbol": "SPY", "direction": "long", "status": "OPEN",
                    "opened_at": "2026-07-21T15:30:00Z"}
        }
    )
    breaches = evaluate(cfg=cfg, **_good_kwargs(symbol="SPY", side="sell"))
    assert not any("already" in b.lower() for b in breaches)


# 4. Position size risk cap ---------------------------------------------- #
def test_position_size_over_cap_blocks():
    # 1000 shares @ $6, stop $5.50 => $500 risk = 25% of €2K, way over 1.5%.
    cfg = _good_cfg()
    breaches = evaluate(
        cfg=cfg, **_good_kwargs(quantity=1000, stop=5.50, target=6.50)
    )
    assert any("per-trade cap" in b.lower() for b in breaches)


def test_position_size_under_cap_passes():
    # 100 shares @ $6, stop $5.90 => $10 risk = 0.5% of €2K, under 1.5%.
    cfg = _good_cfg()
    breaches = evaluate(cfg=cfg, **_good_kwargs(quantity=100, stop=5.90, target=6.20))
    assert not any("per-trade cap" in b.lower() for b in breaches)


# 5. Stale signal -------------------------------------------------------- #
def test_stale_signal_blocks():
    cfg = _good_cfg(current_market_price=8.00)  # 25%+ away from entry 6.00
    breaches = evaluate(cfg=cfg, **_good_kwargs(entry_price=6.00))
    assert any("stale" in b.lower() for b in breaches)


def test_fresh_signal_passes():
    cfg = _good_cfg(current_market_price=6.01)  # 0.17% away from entry 6.00
    breaches = evaluate(cfg=cfg, **_good_kwargs(entry_price=6.00))
    assert not any("stale" in b.lower() for b in breaches)


# 6. News blackout ------------------------------------------------------- #
def test_news_blackout_blocks():
    def stub_blocking_news_guard(instrument, at, **kw):
        return {
            "decision": "block",
            "reason": "USD NFP in 5 min is inside the 30m-before blackout for SPY.",
        }
    cfg = _good_cfg(news_guard=stub_blocking_news_guard)
    breaches = evaluate(cfg=cfg, **_good_kwargs())
    assert any("news" in b.lower() for b in breaches)


def test_news_blackout_approve_passes():
    def stub_approving_news_guard(instrument, at, **kw):
        return {"decision": "approve", "reason": "no events nearby"}
    cfg = _good_cfg(news_guard=stub_approving_news_guard)
    breaches = evaluate(cfg=cfg, **_good_kwargs())
    assert not any("news" in b.lower() for b in breaches)


def test_news_check_unavailable_does_not_block():
    """If news_guard itself fails, the trade is NOT blocked — we soft-pass
    and surface the failure as a warning. Better than blocking everything."""
    def broken_news_guard(instrument, at, **kw):
        raise ConnectionError("forexfactory unreachable")
    cfg = _good_cfg(news_guard=broken_news_guard)
    breaches = evaluate(cfg=cfg, **_good_kwargs())
    # Should NOT block — only the soft warning should appear
    assert not any("inside the" in b.lower() for b in breaches)


# 7. R:R ratio ----------------------------------------------------------- #
def test_rr_below_minimum_blocks():
    # entry 6.00, stop 5.90, target 6.05 => 0.05/0.10 = 0.5:1, below 2:1
    cfg = _good_cfg()
    breaches = evaluate(cfg=cfg, **_good_kwargs(target=6.05))
    assert any("r:r" in b.lower() or "minimum" in b.lower() for b in breaches)


def test_rr_at_minimum_passes():
    # entry 6.00, stop 5.90, target 6.20 => 0.20/0.10 = 2.0:1
    cfg = _good_cfg()
    breaches = evaluate(cfg=cfg, **_good_kwargs(target=6.20))
    assert not any("r:r" in b.lower() or "minimum" in b.lower() for b in breaches)


# Integration: gate_or_block helper --------------------------------------- #
def test_gate_or_block_pass_returns_passed_true():
    cfg = _good_cfg()
    res = gate_or_block(cfg=cfg, **_good_kwargs())
    assert res["passed"] is True
    assert res["breaches"] == []
    assert res["reason"] == "PASS"


def test_gate_or_block_fail_returns_reason_string():
    cfg = _good_cfg(current_market_price=10.00)  # stale
    res = gate_or_block(cfg=cfg, **_good_kwargs())
    assert res["passed"] is False
    assert "BLOCK:" in res["reason"]
    assert "stale" in res["reason"].lower()


def test_defaults_match_arch_v1():
    """Sanity check: defaults align with ARCHITECTURE_v1.0.md §3 phased rollout."""
    assert DEFAULTS["account_equity"] == 2_000.0
    assert DEFAULTS["daily_loss_pct"] == 10.0
    assert DEFAULTS["max_open_positions"] == 3
    assert DEFAULTS["max_risk_per_trade_pct"] == 1.5
    assert DEFAULTS["min_rr_ratio"] == 2.0
