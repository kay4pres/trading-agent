"""Verification suite for the trade_journal adapter.

Bridges positions.json (our source of truth) -> trade_journal.csv (the
trading-loop engine's input format). Tests are offline: they construct
synthetic positions.json in tmp_path and verify the CSV output.
"""

import csv
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# Re-import under test-local env var to redirect both the input and output
os.environ["POSITIONS_FILE"] = ""  # force re-default to a tmp file per test
os.environ["TRADE_JOURNAL_CSV"] = ""

from trading_agent.learning import trade_journal  # noqa: E402


@pytest.fixture
def tmp_paths(tmp_path, monkeypatch):
    """Point trade_journal at a fresh tmp_path for input and output."""
    pos_file = tmp_path / "positions.json"
    journal_csv = tmp_path / "trade_journal.csv"
    monkeypatch.setattr(trade_journal, "POSITIONS_FILE", pos_file)
    monkeypatch.setattr(trade_journal, "JOURNAL_CSV", journal_csv)
    return pos_file, journal_csv


def _seed_positions(pos_file: Path, positions: list[dict]):
    """Write a synthetic positions.json with the given closed positions."""
    state = {
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {},
        "history": [
            {**p, "status": "CLOSED"} for p in positions
        ],
    }
    pos_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def test_derive_r_multiple_long_winner():
    # long, entry 6.00, stop 5.90, exit 6.20 -> 0.20/0.10 = 2.0R
    r = trade_journal.derive_r_multiple(6.00, 5.90, 6.20, "long")
    assert r == pytest.approx(2.0)


def test_derive_r_multiple_long_loser():
    # long, entry 6.00, stop 5.90, exit 5.80 -> -0.20/0.10 = -2.0R
    r = trade_journal.derive_r_multiple(6.00, 5.90, 5.80, "long")
    assert r == pytest.approx(-2.0)


def test_derive_r_multiple_short_winner():
    # short, entry 6.00, stop 6.10, exit 5.80 -> (6.00-5.80)/0.10 = 2.0R
    r = trade_journal.derive_r_multiple(6.00, 6.10, 5.80, "short")
    assert r == pytest.approx(2.0)


def test_derive_r_multiple_short_loser():
    # short, entry 6.00, stop 6.10, exit 6.20 -> (6.00-6.20)/0.10 = -2.0R
    r = trade_journal.derive_r_multiple(6.00, 6.10, 6.20, "short")
    assert r == pytest.approx(-2.0)


def test_derive_r_multiple_zero_risk_returns_none():
    assert trade_journal.derive_r_multiple(6.00, 6.00, 6.10, "long") is None


def test_extend_position_schema_adds_missing_fields():
    pos = {
        "symbol": "PTLE",
        "direction": "long",
        "entry_price": 6.06,
        "stop": 5.95,
        "exit_price": 6.16,
        "exit_reason": "target",
        "pnl": 10.0,
        "opened_at": "2026-07-21T15:30:00Z",
    }
    ext = trade_journal.extend_position_schema(pos)
    assert "rule_compliance" in ext
    assert ext["rule_compliance"] is True  # default
    assert "r_multiple" in ext
    assert ext["r_multiple"] == pytest.approx(0.10 / 0.11, rel=0.01)
    assert ext["session"] in ("premarket", "open", "midday", "close", "unknown")


def test_extend_position_schema_preserves_existing_values():
    pos = {
        "symbol": "MIMI",
        "direction": "long",
        "entry_price": 5.00,
        "stop": 4.95,
        "exit_price": 5.20,
        "rule_compliance": False,  # already set
        "emotional_state": "FOMO",  # already set
        "r_multiple": 4.0,           # already set
        "session": "open",           # already set
    }
    ext = trade_journal.extend_position_schema(pos)
    assert ext["rule_compliance"] is False  # NOT overwritten
    assert ext["emotional_state"] == "FOMO"
    assert ext["r_multiple"] == 4.0
    assert ext["session"] == "open"


def test_export_to_csv_creates_header_on_empty(tmp_paths):
    pos_file, csv_path = tmp_paths
    _seed_positions(pos_file, [
        {"symbol": "PTLE", "direction": "long", "entry_price": 6.06,
         "stop": 5.95, "exit_price": 6.16, "exit_reason": "target",
         "pnl": 10.0, "opened_at": "2026-07-21T15:30:00Z",
         "entry_signal": "First Pullback"},
    ])
    n = trade_journal.export_to_csv(csv_path)
    assert n == 1
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    assert "asset" in content  # header
    assert "PTLE" in content
    assert "First Pullback" in content


def test_export_to_csv_skips_open_positions(tmp_paths):
    pos_file, csv_path = tmp_paths
    state = {
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {
            "PTLE": {
                "symbol": "PTLE", "direction": "long", "status": "OPEN",
                "entry_price": 6.06, "stop": 5.95,
            }
        },
        "history": [
            {"symbol": "MIMI", "direction": "long", "status": "CLOSED",
             "entry_price": 5.00, "stop": 4.95, "exit_price": 5.20,
             "opened_at": "2026-07-21T15:30:00Z"},
        ],
    }
    pos_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    n = trade_journal.export_to_csv(csv_path)
    assert n == 1  # only MIMI (CLOSED), not PTLE (OPEN)
    content = csv_path.read_text(encoding="utf-8")
    assert "MIMI" in content
    assert "PTLE" not in content


def test_load_journal_returns_engine_compatible_dicts(tmp_paths):
    pos_file, csv_path = tmp_paths
    _seed_positions(pos_file, [
        {"symbol": "ILLR", "direction": "long", "entry_price": 4.00,
         "stop": 3.95, "exit_price": 4.20, "opened_at": "2026-07-21T15:30:00Z"},
    ])
    trade_journal.export_to_csv(csv_path)
    rows = trade_journal.load_journal(csv_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["asset"] == "ILLR"
    assert r["direction"] == "long"
    assert r["entry"] == pytest.approx(4.00)
    assert r["stop"] == pytest.approx(3.95)
    assert r["exit"] == pytest.approx(4.20)
    assert isinstance(r["rule_compliance"], bool)
    assert r["rule_compliance"] is True
    assert "r_multiple" in r
    assert r["r_multiple"] == pytest.approx(0.20 / 0.05)


def test_load_journal_handles_empty_file(tmp_paths):
    _pos_file, csv_path = tmp_paths
    assert trade_journal.load_journal(csv_path) == []


def test_closed_positions_returns_only_closed(tmp_paths):
    pos_file, _csv_path = tmp_paths
    state = {
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {},
        "history": [
            {"symbol": "A", "status": "CLOSED", "entry_price": 1.0},
            {"symbol": "B", "status": "OPEN", "entry_price": 2.0},
            {"symbol": "C", "status": "EXITED", "entry_price": 3.0},
            {"symbol": "D", "status": "closed", "entry_price": 4.0},  # lowercase
        ],
    }
    pos_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    closed = trade_journal.closed_positions()
    symbols = {p["symbol"] for p in closed}
    assert symbols == {"A", "C", "D"}  # OPEN excluded, all 3 closed variants included


def test_infer_session_for_premarket_time():
    s = trade_journal.infer_session("2026-07-21T08:30:00-04:00")
    # 08:30 ET = premarket
    assert s == "premarket"


def test_infer_session_for_open_time():
    s = trade_journal.infer_session("2026-07-21T09:45:00-04:00")
    assert s == "open"


def test_infer_session_for_midday_time():
    s = trade_journal.infer_session("2026-07-21T13:30:00-04:00")
    assert s == "midday"


def test_infer_session_for_close_time():
    s = trade_journal.infer_session("2026-07-21T15:45:00-04:00")
    assert s == "close"


def test_infer_session_for_garbage_returns_unknown():
    assert trade_journal.infer_session("not a timestamp") == "unknown"
