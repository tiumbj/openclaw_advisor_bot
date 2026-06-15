from __future__ import annotations

from ._version import PHASE, __version__

PACKAGE_VERSION = __version__
PACKAGE_PHASE = PHASE
CANONICAL_RUNTIME_AGENT_ID = "super-advisor"
RUNTIME_AGENT_IDS = (
    "super-advisor",
    "xau-strategy-auditor",
    "system-coder-auditor",
    "telegram-publisher",
    "market-data-integrity-agent",
    "price-action-microstructure-agent",
    "intermarket-macro-agent",
    "statistical-backtest-agent",
    "failure-root-cause-agent",
    "security-compliance-agent",
    "reliability-watchdog-agent",
    "knowledge-skill-manager",
)

# Skills owned by the original 4 runtime agents (maintained for compatibility)
_SUPER_ADVISOR_SKILLS = (
    "advisor-safety-contract",
    "environment-health",
    "evidence-audit",
    "agent-orchestration-contract",
    "super-potential-review",
    "incident-reporting",
    "publication-policy",
)
_XAU_STRATEGY_AUDITOR_SKILLS = (
    "xauusd-market-analysis",
    "multi-timeframe-structure-review",
    "price-action-order-block",
    "chart-pattern-filter-review",
    "candlestick-microstructure",
    "strategy-logic-audit",
    "realtime-evidence-review",
    "super-potential-audit",
    "alert-quality-improvement",
)
_SYSTEM_CODER_AUDITOR_SKILLS = (
    "python-pipeline-micro-audit",
    "code-architecture-review",
    "logic-conflict-detection",
    "dead-code-and-duplicate-review",
    "test-and-regression-design",
    "blueprint-compliance-audit",
    "safe-patch-workflow",
    "release-and-rollback",
    "skill-improvement-proposal",
)
_TELEGRAM_PUBLISHER_SKILLS = (
    "thai-telegram-publisher",
    "telegram-message-contract",
    "telegram-delivery-safety",
    "telegram-deduplication-throttle",
    "telegram-retry-and-dead-letter",
    "telegram-security-redaction",
)
# Skills for new specialist agents
_MARKET_DATA_INTEGRITY_SKILLS = (
    "market-data-coverage-audit",
    "data-provenance-contract",
    "stale-data-detection",
)
_PRICE_ACTION_MICROSTRUCTURE_SKILLS = (
    "candlestick-structure-analysis",
    "microstructure-trigger-audit",
    "m1-m5-pattern-review",
)
_INTERMARKET_MACRO_SKILLS = (
    "fx-basket-analysis",
    "us10y-context-review",
    "intermarket-correlation-audit",
    "regime-classification",
)
_STATISTICAL_BACKTEST_SKILLS = (
    "sample-adequacy-review",
    "walk-forward-analysis",
    "overfitting-detection",
)
_FAILURE_ROOT_CAUSE_SKILLS = (
    "alert-failure-analysis",
    "root-cause-tree-builder",
    "corrective-hypothesis-design",
)
_SECURITY_COMPLIANCE_SKILLS = (
    "advisor-only-enforcement",
    "privilege-boundary-audit",
    "secret-exposure-scan",
)
_RELIABILITY_WATCHDOG_SKILLS = (
    "process-health-monitor",
    "component-restart-protocol",
    "incident-escalation-contract",
)
_KNOWLEDGE_SKILL_MANAGER_SKILLS = (
    "research-knowledge-lifecycle",
    "skill-candidate-lifecycle",
    "experiment-outcome-recording",
)

AGENT_SKILL_NAMES: dict[str, tuple[str, ...]] = {
    "super-advisor": _SUPER_ADVISOR_SKILLS,
    "xau-strategy-auditor": _XAU_STRATEGY_AUDITOR_SKILLS,
    "system-coder-auditor": _SYSTEM_CODER_AUDITOR_SKILLS,
    "telegram-publisher": _TELEGRAM_PUBLISHER_SKILLS,
    "market-data-integrity-agent": _MARKET_DATA_INTEGRITY_SKILLS,
    "price-action-microstructure-agent": _PRICE_ACTION_MICROSTRUCTURE_SKILLS,
    "intermarket-macro-agent": _INTERMARKET_MACRO_SKILLS,
    "statistical-backtest-agent": _STATISTICAL_BACKTEST_SKILLS,
    "failure-root-cause-agent": _FAILURE_ROOT_CAUSE_SKILLS,
    "security-compliance-agent": _SECURITY_COMPLIANCE_SKILLS,
    "reliability-watchdog-agent": _RELIABILITY_WATCHDOG_SKILLS,
    "knowledge-skill-manager": _KNOWLEDGE_SKILL_MANAGER_SKILLS,
}

SKILL_NAMES = tuple(
    skill for agent_id in RUNTIME_AGENT_IDS for skill in AGENT_SKILL_NAMES[agent_id]
)
SKILL_OWNERS = {
    skill: agent_id for agent_id, skills in AGENT_SKILL_NAMES.items() for skill in skills
}

_STANDARD_DENY = (
    "group:runtime",
    "group:web",
    "group:ui",
    "group:automation",
    "group:messaging",
    "group:plugins",
    "group:memory",
    "group:sessions",
    "write",
    "edit",
    "apply_patch",
    "exec",
    "process",
    "code_execution",
    "browser",
    "canvas",
    "gateway",
    "message",
    "subagents",
    "memory_search",
    "memory_get",
    "sessions_list",
    "sessions_history",
    "sessions_send",
    "sessions_spawn",
    "sessions_yield",
)
_SUPER_ADVISOR_DENY = tuple(
    item for item in _STANDARD_DENY if item not in {"group:messaging", "message"}
)

AGENT_ALLOWED_TOOLS: dict[str, tuple[str, ...]] = {
    "super-advisor": ("read", "session_status"),
    "xau-strategy-auditor": ("read", "session_status"),
    "system-coder-auditor": ("read", "session_status"),
    "telegram-publisher": ("read", "session_status"),
    "market-data-integrity-agent": ("read", "session_status"),
    "price-action-microstructure-agent": ("read", "session_status"),
    "intermarket-macro-agent": ("read", "session_status"),
    "statistical-backtest-agent": ("read", "session_status"),
    "failure-root-cause-agent": ("read", "session_status"),
    "security-compliance-agent": ("read", "session_status"),
    "reliability-watchdog-agent": ("read", "session_status"),
    "knowledge-skill-manager": ("read", "session_status"),
}

AGENT_DENIED_TOOLS: dict[str, tuple[str, ...]] = {
    agent_id: (_SUPER_ADVISOR_DENY if agent_id == "super-advisor" else _STANDARD_DENY)
    for agent_id in RUNTIME_AGENT_IDS
}

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

# MT5 symbol env var names in order matching the 8 required symbols
MT5_SYMBOL_ENV_VARS = (
    "MT5_XAUUSD_SYMBOL",
    "MT5_EURUSD_SYMBOL",
    "MT5_GBPUSD_SYMBOL",
    "MT5_AUDUSD_SYMBOL",
    "MT5_NZDUSD_SYMBOL",
    "MT5_USDJPY_SYMBOL",
    "MT5_USDCHF_SYMBOL",
    "MT5_USDCAD_SYMBOL",
    "MT5_DXY_SYMBOL",
    "MT5_US10Y_SYMBOL",
)

# FRED series definitions
FRED_SERIES = {
    "US10Y": {
        "series_id": "DGS10",
        "internal_id": "US10Y_DAILY",
        "realtime_class": "DAILY_MACRO",
        "unit": "Percent",
        "is_proxy": False,
        "is_exact_dxy": False,
    },
    "USD_BROAD": {
        "series_id": "DTWEXBGS",
        "internal_id": "DXY_PROXY_FRED",
        "realtime_class": "DAILY_MACRO",
        "unit": "Index",
        "is_proxy": True,
        "is_exact_dxy": False,
        "usage": "macro_usd_strength_context",
    },
}

# FX basket pairs for DXY proxy computation
# Pairs where USD is the quote (direction must be reversed for USD strength)
FX_BASKET_PAIRS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD")
FX_BASKET_REVERSE_PAIRS = frozenset(("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"))
FX_BASKET_INTERNAL_ID = "FX_BASKET_COMPUTED"

# Data realtime class values
REALTIME_CLASS_REALTIME = "REALTIME"
REALTIME_CLASS_DELAYED_15MIN = "DELAYED_15MIN"
REALTIME_CLASS_DAILY_MACRO = "DAILY_MACRO"
REALTIME_CLASS_COMPUTED = "COMPUTED"
REALTIME_CLASS_STALE = "STALE"
REALTIME_CLASS_UNKNOWN = "UNKNOWN"
REALTIME_CLASS_ALLOWED = (
    REALTIME_CLASS_REALTIME,
    REALTIME_CLASS_DELAYED_15MIN,
    REALTIME_CLASS_DAILY_MACRO,
    REALTIME_CLASS_COMPUTED,
    REALTIME_CLASS_STALE,
    REALTIME_CLASS_UNKNOWN,
)

# Backward-compatible aliases for code paths/tests that still describe intraday timing.
REALTIME_CLASS_INTRADAY_REALTIME = REALTIME_CLASS_REALTIME
REALTIME_CLASS_INTRADAY_DELAYED = REALTIME_CLASS_DELAYED_15MIN

# System Telegram event types
TELEGRAM_SYSTEM_EVENTS = (
    "SYSTEM_STARTED",
    "SYSTEM_RECOVERED",
    "SYSTEM_SHUTTING_DOWN",
    "SYSTEM_OFFLINE_DETECTED",
    "GATEWAY_FAILED",
    "PYTHON_ENGINE_FAILED",
    "QUEUE_STALLED",
    "DATA_STALE",
    "MT5_DISCONNECTED",
    "FRED_UNAVAILABLE",
    "DISK_LOW",
    "DATABASE_LOCKED",
    "EXPERIMENT_FAILED",
    "SECURITY_INCIDENT",
)
