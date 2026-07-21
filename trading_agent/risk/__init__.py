"""Risk modules — pre-trade gate that BLOCKS orders violating hard limits.

Adapted from Lewis Jackson's risk-manager skill Mode #1 (MIT-style).
"""

from trading_agent.risk.pre_trade_gate import (
    DEFAULTS,
    GateConfig,
    evaluate,
    gate_or_block,
)

__all__ = ["DEFAULTS", "GateConfig", "evaluate", "gate_or_block"]
