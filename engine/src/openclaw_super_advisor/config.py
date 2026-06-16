from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .agent_registry import build_agent_registry
from .agent_topology import build_agent_topology, validate_routing
from .constants import RUNTIME_AGENT_IDS, SKILL_NAMES
from .env import load_settings
from .paths import ProjectPaths

PLACEHOLDER_IN_STRING = re.compile(r'"{{([A-Z0-9_]+)}}"')
PLACEHOLDER_RAW = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


class ConfigValidationError(RuntimeError):
    """Raised when rendered config is invalid."""


@dataclass(frozen=True)
class ConfigValidationIssue:
    path: str
    message: str


@dataclass(frozen=True)
class ConfigValidationReport:
    valid: bool
    issues: tuple[ConfigValidationIssue, ...]


def _replace_string_placeholder(
    match: re.Match[str],
    values: dict[str, str],
) -> str:
    name = match.group(1)
    if name not in values:
        raise ConfigValidationError(f"Missing template value: {name}")
    return json.dumps(values[name])


def _replace_raw_placeholder(
    match: re.Match[str],
    values: dict[str, str],
) -> str:
    name = match.group(1)
    if name not in values:
        raise ConfigValidationError(f"Missing template value: {name}")
    return values[name]


def render_config(
    paths: ProjectPaths,
    env_path: Path | None = None,
) -> dict[str, object]:
    settings = load_settings(paths, env_path=env_path, strict=False)
    render_values = settings.render_context()
    for name, value in settings.parsed_values.items():
        if isinstance(value, Path):
            normalized = (paths.root_dir / value).resolve() if not value.is_absolute() else value
            render_values[name] = str(normalized)
    render_values["OPENCLAW_WORKSPACE_AGENTS_DIR"] = str(paths.workspace_dir / "agents")
    render_values["OPENCLAW_STATE_AGENTS_DIR"] = str(paths.state_dir / "agents")
    for agent_id in RUNTIME_AGENT_IDS:
        prefix = agent_id.upper().replace("-", "_")
        render_values[f"OPENCLAW_{prefix}_WORKSPACE_DIR"] = str(
            paths.workspace_dir / "agents" / agent_id
        )
        render_values[f"OPENCLAW_{prefix}_AGENT_DIR"] = str(
            paths.state_dir / "agents" / agent_id / "agent"
        )
        render_values[f"OPENCLAW_{prefix}_SESSION_STORE"] = str(
            paths.state_dir / "agents" / agent_id / "sessions"
        )
        render_values[f"OPENCLAW_{prefix}_MEMORY_DIR"] = str(
            paths.state_dir / "agents" / agent_id / "memory"
        )
    template_text = paths.config_template_path.read_text(encoding="utf-8")
    rendered = PLACEHOLDER_IN_STRING.sub(
        lambda match: _replace_string_placeholder(match, render_values), template_text
    )
    rendered = PLACEHOLDER_RAW.sub(
        lambda match: _replace_raw_placeholder(match, render_values), rendered
    )
    payload = json.loads(rendered)
    if not isinstance(payload, dict):
        raise ConfigValidationError("Rendered config must be a JSON object")
    try:
        registry = build_agent_registry(paths)
        payload["agentCapabilityRegistry"] = {
            "path": str(paths.agent_registry_path),
            "schemaVersion": registry.schema_version,
            "registryVersion": registry.registry_version,
            "registryHash": registry.registry_hash,
            "agentCount": registry.agent_count,
            "skillCount": registry.skill_count,
        }
    except (FileNotFoundError, ValueError):
        payload["agentCapabilityRegistry"] = {
            "path": str(paths.agent_registry_path),
            "schemaVersion": "",
            "registryVersion": "",
            "registryHash": "",
            "agentCount": 0,
            "skillCount": 0,
        }
    return cast(dict[str, object], payload)


def _as_object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{path} must be an object")
    return cast(dict[str, object], value)


def _as_list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ConfigValidationError(f"{path} must be a list")
    return cast(list[object], value)


def _require_equal(
    issues: list[ConfigValidationIssue],
    actual: object,
    expected: object,
    path: str,
) -> None:
    if actual != expected:
        issues.append(ConfigValidationIssue(path, f"expected {expected!r}, got {actual!r}"))


def _require_positive_int(
    issues: list[ConfigValidationIssue],
    actual: object,
    path: str,
) -> None:
    if not isinstance(actual, int) or actual <= 0:
        issues.append(ConfigValidationIssue(path, f"expected positive integer, got {actual!r}"))


def validate_rendered_config(
    config: dict[str, object],
    paths: ProjectPaths,
) -> ConfigValidationReport:
    if not isinstance(config, dict):
        raise ConfigValidationError("config must be an object")
    issues: list[ConfigValidationIssue] = []
    env_section = _as_object(config.get("env"), "env")
    shell_env = _as_object(env_section.get("shellEnv"), "env.shellEnv")
    _require_equal(issues, shell_env.get("enabled"), False, "env.shellEnv.enabled")

    gateway = _as_object(config.get("gateway"), "gateway")
    _require_equal(issues, gateway.get("mode"), "local", "gateway.mode")
    _require_equal(issues, gateway.get("bind"), "loopback", "gateway.bind")
    _require_equal(issues, gateway.get("port"), 18789, "gateway.port")
    auth = _as_object(gateway.get("auth"), "gateway.auth")
    _require_equal(issues, auth.get("mode"), "token", "gateway.auth.mode")
    token = _as_object(auth.get("token"), "gateway.auth.token")
    _require_equal(issues, token.get("source"), "env", "gateway.auth.token.source")
    _require_equal(issues, token.get("provider"), "default", "gateway.auth.token.provider")
    _require_equal(
        issues,
        token.get("id"),
        "OPENCLAW_GATEWAY_TOKEN",
        "gateway.auth.token.id",
    )
    control_ui = _as_object(gateway.get("controlUi"), "gateway.controlUi")
    _require_equal(issues, control_ui.get("enabled"), True, "gateway.controlUi.enabled")

    hooks = _as_object(config.get("hooks"), "hooks")
    _require_equal(issues, hooks.get("enabled"), False, "hooks.enabled")
    _require_equal(issues, config.get("skills"), list(SKILL_NAMES), "skills")

    agents = _as_object(config.get("agents"), "agents")
    defaults = _as_object(agents.get("defaults"), "agents.defaults")
    _require_equal(
        issues,
        defaults.get("workspace"),
        str(paths.workspace_dir / "agents"),
        "agents.defaults.workspace",
    )
    _require_equal(issues, defaults.get("skills"), list(SKILL_NAMES), "agents.defaults.skills")

    agent_list = _as_list(agents.get("list"), "agents.list")
    expected_agents = build_agent_topology(paths)
    if len(agent_list) != len(expected_agents):
        issues.append(
            ConfigValidationIssue(
                "agents.list", f"expected exactly {len(expected_agents)} configured agents"
            )
        )
    else:
        seen_ids: set[str] = set()
        expected_by_id = {agent.agent_id: agent for agent in expected_agents}
        for index, item in enumerate(agent_list):
            agent = _as_object(item, f"agents.list[{index}]")
            agent_id = str(agent.get("id", ""))
            if agent_id not in expected_by_id:
                issues.append(
                    ConfigValidationIssue(
                        f"agents.list[{index}].id", f"unexpected agent id {agent_id!r}"
                    )
                )
                continue
            if agent_id in seen_ids:
                issues.append(
                    ConfigValidationIssue(
                        f"agents.list[{index}].id", f"duplicate agent id {agent_id!r}"
                    )
                )
            seen_ids.add(agent_id)
            expected = expected_by_id[agent_id]
            _require_equal(
                issues,
                agent.get("workspace"),
                expected.workspace,
                f"agents.list[{index}].workspace",
            )
            _require_equal(
                issues,
                agent.get("agentDir"),
                expected.agent_dir,
                f"agents.list[{index}].agentDir",
            )
            _require_equal(
                issues,
                agent.get("sessionStore"),
                expected.session_store,
                f"agents.list[{index}].sessionStore",
            )
            _require_equal(
                issues,
                agent.get("memoryDir"),
                expected.memory_dir,
                f"agents.list[{index}].memoryDir",
            )
            _require_equal(
                issues, agent.get("skills"), list(expected.skills), f"agents.list[{index}].skills"
            )
            _validate_tools(
                _as_object(agent.get("tools"), f"agents.list[{index}].tools"),
                f"agents.list[{index}].tools",
                issues,
                is_super_advisor=agent_id == "super-advisor",
                is_blueprint_coder=agent_id == "blueprint-coder",
            )
            secret_access = _as_object(
                agent.get("secretAccess"), f"agents.list[{index}].secretAccess"
            )
            expected_secret_mode = (
                "approved_payload_only" if agent_id == "telegram-publisher" else "none"
            )
            _require_equal(
                issues,
                secret_access.get("mode"),
                expected_secret_mode,
                f"agents.list[{index}].secretAccess.mode",
            )

    _validate_market_data(_as_object(config.get("marketData"), "marketData"), issues)
    _validate_tools(_as_object(config.get("tools"), "tools"), "tools", issues)
    routing = config.get("routing")
    if isinstance(routing, dict):
        route_report = validate_routing(
            {
                "realtime": cast(list[list[str]], routing.get("realtime", [])),
                "code-audit": cast(list[list[str]], routing.get("code-audit", [])),
                "code-work-order": cast(list[list[str]], routing.get("code-work-order", [])),
            }
        )
        if not route_report.valid:
            for item in route_report.issues:
                issues.append(
                    ConfigValidationIssue(f"routing.{item.path}", f"{item.rule}: {item.message}")
                )
    else:
        issues.append(ConfigValidationIssue("routing", "routing section is required"))
    return ConfigValidationReport(valid=not issues, issues=tuple(issues))


def _validate_market_data(
    market_data: dict[str, object],
    issues: list[ConfigValidationIssue],
) -> None:
    backend = _as_object(market_data.get("backend"), "marketData.backend")
    _require_equal(issues, backend.get("kind"), "mt5", "marketData.backend.kind")
    _require_equal(issues, backend.get("mode"), "readonly", "marketData.backend.mode")

    symbols = _as_list(market_data.get("symbols"), "marketData.symbols")
    if not symbols:
        issues.append(ConfigValidationIssue("marketData.symbols", "expected at least one symbol"))
    for index, item in enumerate(symbols):
        symbol = _as_object(item, f"marketData.symbols[{index}]")
        canonical = symbol.get("canonical")
        aliases = symbol.get("aliases")
        if not isinstance(canonical, str) or not canonical:
            issues.append(
                ConfigValidationIssue(
                    f"marketData.symbols[{index}].canonical",
                    "expected non-empty canonical symbol",
                )
            )
        alias_list = aliases if isinstance(aliases, list) else None
        if not alias_list or not all(isinstance(alias, str) and alias for alias in alias_list):
            issues.append(
                ConfigValidationIssue(
                    f"marketData.symbols[{index}].aliases",
                    "expected non-empty string alias list",
                )
            )

    timeframes = _as_list(market_data.get("timeframes"), "marketData.timeframes")
    supported = {"M1", "M5", "M15", "H1", "H4", "D1"}
    has_supported_timeframes = all(
        isinstance(item, str) and item in supported for item in timeframes
    )
    if not timeframes or not has_supported_timeframes:
        issues.append(
            ConfigValidationIssue(
                "marketData.timeframes",
                f"expected supported timeframe list from {sorted(supported)!r}",
            )
        )

    storage = _as_object(market_data.get("storage"), "marketData.storage")
    for path_name in ("baseDir", "sqlitePath", "parquetDir"):
        value = storage.get(path_name)
        if not isinstance(value, str) or not value:
            issues.append(
                ConfigValidationIssue(
                    f"marketData.storage.{path_name}",
                    "expected non-empty string path",
                )
            )

    collection = _as_object(market_data.get("collection"), "marketData.collection")
    _require_positive_int(
        issues,
        collection.get("pollSeconds"),
        "marketData.collection.pollSeconds",
    )
    _require_positive_int(
        issues,
        collection.get("tickLookbackSeconds"),
        "marketData.collection.tickLookbackSeconds",
    )
    _require_positive_int(
        issues,
        collection.get("barLookbackCount"),
        "marketData.collection.barLookbackCount",
    )
    _require_positive_int(
        issues,
        collection.get("freshnessThresholdSeconds"),
        "marketData.collection.freshnessThresholdSeconds",
    )
    _require_positive_int(
        issues,
        collection.get("retryMaxAttempts"),
        "marketData.collection.retryMaxAttempts",
    )
    _require_positive_int(
        issues,
        collection.get("retryBackoffSeconds"),
        "marketData.collection.retryBackoffSeconds",
    )


def _validate_tools(
    tools: dict[str, object],
    prefix: str,
    issues: list[ConfigValidationIssue],
    *,
    is_super_advisor: bool = False,
    is_blueprint_coder: bool = False,
) -> None:
    expected_allow = (
        ["read", "session_status", "write", "edit", "apply_patch"]
        if is_blueprint_coder
        else ["read", "session_status"]
    )
    _require_equal(issues, tools.get("allow"), expected_allow, f"{prefix}.allow")
    expected_also_allow = ["message"] if is_super_advisor else None
    _require_equal(issues, tools.get("alsoAllow"), expected_also_allow, f"{prefix}.alsoAllow")
    deny = tools.get("deny")
    deny_values = set(cast(list[str], deny)) if isinstance(deny, list) else set()
    required_denies = {
        "group:runtime",
        "group:web",
        "group:ui",
        "group:automation",
        "group:plugins",
        "group:memory",
        "group:sessions",
        "process",
        "code_execution",
        "browser",
        "canvas",
        "gateway",
        "subagents",
    }
    if not is_blueprint_coder:
        # blueprint-coder manages these through exec.mode=allowlist and allowed_tools instead
        required_denies.update({"write", "edit", "apply_patch", "exec"})
    # group:messaging and message are only required in non-root, non-super-advisor scopes.
    # Root tools omits them so super-advisor (which inherits root) can use reply-scoped messaging.
    # Super-advisor uses alsoAllow:["message"] + actions.allow:["reply"] instead of deny.
    if prefix != "tools" and not is_super_advisor:
        required_denies.update({"group:messaging", "message"})
    missing = sorted(required_denies.difference(deny_values))
    if missing:
        issues.append(
            ConfigValidationIssue(
                f"{prefix}.deny", f"missing required denies: {', '.join(missing)}"
            )
        )
    exec_section = _as_object(tools.get("exec"), f"{prefix}.exec")
    expected_exec_mode = "allowlist" if is_blueprint_coder else "deny"
    _require_equal(issues, exec_section.get("mode"), expected_exec_mode, f"{prefix}.exec.mode")
    message = _as_object(tools.get("message"), f"{prefix}.message")
    _require_equal(
        issues,
        message.get("allowCrossContextSend"),
        False,
        f"{prefix}.message.allowCrossContextSend",
    )
    actions = _as_object(message.get("actions"), f"{prefix}.message.actions")
    expected_actions_allow = ["reply"] if is_super_advisor else []
    _require_equal(
        issues, actions.get("allow"), expected_actions_allow, f"{prefix}.message.actions.allow"
    )
    agent_to_agent = _as_object(tools.get("agentToAgent"), f"{prefix}.agentToAgent")
    _require_equal(issues, agent_to_agent.get("enabled"), False, f"{prefix}.agentToAgent.enabled")
    elevated = _as_object(tools.get("elevated"), f"{prefix}.elevated")
    _require_equal(issues, elevated.get("enabled"), False, f"{prefix}.elevated.enabled")
    sandbox = _as_object(tools.get("sandbox"), f"{prefix}.sandbox")
    sandbox_tools = _as_object(sandbox.get("tools"), f"{prefix}.sandbox.tools")
    _require_equal(
        issues,
        sandbox_tools.get("allow"),
        ["read", "session_status"],
        f"{prefix}.sandbox.tools.allow",
    )
    _require_equal(
        issues,
        sandbox_tools.get("alsoAllow"),
        expected_also_allow,
        f"{prefix}.sandbox.tools.alsoAllow",
    )
