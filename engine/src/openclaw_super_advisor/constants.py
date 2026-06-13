from __future__ import annotations

from ._version import PHASE, __version__

PACKAGE_VERSION = __version__
PACKAGE_PHASE = PHASE
CANONICAL_RUNTIME_AGENT_ID = "super-advisor"
SKILL_NAMES = (
    "advisor-safety-contract",
    "environment-health",
    "python-engine-bridge",
    "evidence-audit",
    "super-potential-review",
    "thai-telegram-publisher",
    "incident-reporting",
)
FORBIDDEN_SYMBOLS = (
    "order_send",
    "order_check",
    "TRADE_ACTION",
    "ExecutionKernel",
    "execution_kernel",
    "execution_dispatch_bridge",
    "position_close",
    "close_position",
    "modify_order",
    "cancel_order",
    "execute_order",
    "auto_trade",
)
FORBIDDEN_TRACKED_PATHS = (
    r"state\.env",
    r"state\openclaw.json",
    r"state\credentials",
    r"state\sessions",
    r"state\logs",
    r"\.venv",
    r"logs",
    r"data\runtime",
    r"archive",
)
ENV_STATUSES = ("PRESENT", "MISSING", "BLANK", "INVALID_FORMAT")
