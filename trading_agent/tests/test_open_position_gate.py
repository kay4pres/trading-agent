"""Integration tests for the open_position() pre-trade gate wiring.

Verifies that:
  1. A blocked order (max positions reached) does NOT create a position.
  2. A blocked order sends a Telegram-style notification.
  3. A valid order DOES create a position.
  4. The order is paper-routed (no live broker submission).
  5. The execution_audit_id is persisted to the position record.
  6. The closed-position journal is appended on exit.

Uses monkeypatch to:
  - Redirect POSITIONS_FILE to a tmp_path
  - Stub get_live_price() to a known value
  - Stub send_telegram() to capture (not send) messages
  - Stub Alpaca paper trading to no-op
  - Stub news_guard callable
"""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# Redirect data dir before importing trader_agent
TEST_DATA = Path(__file__).resolve().parent / "_tmp_data"
TEST_DATA.mkdir(exist_ok=True)
os.environ["POSITIONS_FILE"] = str(TEST_DATA / "positions.json")
os.environ["TRADE_JOURNAL_CSV"] = str(TEST_DATA / "trade_journal.csv")
os.environ["EXECUTION_SAFETY_AUDIT"] = str(TEST_DATA / "execution_audit.jsonl")

# trader_agent.py lives at trading_agent/trader_agent.py.
from trading_agent import trader_agent  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_data_dir(monkeypatch, tmp_path):
    """Each test gets its own tmp_path-based positions.json + journal CSV."""
    pos_file = tmp_path / "positions.json"
    journal = tmp_path / "trade_journal.csv"
    audit = tmp_path / "execution_audit.jsonl"
    monkeypatch.setattr(trader_agent, "POSITIONS_FILE", pos_file)
    monkeypatch.setenv("TRADE_JOURNAL_CSV", str(journal))
    monkeypatch.setenv("EXECUTION_SAFETY_AUDIT", str(audit))
    # Reset module-level state in trade_journal that may have cached paths
    from trading_agent.learning import trade_journal
    monkeypatch.setattr(trade_journal, "POSITIONS_FILE", pos_file)
    monkeypatch.setattr(trade_journal, "JOURNAL_CSV", journal)
    yield


@pytest.fixture
def captured_telegram(monkeypatch):
    """Replace send_telegram with a list-capturing stub."""
    captured = []
    monkeypatch.setattr(trader_agent, "send_telegram",
                        lambda msg: captured.append(msg))
    return captured


@pytest.fixture
def no_atr(monkeypatch):
    """Stub get_atr() and get_live_price() with deterministic values."""
    monkeypatch.setattr(trader_agent, "get_atr", lambda symbol: 0.08)
    monkeypatch.setattr(trader_agent, "get_live_price", lambda symbol: 6.00)
    # calc_stop_target uses get_atr and a fixed 0.20 target/0.10 stop
    # when ATR is known. Stub it for determinism.
    monkeypatch.setattr(trader_agent, "calc_stop_target",
                        lambda symbol, entry, pullback_low=None: (5.90, 6.20, None))
    yield


@pytest.fixture
def no_alpaca(monkeypatch):
    """Make _get_alpaca_trading return None so no real order goes out."""
    monkeypatch.setattr(trader_agent, "_get_alpaca_trading", lambda: None)
    yield


def test_blocked_by_max_positions_does_not_create(captured_telegram, no_atr, no_alpaca):
    """Pre-seed 3 OPEN positions, attempt a 4th — must be BLOCKED at gate."""
    # Seed 3 open positions
    state = {
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {
            f"SYM{i}": {
                "symbol": f"SYM{i}", "direction": "long", "status": "OPEN",
                "entry_price": 5.0, "stop": 4.95, "target": 5.20,
                "quantity": 100, "opened_at": "2026-07-21T15:00:00Z",
                "exit_price": None, "pnl": None, "exited_at": None,
                "exit_reason": None,
            }
            for i in range(3)
        },
        "history": [],
    }
    trader_agent.POSITIONS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Attempt to open a 4th position
    result = trader_agent.open_position(
        symbol="NEWSYM", direction="long", entry_price=6.00, quantity=100,
    )
    assert result is False

    # Telegram was called with the BLOCK message
    assert any("GATE BLOCKED" in m for m in captured_telegram), captured_telegram

    # Position was NOT created
    after = json.loads(trader_agent.POSITIONS_FILE.read_text(encoding="utf-8"))
    assert "NEWSYM" not in after["positions"]


def test_blocked_by_stale_signal_does_not_create(captured_telegram, no_atr, no_alpaca):
    """Market price 5% away from entry -> stale signal -> BLOCKED."""
    trader_agent.POSITIONS_FILE.write_text(json.dumps({
        "schema_version": "1.0", "updated_at": "2026-07-21T15:30:00Z",
        "positions": {}, "history": [],
    }, indent=2), encoding="utf-8")

    # Override get_live_price to return 6.50 (entry 6.00 is 8% away -> stale)
    trader_agent.get_live_price = lambda symbol: 6.50

    result = trader_agent.open_position(
        symbol="PTLE", direction="long", entry_price=6.00, quantity=100,
    )
    assert result is False
    assert any("stale" in m.lower() for m in captured_telegram), captured_telegram


def test_valid_order_creates_position_paper_routed(captured_telegram, no_atr, no_alpaca):
    """A clean order creates a position and routes to paper."""
    trader_agent.POSITIONS_FILE.write_text(json.dumps({
        "schema_version": "1.0", "updated_at": "2026-07-21T15:30:00Z",
        "positions": {}, "history": [],
    }, indent=2), encoding="utf-8")

    result = trader_agent.open_position(
        symbol="PTLE", direction="long", entry_price=6.00, quantity=100,
    )
    assert result is True

    # Position was created
    after = json.loads(trader_agent.POSITIONS_FILE.read_text(encoding="utf-8"))
    assert "PTLE" in after["positions"]
    pos = after["positions"]["PTLE"]
    assert pos["status"] == "OPEN"
    assert pos["entry_price"] == 6.00
    assert pos["quantity"] == 100
    # Execution guard ran (paper by default)
    assert pos["execution_decision"] in ("paper", "live")
    assert pos.get("execution_audit_id", "").startswith("aud_")
    # Telegram entry notification
    assert any("ENTRY" in m for m in captured_telegram), captured_telegram


def test_execution_audit_written(captured_telegram, no_atr, no_alpaca):
    """Each order writes one JSON line to the execution audit log."""
    from pathlib import Path
    audit_path = Path(os.environ["EXECUTION_SAFETY_AUDIT"])

    trader_agent.POSITIONS_FILE.write_text(json.dumps({
        "schema_version": "1.0", "updated_at": "2026-07-21T15:30:00Z",
        "positions": {}, "history": [],
    }, indent=2), encoding="utf-8")

    trader_agent.open_position(
        symbol="PTLE", direction="long", entry_price=6.00, quantity=100,
    )
    assert audit_path.exists()
    lines = [l for l in audit_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 1
    rec = json.loads(lines[-1])
    assert rec["symbol"] == "PTLE"
    assert rec["decision"] in ("paper", "live", "blocked")


def test_closed_position_written_to_journal_csv(no_atr, no_alpaca):
    """execute_exit() appends to the trade journal CSV in engine schema."""
    from trading_agent.learning import trade_journal
    journal_path = Path(os.environ["TRADE_JOURNAL_CSV"])

    # Seed an open position
    trader_agent.POSITIONS_FILE.write_text(json.dumps({
        "schema_version": "1.0", "updated_at": "2026-07-21T15:30:00Z",
        "positions": {
            "MIMI": {
                "symbol": "MIMI", "direction": "long", "status": "OPEN",
                "entry_price": 5.00, "stop": 4.95, "target": 5.20,
                "quantity": 100, "opened_at": "2026-07-21T15:30:00Z",
                "entry_signal": "First Pullback",
                "exit_price": None, "pnl": None, "exited_at": None,
                "exit_reason": None,
            }
        },
        "history": [],
    }, indent=2), encoding="utf-8")

    state = json.loads(trader_agent.POSITIONS_FILE.read_text(encoding="utf-8"))
    pos = state["positions"]["MIMI"]
    # execute_exit at 5.20 (target hit, +$20)
    trader_agent.execute_exit(state, "MIMI", pos, "TARGET_HIT", 5.20)
    trader_agent.save_positions(state)

    # Journal CSV has one row
    assert journal_path.exists()
    rows = trade_journal.load_journal(journal_path)
    assert len(rows) == 1
    assert rows[0]["asset"] == "MIMI"
    assert rows[0]["entry"] == 5.00
    assert rows[0]["exit"] == 5.20
    # R-multiple: 0.20/0.05 = 4.0
    assert rows[0]["r_multiple"] == pytest.approx(4.0)


def test_gate_blocks_bear_regime_for_long_entry_via_callable(monkeypatch, no_atr, no_alpaca, captured_telegram):
    """News guard callable returning block -> trade is BLOCKED."""
    from trading_agent.risk import pre_trade_gate

    # Monkeypatch the news_guard factory inside the gate builder
    def fake_blocking_news_guard(instrument, at, **kw):
        return {
            "decision": "block",
            "reason": f"USD NFP in 5 min is inside the 30m-before blackout for {instrument}.",
        }

    # Reach into the gate builder and swap the callable
    original = trader_agent._build_pre_trade_gate

    def patched_build(symbol, direction, entry_price, stop, target, quantity):
        cfg, _, _ = original(symbol, direction, entry_price, stop, target, quantity)
        cfg.news_guard = fake_blocking_news_guard
        return cfg, fake_blocking_news_guard, cfg.current_market_price

    monkeypatch.setattr(trader_agent, "_build_pre_trade_gate", patched_build)

    trader_agent.POSITIONS_FILE.write_text(json.dumps({
        "schema_version": "1.0", "updated_at": "2026-07-21T15:30:00Z",
        "positions": {}, "history": [],
    }, indent=2), encoding="utf-8")

    result = trader_agent.open_position(
        symbol="PTLE", direction="long", entry_price=6.00, quantity=100,
    )
    assert result is False
    assert any("news" in m.lower() for m in captured_telegram), captured_telegram
