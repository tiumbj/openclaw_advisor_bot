from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw_super_advisor.agent_registry import (
    AGENT_REGISTRY_DEGRADED,
    AGENT_REGISTRY_INVALID,
    AGENT_REGISTRY_READY,
    ManagerRegistryRuntime,
    build_agent_registry,
    validate_agent_registry,
)
from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.paths import build_paths


def _runtime(sample_project: Path) -> ManagerRegistryRuntime:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    return ManagerRegistryRuntime.load(paths, rendered)


def test_registry_validation_is_ready(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)

    report = validate_agent_registry(paths, rendered_config=rendered, require_generated_file=True)

    assert report.valid is True
    assert report.status == AGENT_REGISTRY_READY
    assert report.registry is not None
    assert report.registry.agent_count == 13
    assert report.registry.skill_count == 74
    assert report.missing_agent_count == 0
    assert report.duplicate_agent_count == 0
    assert report.registry_config_mismatch_count == 0


def test_registry_definition_sources_are_workspace_relative(sample_project: Path) -> None:
    registry = build_agent_registry(build_paths(sample_project))

    assert all(not Path(agent.definition_source).is_absolute() for agent in registry.agents)
    assert all(agent.definition_source.startswith("workspace/agents/") for agent in registry.agents)
    assert registry.generated_from == "workspace/agents"
    assert registry.generated_path == "config/agent_capability_registry.json"


@pytest.mark.parametrize(
    ("task_type", "expected_agent"),
    [
        ("xauusd_strategy_audit", "xau-strategy-auditor"),
        ("code_implementation", "blueprint-coder"),
        ("code_review", "system-coder-auditor"),
        ("security_review", "security-compliance-agent"),
        ("runtime_incident_root_cause", "failure-root-cause-agent"),
        ("runtime_reliability_monitoring", "reliability-watchdog-agent"),
        ("data_freshness_investigation", "market-data-integrity-agent"),
        ("pa_microstructure_analysis", "price-action-microstructure-agent"),
        ("intermarket_macro_analysis", "intermarket-macro-agent"),
        ("statistical_backtest_validation", "statistical-backtest-agent"),
        ("approved_telegram_publication", "telegram-publisher"),
        ("registry_consistency_check", "knowledge-skill-manager"),
    ],
)
def test_positive_routing_is_registry_backed(
    sample_project: Path, task_type: str, expected_agent: str
) -> None:
    decision = _runtime(sample_project).route_task(task_type)

    assert decision.selected_agent == expected_agent
    assert task_type in decision.reason_for_selection
    assert decision.required_review_chain


def test_manager_answers_agent_duties_from_registry(sample_project: Path) -> None:
    response = _runtime(sample_project).answer_agent_duties_query(
        "บอกหน้าที่ของ agent ทุกตัวในระบบ และบอกว่าแต่ละตัวห้ามทำอะไร"
    )

    assert response.source == "validated_agent_capability_registry"
    assert len(response.agents) == 13
    assert {agent["agent_id"] for agent in response.agents} == {
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
        "blueprint-coder",
    }
    assert all(agent["forbidden_actions"] for agent in response.agents)
    assert response.registry_version == "1.2.15"
    assert response.registry_hash


def test_negative_routing_fails_closed(sample_project: Path) -> None:
    runtime = _runtime(sample_project)

    assert runtime.route_task("code_implementation").selected_agent != "system-coder-auditor"
    assert runtime.route_task("code_implementation").selected_agent == "blueprint-coder"
    assert runtime.route_task("approved_telegram_publication").selected_agent != "blueprint-coder"
    assert runtime.route_task("pa_microstructure_analysis").selected_agent != "telegram-publisher"
    assert (
        runtime.route_task("xauusd_strategy_audit").selected_agent
        != "market-data-integrity-agent"
    )
    assert runtime.route_task("statistical_backtest_validation").selected_agent != "super-advisor"
    assert (
        runtime.route_task("intermarket_macro_analysis").selected_agent
        != "knowledge-skill-manager"
    )
    assert runtime.route_task("unknown_task_type").selected_agent is None


def test_unknown_agent_route_fails_closed(sample_project: Path) -> None:
    runtime = _runtime(sample_project)

    allowed, reason = runtime.validate_agent_route(
        "super-advisor", "unknown-agent", "code_review"
    )

    assert allowed is False
    assert "unknown agent id" in reason


def test_missing_agent_definition_fails_closed(sample_project: Path) -> None:
    agent_path = sample_project / "workspace" / "agents" / "telegram-publisher" / "AGENT.md"
    agent_path.unlink()
    paths = build_paths(sample_project)

    report = validate_agent_registry(paths)

    assert report.valid is False
    assert report.status == AGENT_REGISTRY_INVALID


def test_missing_registry_file_fails_closed(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    paths.agent_registry_path.unlink()
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)

    report = validate_agent_registry(paths, rendered_config=rendered, require_generated_file=True)
    assert report.status == AGENT_REGISTRY_DEGRADED

    with pytest.raises(RuntimeError, match="generated agent registry file is missing"):
        ManagerRegistryRuntime.load(paths, rendered)


def test_stale_registry_file_fails_closed(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    payload = json.loads(paths.agent_registry_path.read_text(encoding="utf-8"))
    payload["registry_hash"] = "stale-hash"
    paths.agent_registry_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)

    with pytest.raises(
        RuntimeError,
        match=r"generated registry does not match AGENT\.md definitions",
    ):
        ManagerRegistryRuntime.load(paths, rendered)


def test_unknown_frontmatter_field_fails_validation(sample_project: Path) -> None:
    agent_path = sample_project / "workspace" / "agents" / "super-advisor" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8").replace(
        "definition_version: 1.2.15",
        "unexpected_field: true\ndefinition_version: 1.2.15",
    )
    agent_path.write_text(text, encoding="utf-8")

    report = validate_agent_registry(build_paths(sample_project))

    assert report.valid is False
    assert report.status == AGENT_REGISTRY_INVALID
    assert any(issue.rule == "parse_error" for issue in report.issues)


def test_deterministic_registry_generation(sample_project: Path) -> None:
    paths = build_paths(sample_project)

    first = build_agent_registry(paths)
    second = build_agent_registry(paths)

    assert first.to_dict() == second.to_dict()
    assert first.registry_hash == second.registry_hash


def test_changing_responsibility_changes_definition_hash(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    before = build_agent_registry(paths).get_agent_capability("super-advisor").definition_hash
    agent_path = sample_project / "workspace" / "agents" / "super-advisor" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8").replace(
        "  - Consolidate specialist outputs and explain routing decisions.",
        "  - Consolidate specialist outputs, explain routing decisions, and emit audit evidence.",
    )
    agent_path.write_text(text, encoding="utf-8")
    after = build_agent_registry(build_paths(sample_project)).get_agent_capability(
        "super-advisor"
    ).definition_hash

    assert before != after


def test_changing_forbidden_action_changes_definition_hash(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    before = build_agent_registry(paths).get_agent_capability("telegram-publisher").definition_hash
    agent_path = sample_project / "workspace" / "agents" / "telegram-publisher" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8").replace(
        "  - access Telegram secrets directly",
        "  - access Telegram secrets or unapproved delivery transports directly",
    )
    agent_path.write_text(text, encoding="utf-8")
    after = build_agent_registry(build_paths(sample_project)).get_agent_capability(
        "telegram-publisher"
    ).definition_hash

    assert before != after


def test_changing_route_changes_definition_hash(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    before = (
        build_agent_registry(paths)
        .get_agent_capability("system-coder-auditor")
        .definition_hash
    )
    agent_path = sample_project / "workspace" / "agents" / "system-coder-auditor" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8").replace(
        "downstream_routes:\n  - super-advisor\n  - security-compliance-agent",
        "downstream_routes:\n  - security-compliance-agent\n  - super-advisor",
    )
    agent_path.write_text(text, encoding="utf-8")
    after = build_agent_registry(build_paths(sample_project)).get_agent_capability(
        "system-coder-auditor"
    ).definition_hash

    assert before != after


def test_whitespace_only_body_change_does_not_change_definition_hash(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    before = (
        build_agent_registry(paths)
        .get_agent_capability("knowledge-skill-manager")
        .definition_hash
    )
    agent_path = sample_project / "workspace" / "agents" / "knowledge-skill-manager" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8") + "\n"
    agent_path.write_text(text, encoding="utf-8")
    after = build_agent_registry(build_paths(sample_project)).get_agent_capability(
        "knowledge-skill-manager"
    ).definition_hash

    assert before == after


def test_nonexistent_route_target_fails_validation(sample_project: Path) -> None:
    agent_path = sample_project / "workspace" / "agents" / "xau-strategy-auditor" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8").replace(
        "downstream_routes:\n  - super-advisor",
        "downstream_routes:\n  - nonexistent-agent",
    )
    agent_path.write_text(text, encoding="utf-8")
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)

    report = validate_agent_registry(paths, rendered_config=rendered)

    assert report.valid is False
    assert any(issue.rule == "unknown_agent" for issue in report.issues)


def test_agents_cannot_self_approve(sample_project: Path) -> None:
    runtime = _runtime(sample_project)

    assert runtime.get_agent_capability("blueprint-coder").self_approval_allowed is False
    assert runtime.get_agent_capability("system-coder-auditor").self_approval_allowed is False
    assert runtime.get_agent_capability("security-compliance-agent").self_approval_allowed is False
