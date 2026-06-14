from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ._version import PHASE, __version__
from .constants import (
    AGENT_ALLOWED_TOOLS,
    AGENT_DENIED_TOOLS,
    AGENT_SKILL_NAMES,
    CANONICAL_RUNTIME_AGENT_ID,
    RUNTIME_AGENT_IDS,
    SKILL_NAMES,
    SKILL_OWNERS,
)
from .paths import ProjectPaths

REALTIME_ROUTE_ALLOWLIST = (
    ("evidence-archive", "super-advisor"),
    ("super-advisor", "xau-strategy-auditor"),
    ("xau-strategy-auditor", "super-advisor"),
    ("super-advisor", "telegram-publisher"),
    ("telegram-publisher", "outcome-ledger"),
)
CODE_AUDIT_ROUTE_ALLOWLIST = (
    ("source-bundle", "system-coder-auditor"),
    ("system-coder-auditor", "audit-report"),
)


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    name: str
    description: str
    workspace: str
    agent_dir: str
    session_store: str
    memory_dir: str
    skills: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    denied_tools: tuple[str, ...]
    secret_access: str
    timeout_seconds: int
    retry_max_attempts: int


@dataclass(frozen=True)
class AgentTopologyIssue:
    path: str
    rule: str
    message: str


@dataclass(frozen=True)
class AgentTopologyReport:
    version: str
    phase: str
    valid: bool
    agents: tuple[AgentContract, ...]
    issues: tuple[AgentTopologyIssue, ...]
    route_issues: tuple[AgentTopologyIssue, ...]


@dataclass(frozen=True)
class RouteValidationReport:
    version: str
    phase: str
    valid: bool
    allowed_routes: tuple[tuple[str, str], ...]
    issues: tuple[AgentTopologyIssue, ...]


def _agent_specs() -> dict[str, dict[str, object]]:
    return {
        "super-advisor": {
            "name": "OpenClaw MAIN Agent Manager",
            "description": (
                "Sole user-facing coordinator; planner, router, evidence arbiter, release gate."
            ),
            "secret_access": "none",
            "timeout_seconds": 300,
            "retry_max_attempts": 2,
        },
        "xau-strategy-auditor": {
            "name": "XAU Strategy Research Agent",
            "description": "Read-only XAUUSD multi-timeframe research and alert-quality review.",
            "secret_access": "none",
            "timeout_seconds": 90,
            "retry_max_attempts": 2,
        },
        "system-coder-auditor": {
            "name": "System Coder Auditor",
            "description": "Read-only code-audit agent; isolated worktree patch proposals only.",
            "secret_access": "none",
            "timeout_seconds": 90,
            "retry_max_attempts": 2,
        },
        "telegram-publisher": {
            "name": "Thai Telegram Publisher",
            "description": "Approved Thai publication formatter and delivery safety gate.",
            "secret_access": "approved_payload_only",
            "timeout_seconds": 60,
            "retry_max_attempts": 3,
        },
        "market-data-integrity-agent": {
            "name": "Market Data Integrity Agent",
            "description": "MT5/FRED data quality audit: missing bars, timezone, provenance.",
            "secret_access": "none",
            "timeout_seconds": 120,
            "retry_max_attempts": 3,
        },
        "price-action-microstructure-agent": {
            "name": "Price Action Microstructure Agent",
            "description": (
                "Candlestick structure, wick/body, rejection, and M1/M5 trigger analysis."
            ),
            "secret_access": "none",
            "timeout_seconds": 90,
            "retry_max_attempts": 2,
        },
        "intermarket-macro-agent": {
            "name": "Intermarket Macro Agent",
            "description": "USD basket, US10Y, FX correlation, lead/lag, regime classification.",
            "secret_access": "none",
            "timeout_seconds": 120,
            "retry_max_attempts": 2,
        },
        "statistical-backtest-agent": {
            "name": "Statistical Backtest Agent",
            "description": (
                "Sample adequacy, walk-forward, stability, overfitting and leakage detection."
            ),
            "secret_access": "none",
            "timeout_seconds": 300,
            "retry_max_attempts": 2,
        },
        "failure-root-cause-agent": {
            "name": "Failure Root Cause Agent",
            "description": (
                "Alert failure analysis, logic conflict audit, root-cause tree, "
                "corrective hypothesis."
            ),
            "secret_access": "none",
            "timeout_seconds": 120,
            "retry_max_attempts": 2,
        },
        "security-compliance-agent": {
            "name": "Security Compliance Agent",
            "description": "Advisor-only enforcement, secret exposure scan, agent privilege audit.",
            "secret_access": "none",
            "timeout_seconds": 60,
            "retry_max_attempts": 2,
        },
        "reliability-watchdog-agent": {
            "name": "Reliability Watchdog Agent",
            "description": (
                "Process health, heartbeat monitoring, restart protocol, incident escalation."
            ),
            "secret_access": "none",
            "timeout_seconds": 30,
            "retry_max_attempts": 5,
        },
        "knowledge-skill-manager": {
            "name": "Knowledge and Skill Manager",
            "description": (
                "Research knowledge lifecycle, experiment records, skill candidate management."
            ),
            "secret_access": "none",
            "timeout_seconds": 120,
            "retry_max_attempts": 2,
        },
    }


def build_agent_topology(paths: ProjectPaths) -> tuple[AgentContract, ...]:
    specs = _agent_specs()
    agents: list[AgentContract] = []
    for agent_id in RUNTIME_AGENT_IDS:
        spec = specs[agent_id]
        name = cast(str, spec["name"])
        description = cast(str, spec["description"])
        secret_access = cast(str, spec["secret_access"])
        timeout_seconds = cast(int, spec["timeout_seconds"])
        retry_max_attempts = cast(int, spec["retry_max_attempts"])
        agents.append(
            AgentContract(
                agent_id=agent_id,
                name=name,
                description=description,
                workspace=str(paths.workspace_dir / "agents" / agent_id),
                agent_dir=str(paths.state_dir / "agents" / agent_id / "agent"),
                session_store=str(paths.state_dir / "agents" / agent_id / "sessions"),
                memory_dir=str(paths.state_dir / "agents" / agent_id / "memory"),
                skills=AGENT_SKILL_NAMES[agent_id],
                allowed_tools=AGENT_ALLOWED_TOOLS[agent_id],
                denied_tools=AGENT_DENIED_TOOLS[agent_id],
                secret_access=secret_access,
                timeout_seconds=timeout_seconds,
                retry_max_attempts=retry_max_attempts,
            )
        )
    return tuple(agents)


def render_blueprint_config(paths: ProjectPaths) -> dict[str, object]:
    agents = []
    for agent in build_agent_topology(paths):
        agents.append(
            {
                "id": agent.agent_id,
                "default": agent.agent_id == CANONICAL_RUNTIME_AGENT_ID,
                "name": agent.name,
                "description": agent.description,
                "workspace": agent.workspace,
                "agentDir": agent.agent_dir,
                "sessionStore": agent.session_store,
                "memoryDir": agent.memory_dir,
                "skills": list(agent.skills),
                "tools": {
                    "allow": list(agent.allowed_tools),
                    "deny": list(agent.denied_tools),
                    "exec": {
                        "mode": "deny",
                        "applyPatch": {"enabled": False, "workspaceOnly": True},
                    },
                    "fs": {"workspaceOnly": True},
                    "message": {
                        "allowCrossContextSend": False,
                        "crossContext": {
                            "allowWithinProvider": False,
                            "allowAcrossProviders": False,
                        },
                        "actions": {"allow": []},
                        "broadcast": {"enabled": False},
                    },
                    "agentToAgent": {"enabled": False},
                    "elevated": {"enabled": False},
                    "sandbox": {
                        "tools": {
                            "allow": list(agent.allowed_tools),
                            "deny": list(agent.denied_tools),
                        }
                    },
                },
                "secretAccess": {"mode": agent.secret_access},
                "timeoutSeconds": agent.timeout_seconds,
                "retry": {"maxAttempts": agent.retry_max_attempts, "backoffSeconds": 2},
            }
        )
    return {
        "version": __version__,
        "phase": PHASE,
        "skills": list(SKILL_NAMES),
        "agents": agents,
        "routing": {
            "realtime": [
                ["evidence-archive", "super-advisor"],
                ["super-advisor", "xau-strategy-auditor"],
                ["xau-strategy-auditor", "super-advisor"],
                ["super-advisor", "telegram-publisher"],
                ["telegram-publisher", "outcome-ledger"],
            ],
            "code-audit": [
                ["source-bundle", "system-coder-auditor"],
                ["system-coder-auditor", "audit-report"],
            ],
        },
    }


def validate_agent_topology(
    config: dict[str, object] | None,
    paths: ProjectPaths,
) -> AgentTopologyReport:
    agents = build_agent_topology(paths)
    issues: list[AgentTopologyIssue] = []
    route_issues: list[AgentTopologyIssue] = []
    if config is None:
        return AgentTopologyReport(
            version=__version__,
            phase=PHASE,
            valid=False,
            agents=agents,
            issues=(AgentTopologyIssue("config", "missing", "config is required"),),
            route_issues=(),
        )
    skill_values = config.get("skills")
    if skill_values != list(SKILL_NAMES):
        issues.append(
            AgentTopologyIssue(
                "skills",
                "skill_catalog_mismatch",
                "runtime skill catalog must match the declared blueprint skills",
            )
        )

    agents_value = config.get("agents")
    if not isinstance(agents_value, dict):
        issues.append(AgentTopologyIssue("agents", "missing", "agents section is required"))
    else:
        defaults = agents_value.get("defaults")
        if not isinstance(defaults, dict):
            issues.append(AgentTopologyIssue("agents.defaults", "missing", "defaults required"))
        agent_list = agents_value.get("list")
        if not isinstance(agent_list, list):
            issues.append(AgentTopologyIssue("agents.list", "missing", "agent list is required"))
        else:
            seen_ids: set[str] = set()
            if len(agent_list) != len(agents):
                issues.append(
                    AgentTopologyIssue(
                        "agents.list",
                        "count_mismatch",
                        f"expected {len(agents)} agents, got {len(agent_list)}",
                    )
                )
            for index, agent_item in enumerate(agent_list):
                if not isinstance(agent_item, dict):
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}]",
                            "type",
                            "agent entry must be an object",
                        )
                    )
                    continue
                agent_id = str(agent_item.get("id", ""))
                if agent_id not in AGENT_SKILL_NAMES:
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].id",
                            "unknown_agent",
                            f"unexpected agent id {agent_id!r}",
                        )
                    )
                    continue
                if agent_id in seen_ids:
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].id",
                            "duplicate_agent",
                            f"duplicate agent id {agent_id!r}",
                        )
                    )
                seen_ids.add(agent_id)
                expected = next(item for item in agents if item.agent_id == agent_id)
                if str(agent_item.get("workspace", "")) != expected.workspace:
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].workspace",
                            "workspace_mismatch",
                            "agent workspace must be isolated per agent",
                        )
                    )
                if str(agent_item.get("agentDir", "")) != expected.agent_dir:
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].agentDir",
                            "agent_dir_mismatch",
                            "agent directory must be isolated per agent",
                        )
                    )
                if list(agent_item.get("skills", [])) != list(expected.skills):
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].skills",
                            "skills_mismatch",
                            "agent skill allowlist mismatch",
                        )
                    )
                tools = agent_item.get("tools")
                if not isinstance(tools, dict):
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].tools",
                            "missing",
                            "tools block is required",
                        )
                    )
                    continue
                allow = tuple(tools.get("allow", []))
                if allow != expected.allowed_tools:
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].tools.allow",
                            "allow_mismatch",
                            "tool allowlist mismatch",
                        )
                    )
                deny = tuple(tools.get("deny", []))
                if deny != expected.denied_tools:
                    issues.append(
                        AgentTopologyIssue(
                            f"agents.list[{index}].tools.deny",
                            "deny_mismatch",
                            "tool denylist mismatch",
                        )
                    )

    routing = config.get("routing")
    if isinstance(routing, dict):
        realtime = routing.get("realtime", [])
        if [tuple(r) for r in realtime] != list(REALTIME_ROUTE_ALLOWLIST):
            route_issues.append(
                AgentTopologyIssue(
                    "routing.realtime",
                    "allowlist_mismatch",
                    "realtime routing must match the allowlist",
                )
            )
        code_audit = routing.get("code-audit", [])
        if [tuple(r) for r in code_audit] != list(CODE_AUDIT_ROUTE_ALLOWLIST):
            route_issues.append(
                AgentTopologyIssue(
                    "routing.code-audit",
                    "allowlist_mismatch",
                    "code-audit routing must match the allowlist",
                )
            )

    return AgentTopologyReport(
        version=__version__,
        phase=PHASE,
        valid=not issues and not route_issues,
        agents=agents,
        issues=tuple(issues),
        route_issues=tuple(route_issues),
    )


def validate_routing(
    routes: dict[str, list[list[str]]] | None,
) -> RouteValidationReport:
    issues: list[AgentTopologyIssue] = []
    if routes is None:
        return RouteValidationReport(
            version=__version__,
            phase=PHASE,
            valid=False,
            allowed_routes=(),
            issues=(AgentTopologyIssue("routing", "missing", "routing config is required"),),
        )
    realtime = routes.get("realtime", [])
    code_audit = routes.get("code-audit", [])
    if [tuple(item) for item in realtime] != list(REALTIME_ROUTE_ALLOWLIST):
        issues.append(
            AgentTopologyIssue(
                "routing.realtime",
                "allowlist_mismatch",
                "realtime routing must match the allowlist",
            )
        )
    if [tuple(item) for item in code_audit] != list(CODE_AUDIT_ROUTE_ALLOWLIST):
        issues.append(
            AgentTopologyIssue(
                "routing.code-audit",
                "allowlist_mismatch",
                "code-audit routing must match the allowlist",
            )
        )
    disallowed_routes = {
        ("telegram-publisher", "xau-strategy-auditor"),
        ("telegram-publisher", "system-coder-auditor"),
        ("xau-strategy-auditor", "telegram-publisher"),
        ("system-coder-auditor", "super-advisor"),
        ("unknown-agent", "any"),
    }
    for route in [*map(tuple, realtime), *map(tuple, code_audit)]:
        if route in disallowed_routes:
            issues.append(
                AgentTopologyIssue(
                    "routing",
                    "disallowed_route",
                    f"disallowed route {route[0]!r} -> {route[1]!r}",
                )
            )
    return RouteValidationReport(
        version=__version__,
        phase=PHASE,
        valid=not issues,
        allowed_routes=tuple([*REALTIME_ROUTE_ALLOWLIST, *CODE_AUDIT_ROUTE_ALLOWLIST]),
        issues=tuple(issues),
    )


def validate_skill_owners(skill_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for skill_name in skill_names:
        if skill_name not in SKILL_OWNERS:
            missing.append(skill_name)
    return tuple(missing)
