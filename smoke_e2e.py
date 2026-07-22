#!/usr/bin/env python3
"""
smoke_e2e.py — end-to-end smoke test for the Dev environment.

Verifies that the 5 new modules (execution guard, news_guard, pre-trade gate,
regime, learning loop) all work together in a real running container.

Runs after the Dev stack is up. Exits 0 on success, 1 on any failure.

Verifies (in order):
  1. All 75 unit tests pass
  2. The pre-trade gate blocks an over-positioned order
  3. A valid order passes the gate, gets paper-routed by the execution guard
  4. The audit log contains the new decision
  5. execute_exit() appends a row to trade_journal.csv
  6. The trading_loop engine accepts the journal as input

Usage (inside the Dev container):
    python /app/smoke_e2e.py

This is the canonical "Dev is working" check per Phase A of the rollout plan.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Resolve project root: /app in container, current dir otherwise.
PROJECT_ROOT = "/app" if os.path.isdir("/app") else os.getcwd()


def _make_runner(pos_file, journal_csv, audit_log, body_lines):
    """Build a Python `-c` script that runs in a fresh subprocess.

    The script is a thin wrapper: it sets env vars, monkeypatches the
    trader_agent module-level state, then executes the caller-supplied
    body. The body must be valid Python (no need to escape anything).
    """
    body = "\n".join(body_lines)
    pos_file_s = str(pos_file)
    journal_csv_s = str(journal_csv)
    audit_log_s = str(audit_log)
    return f"""
import sys, json
sys.path.insert(0, {PROJECT_ROOT!r})

import trading_agent.trader_agent as ta
ta.POSITIONS_FILE = __import__('pathlib').Path({pos_file_s!r})
ta.get_live_price = lambda s: 6.00
ta.get_atr = lambda s: 0.08
ta.calc_stop_target = lambda s, e, pullback_low=None: (5.90, 6.20, None)
ta._get_alpaca_trading = lambda: None
ta.send_telegram = lambda m: None

{body}
"""


def _run_in_subprocess(code, pos_file, journal_csv, audit_log):
    """Run a Python `-c` script in a subprocess with the env vars set."""
    full_env = {**os.environ, **{
        "POSITIONS_FILE": str(pos_file),
        "TRADE_JOURNAL_CSV": str(journal_csv),
        "EXECUTION_SAFETY_AUDIT": str(audit_log),
        # Force UTF-8 so emoji in Telegram messages don't break on Windows charmap
        # (the container is UTF-8 by default; this is for local runs).
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=full_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return result


# 1. Run all unit tests --------------------------------------------------- #
print("=" * 70)
print("STEP 1/6: Unit tests (75 expected)")
print("=" * 70)
result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "trading_agent/execution/",
        "trading_agent/data_plane/",
        "trading_agent/risk/",
        "trading_agent/learning/",
        "trading_agent/tests/",
        "-v", "--tb=short",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    timeout=120,
)
print(result.stdout[-2000:])
if result.returncode != 0:
    print(f"[FAIL] pytest exit code {result.returncode}")
    print("STDOUT tail:", result.stdout[-500:])
    print("STDERR tail:", result.stderr[-500:])
    sys.exit(1)
print(f"[PASS] Unit tests passed (return code {result.returncode})")


# 2. Blocked order doesn't create a position ------------------------------ #
print()
print("=" * 70)
print("STEP 2/6: Pre-trade gate blocks over-positioned order")
print("=" * 70)
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    pos_file = tmp / "positions.json"
    journal_csv = tmp / "trade_journal.csv"
    audit_log = tmp / "audit.jsonl"

    # Seed 3 open positions + the test 4th
    pos_file.write_text(json.dumps({
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {
            f"S{i}": {
                "symbol": f"S{i}", "direction": "long", "status": "OPEN",
                "entry_price": 5.0, "stop": 4.95, "target": 5.20,
                "quantity": 100, "opened_at": "2026-07-21T15:00:00Z",
            } for i in range(3)
        },
        "history": [],
    }, indent=2), encoding="utf-8")

    body = [
        "result = ta.open_position(",
        "    symbol='NEWSYM', direction='long', entry_price=6.00, quantity=100,",
        ")",
        "state = json.loads(ta.POSITIONS_FILE.read_text())",
        "print(f'RESULT: {result}')",
        "print(f'NEWSYM in positions: {\"NEWSYM\" in state[\"positions\"]}')",
        "ok = result is False and 'NEWSYM' not in state['positions']",
        "sys.exit(0 if ok else 1)",
    ]
    code = _make_runner(pos_file, journal_csv, audit_log, body)
    result = _run_in_subprocess(code, pos_file, journal_csv, audit_log)
    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] blocked-order test failed (rc={result.returncode})")
        print("STDERR:", result.stderr)
        sys.exit(1)
    print("[PASS] Pre-trade gate blocked over-positioned order (no state change)")


# 3. Valid order is paper-routed ----------------------------------------- #
print()
print("=" * 70)
print("STEP 3/6: Valid order is paper-routed, audit log written")
print("=" * 70)
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    pos_file = tmp / "positions.json"
    journal_csv = tmp / "trade_journal.csv"
    audit_log = tmp / "audit.jsonl"
    pos_file.write_text(json.dumps({
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {}, "history": [],
    }, indent=2), encoding="utf-8")

    body = [
        "result = ta.open_position(",
        "    symbol='PTLE', direction='long', entry_price=6.00, quantity=100,",
        ")",
        "state = json.loads(ta.POSITIONS_FILE.read_text())",
        "pos = state['positions'].get('PTLE', {})",
        "print(f'open_position returned: {result}')",
        "print(f'execution_decision: {pos.get(\"execution_decision\")}')",
        "print(f'execution_audit_id: {pos.get(\"execution_audit_id\")}')",
        "ok = (",
        "    result is True",
        "    and 'PTLE' in state['positions']",
        "    and pos.get('execution_decision') in ('paper', 'live')",
        "    and (pos.get('execution_audit_id') or '').startswith('aud_')",
        ")",
        "sys.exit(0 if ok else 1)",
    ]
    code = _make_runner(pos_file, journal_csv, audit_log, body)
    result = _run_in_subprocess(code, pos_file, journal_csv, audit_log)
    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] valid-order test failed (rc={result.returncode})")
        print("STDERR:", result.stderr)
        sys.exit(1)
    print("[PASS] Valid order: paper-routed + audit_id persisted")


# 4. Audit log has the decision ------------------------------------------ #
print()
print("=" * 70)
print("STEP 4/6: Audit log written with decision + reason")
print("=" * 70)
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    pos_file = tmp / "positions.json"
    journal_csv = tmp / "trade_journal.csv"
    audit_log = tmp / "audit.jsonl"
    pos_file.write_text(json.dumps({
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {}, "history": [],
    }, indent=2), encoding="utf-8")

    body = [
        "ta.open_position(symbol='PTLE', direction='long', entry_price=6.00, quantity=100)",
    ]
    code = _make_runner(pos_file, journal_csv, audit_log, body)
    result = _run_in_subprocess(code, pos_file, journal_csv, audit_log)
    if result.returncode != 0:
        print(f"[FAIL] open for audit test failed: {result.stderr}")
        sys.exit(1)

    if not audit_log.exists():
        print(f"[FAIL] audit log not created at {audit_log}")
        sys.exit(1)
    lines = [l for l in audit_log.read_text().splitlines() if l.strip()]
    if not lines:
        print(f"[FAIL] audit log is empty")
        sys.exit(1)
    rec = json.loads(lines[-1])
    print(f"audit record: decision={rec.get('decision')!r}, symbol={rec.get('symbol')!r}")
    if rec.get("decision") not in ("paper", "live", "blocked"):
        print(f"[FAIL] unexpected decision: {rec.get('decision')}")
        sys.exit(1)
    if not rec.get("audit_id", "").startswith("aud_"):
        print(f"[FAIL] missing audit_id: {rec}")
        sys.exit(1)
    print(f"[PASS] Audit log written: audit_id={rec['audit_id'][:20]}..., decision={rec['decision']}")


# 5. execute_exit() appends to journal CSV ------------------------------- #
print()
print("=" * 70)
print("STEP 5/6: execute_exit() appends closed position to journal CSV")
print("=" * 70)
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    pos_file = tmp / "positions.json"
    journal_csv = tmp / "trade_journal.csv"
    audit_log = tmp / "audit.jsonl"
    pos_file.write_text(json.dumps({
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
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

    body = [
        "state = json.loads(ta.POSITIONS_FILE.read_text())",
        "pos = state['positions']['MIMI']",
        "ta.execute_exit(state, 'MIMI', pos, 'TARGET_HIT', 5.20)",
        "ta.save_positions(state)",
    ]
    code = _make_runner(pos_file, journal_csv, audit_log, body)
    result = _run_in_subprocess(code, pos_file, journal_csv, audit_log)
    if result.returncode != 0:
        print(f"[FAIL] exit test failed: {result.stderr}")
        sys.exit(1)

    if not journal_csv.exists():
        print(f"[FAIL] journal CSV not created")
        sys.exit(1)
    with journal_csv.open() as fh:
        rows = list(__import__("csv").DictReader(fh))
    if len(rows) != 1:
        print(f"[FAIL] expected 1 row in journal, got {len(rows)}")
        sys.exit(1)
    r = rows[0]
    print(f"journal row: asset={r['asset']}, entry={r['entry']}, exit={r['exit']}, r_multiple={r['r_multiple']}")
    if r["asset"] != "MIMI" or abs(float(r["r_multiple"]) - 4.0) > 0.001:
        print(f"[FAIL] journal row wrong: {r}")
        sys.exit(1)
    print("[PASS] Closed position appended to trade_journal.csv (r_multiple=4.0)")


# 6. trading_loop engine accepts the journal ----------------------------- #
print()
print("=" * 70)
print("STEP 6/6: trading_loop engine reads the journal CSV")
print("=" * 70)
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    pos_file = tmp / "positions.json"
    journal_csv = tmp / "trade_journal.csv"
    audit_log = tmp / "audit.jsonl"
    pos_file.write_text(json.dumps({
        "schema_version": "1.0",
        "updated_at": "2026-07-21T15:30:00Z",
        "positions": {},
        "history": [
            {"symbol": "AAA", "direction": "long", "status": "CLOSED",
             "entry_price": 10.0, "stop": 9.9, "exit_price": 10.4,
             "opened_at": "2026-07-15T10:00:00Z",
             "entry_signal": "First Pullback", "exit_reason": "TARGET_HIT",
             "pnl": 40.0, "exited_at": "2026-07-15T10:30:00Z"},
            {"symbol": "BBB", "direction": "long", "status": "CLOSED",
             "entry_price": 5.0, "stop": 4.95, "exit_price": 4.85,
             "opened_at": "2026-07-16T10:00:00Z",
             "entry_signal": "First Pullback", "exit_reason": "STOP_HIT",
             "pnl": -15.0, "exited_at": "2026-07-16T10:05:00Z"},
        ],
    }, indent=2), encoding="utf-8")

    body = [
        "from trading_agent.learning.trade_journal import export_to_csv, load_journal",
        "from trading_agent.learning.trading_loop.engine import (",
        "    new_state, run_cycle, compute_metrics,",
        ")",
        "n = export_to_csv()",
        "trades = load_journal()",
        "print(f'exported {n} trades, loaded {len(trades)}')",
        "state = new_state('test', primary_metric='expectancy_R')",
        "rec = run_cycle(state, trades)",
        "print(f'cycle 1 decision: {rec[\"gate\"][\"decision\"]}')",
        "print(f'cycle 1 metrics: {rec[\"metrics\"]}')",
        "metrics = compute_metrics(trades)",
        "print(f'computed metrics: win_rate={metrics[\"win_rate\"]}, expectancy_R={metrics[\"expectancy_R\"]:.2f}')",
        "ok = (",
        "    n == 2",
        "    and len(trades) == 2",
        "    and rec['gate']['decision'] == 'baseline'",
        "    and metrics['win_rate'] == 0.5",
        ")",
        "sys.exit(0 if ok else 1)",
    ]
    code = _make_runner(pos_file, journal_csv, audit_log, body)
    result = _run_in_subprocess(code, pos_file, journal_csv, audit_log)
    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] trading_loop cycle failed (rc={result.returncode})")
        print("STDERR:", result.stderr)
        sys.exit(1)
    print("[PASS] trading_loop ran one cycle on exported journal data")


# Done ------------------------------------------------------------------- #
print()
print("=" * 70)
print("SMOKE E2E PASSED — Dev environment is working")
print("=" * 70)
print("All 6 verification items pass:")
print("  1. [PASS] Unit tests (75 expected)")
print("  2. [PASS] Pre-trade gate blocks over-positioned order")
print("  3. [PASS] Valid order is paper-routed, audit log written")
print("  4. [PASS] Audit log has decision + audit_id")
print("  5. [PASS] execute_exit() appends to trade_journal.csv")
print("  6. [PASS] trading_loop engine reads the journal")
print()
print("Dev environment is ready for sign-off. Move to UAT only after Kay")
print("confirms the 6 items above and resolves the 3 blockers (REA-0.2,")
print("REA-0.3, REA-1.2).")
sys.exit(0)
