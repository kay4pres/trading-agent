"""Execution safety gate.

Adapted from Lewis Jackson's execution-safety skill
(https://github.com/jackson-video-resources/skills, MIT-style) for the
trading-agent project. Original 4-step gate (mode check → hard risk limits →
typed human confirmation → audit log) preserved verbatim. Broker adapter
interfaces are now pointed at our IBGW relay instead of alpaca-py/ccxt.

Attribution:
- Author: Lewis Jackson / 01 Accelerator
- Refactored into this package: 2026-07-21 (Mavis Code, Day 4)
- License: MIT-style (preserved from upstream)
"""

from trading_agent.execution.guard import (
    ALLOW_TRADING_ENV,
    AUDIT_PATH,
    BrokerAdapter,
    IBKRLiveAdapter,
    Order,
    PaperAdapter,
    RiskProfile,
    StubLiveAdapter,
    audit_log_path,
    check_risk_limits,
    guard_order,
)

__all__ = [
    "ALLOW_TRADING_ENV",
    "AUDIT_PATH",
    "BrokerAdapter",
    "IBKRLiveAdapter",
    "Order",
    "PaperAdapter",
    "RiskProfile",
    "StubLiveAdapter",
    "audit_log_path",
    "check_risk_limits",
    "guard_order",
]
