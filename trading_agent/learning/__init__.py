"""Learning — closed self-learning loop with keep/revert gate.

Adapted from Lewis Jackson's trading-loop skill (MIT-style). The engine runs
a monthly closed cadence: hypothesis → paper-trade window → measure →
loss-autopsy → adjust one variable → keep/revert gate → re-run.

This is the missing piece in our arch. We have a `knowledge/memory/trade_journal.md`
plan but no mechanism. The trading_loop engine (19 KB numpy + stdlib) is the
template.

Author attribution:
  - Engine author: Lewis Jackson / 01 Accelerator
  - Refactored into this package: 2026-07-21 (Mavis Code, Day 4)
  - License: MIT-style (preserved from upstream)

For the trading-agent project:
  1. Persist closed positions to E:\\Me\\TradingAgent\\data\\trade_journal.csv
     (one row per closed trade, in the schema trading_loop expects)
  2. Run `trading_loop init` once with hypothesis + primary_metric
  3. Run `trading_loop run` monthly with the next window
  4. Loop proposes ONE variable change, runs next window, keeps or reverts
  5. After 3+ months, the loop's accepted_config is the "best so far"
"""

from trading_agent.learning.trading_loop.engine import (
    DEFAULT_CONFIG,
    EPS,
    HIGHER_IS_BETTER,
    apply_config,
    compute_metrics,
    load_state,
    load_trades,
    loss_autopsy,
    new_state,
    normalise_trade,
    propose_change,
    run_cycle,
    save_state,
)

__all__ = [
    "DEFAULT_CONFIG",
    "EPS",
    "HIGHER_IS_BETTER",
    "apply_config",
    "compute_metrics",
    "load_state",
    "load_trades",
    "loss_autopsy",
    "new_state",
    "normalise_trade",
    "propose_change",
    "run_cycle",
    "save_state",
]
