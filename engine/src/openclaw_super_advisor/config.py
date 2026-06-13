from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .constants import CANONICAL_RUNTIME_AGENT_ID, SKILL_NAMES
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
    template_text = paths.config_template_path.read_text(encoding="utf-8")
    rendered = PLACEHOLDER_IN_STRING.sub(
        lambda match: _replace_string_placeholder(match, settings.raw_values), template_text
    )
    rendered = PLACEHOLDER_RAW.sub(
        lambda match: _replace_raw_placeholder(match, settings.raw_values), rendered
    )
    payload = json.loads(rendered)
    if not isinstance(payload, dict):
        raise ConfigValidationError("Rendered config must be a JSON object")
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

    hooks = _as_object(config.get("hooks"), "hooks")
    _require_equal(issues, hooks.get("enabled"), False, "hooks.enabled")
    _require_equal(issues, config.get("skills"), list(SKILL_NAMES), "skills")

    agents = _as_object(config.get("agents"), "agents")
    defaults = _as_object(agents.get("defaults"), "agents.defaults")
    _require_equal(
        issues, defaults.get("workspace"), str(paths.workspace_dir), "agents.defaults.workspace"
    )
    _require_equal(issues, defaults.get("skills"), list(SKILL_NAMES), "agents.defaults.skills")

    agent_list = _as_list(agents.get("list"), "agents.list")
    if len(agent_list) != 1:
        issues.append(ConfigValidationIssue("agents.list", "expected exactly one configured agent"))
    else:
        agent = _as_object(agent_list[0], "agents.list[0]")
        _require_equal(issues, agent.get("id"), CANONICAL_RUNTIME_AGENT_ID, "agents.list[0].id")
        _require_equal(
            issues, agent.get("workspace"), str(paths.workspace_dir), "agents.list[0].workspace"
        )
        _require_equal(issues, agent.get("skills"), list(SKILL_NAMES), "agents.list[0].skills")
        _validate_tools(
            _as_object(agent.get("tools"), "agents.list[0].tools"), "agents.list[0].tools", issues
        )

    _validate_tools(_as_object(config.get("tools"), "tools"), "tools", issues)
    return ConfigValidationReport(valid=not issues, issues=tuple(issues))


def _validate_tools(
    tools: dict[str, object],
    prefix: str,
    issues: list[ConfigValidationIssue],
) -> None:
    _require_equal(issues, tools.get("allow"), ["read", "session_status"], f"{prefix}.allow")
    deny = tools.get("deny")
    deny_values = set(cast(list[str], deny)) if isinstance(deny, list) else set()
    required_denies = {
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
    }
    missing = sorted(required_denies.difference(deny_values))
    if missing:
        issues.append(
            ConfigValidationIssue(
                f"{prefix}.deny", f"missing required denies: {', '.join(missing)}"
            )
        )
    exec_section = _as_object(tools.get("exec"), f"{prefix}.exec")
    _require_equal(issues, exec_section.get("mode"), "deny", f"{prefix}.exec.mode")
    message = _as_object(tools.get("message"), f"{prefix}.message")
    _require_equal(
        issues,
        message.get("allowCrossContextSend"),
        False,
        f"{prefix}.message.allowCrossContextSend",
    )
    actions = _as_object(message.get("actions"), f"{prefix}.message.actions")
    _require_equal(issues, actions.get("allow"), [], f"{prefix}.message.actions.allow")
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
