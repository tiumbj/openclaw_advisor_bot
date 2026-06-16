from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from openclaw_super_advisor.agent_registry import AGENT_REGISTRY_INVALID, AGENT_REGISTRY_READY
from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.health import run_health_check
from openclaw_super_advisor.main_agent.planner import AgentTask, DependencyPlan, MainPlanner
from openclaw_super_advisor.main_agent.registry_runtime import (
    RegistrySnapshot,
    build_registry_snapshot,
)
from openclaw_super_advisor.main_agent.router import AgentRouter
from openclaw_super_advisor.main_agent.runtime import MainRuntimeManager, RuntimeValidationError
from openclaw_super_advisor.paths import build_paths


def _snapshot(sample_project: Path) -> RegistrySnapshot:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    return build_registry_snapshot(paths, rendered)


def _runtime(sample_project: Path, checkpoint_dir: Path) -> MainRuntimeManager:
    snapshot = _snapshot(sample_project)
    return MainRuntimeManager.from_registry_snapshot(
        snapshot,
        checkpoint_dir,
        lambda task: {
            "task_id": task.task_id,
            "agent_id": task.agent_id,
            "status": "COMPLETED",
            "evidence_reference": f"evidence-{task.task_id}",
            "payload": {},
            "provenance": {"source": "runtime-registry-test"},
        },
    )


def _load_registry_payload(sample_project: Path) -> dict[str, Any]:
    paths = build_paths(sample_project)
    return json.loads(paths.agent_registry_path.read_text(encoding="utf-8"))


def _write_registry_payload(sample_project: Path, payload: dict[str, Any]) -> None:
    paths = build_paths(sample_project)
    paths.agent_registry_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _runtime_invalid_state_assertions(
    sample_project: Path,
    tmp_path: Path,
    *,
    expected_error_substring: str,
    rendered_mutator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    if rendered_mutator is not None:
        rendered = rendered_mutator(rendered)
    snapshot = build_registry_snapshot(paths, rendered)
    runtime = MainRuntimeManager.from_registry_snapshot(snapshot, tmp_path, lambda _task: {})
    health = run_health_check(paths)
    combined_errors = snapshot.validation_errors + health.registry_validation_errors

    assert snapshot.state != AGENT_REGISTRY_READY
    assert runtime.registry_loaded_by_main_runtime is False
    assert health.agent_registry_status != AGENT_REGISTRY_READY
    assert health.registry_loaded_by_main_runtime is False
    assert any(expected_error_substring in error for error in combined_errors)

    with pytest.raises(RuntimeValidationError, match="planner is unavailable"):
        runtime.plan_request("invalid", "code_review", [])
    with pytest.raises(RuntimeValidationError, match="router is unavailable"):
        runtime.route_plan(
            DependencyPlan("invalid-plan", "code_review", (), False),
            {},
        )
    query = runtime.handle_manager_query("มี agent อะไรบ้าง")
    assert query.query_type == "registry_unavailable"
    assert expected_error_substring in str(query.response.get("error", ""))
    assert "source=" not in str(query.response)
    assert "OPENAI_API_KEY" not in str(query.response)
    assert "RUNTIME_AGENT_IDS" not in str(query.response)


def _replace_in_agent(
    sample_project: Path,
    agent_id: str,
    old: str,
    new: str,
) -> None:
    agent_path = sample_project / "workspace" / "agents" / agent_id / "AGENT.md"
    agent_path.write_text(
        agent_path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )


def test_main_planner_uses_registry_not_runtime_ids(sample_project: Path) -> None:
    snapshot = _snapshot(sample_project)
    super_advisor = snapshot.get_agent("super-advisor")
    custom_agent = replace(
        snapshot.get_agent("market-data-integrity-agent"),
        agent_id="custom-registry-agent",
        display_name="Custom Registry Agent",
        accepted_task_types=("custom_task",),
        allowed_actions=("perform custom audit",),
        upstream_routes=("super-advisor",),
        downstream_routes=("super-advisor",),
        required_reviewers=("super-advisor",),
    )
    custom_snapshot = replace(
        snapshot,
        agents=(
            replace(
                super_advisor,
                downstream_routes=(
                    *super_advisor.downstream_routes,
                    "custom-registry-agent",
                ),
            ),
            custom_agent,
        ),
    )
    planner = MainPlanner(custom_snapshot)

    plan = planner.build_plan(
        "custom-plan",
        "custom_task",
        [
            AgentTask(
                task_id="custom-task",
                agent_id="custom-registry-agent",
                skill=custom_agent.owned_skills[0],
                depends_on=(),
                input_schema={"type": "object"},
                task_type="custom_task",
                requested_action="perform",
            )
        ],
        available_inputs={
            "custom-task": {
                "task_id": "custom-task",
                "source_system": "unit-test",
                "evidence_package": {"symbol": "XAUUSD"},
            }
        },
    )

    assert plan.registry_definition_hash == custom_snapshot.definition_hash
    assert plan.planning_decisions[0].selected_agent == "custom-registry-agent"


def test_agent_router_uses_registry_authority_not_static_allowlists(sample_project: Path) -> None:
    snapshot = _snapshot(sample_project)
    super_advisor = snapshot.get_agent("super-advisor")
    custom_agent = replace(
        snapshot.get_agent("market-data-integrity-agent"),
        agent_id="custom-route-agent",
        display_name="Custom Route Agent",
        accepted_task_types=("custom_route_task",),
        allowed_actions=("perform custom route",),
        upstream_routes=("super-advisor",),
        downstream_routes=("super-advisor",),
        required_reviewers=("super-advisor",),
    )
    custom_snapshot = replace(
        snapshot,
        agents=(
            replace(
                super_advisor,
                downstream_routes=(
                    *super_advisor.downstream_routes,
                    "custom-route-agent",
                ),
            ),
            custom_agent,
        ),
    )
    planner = MainPlanner(custom_snapshot)
    router = AgentRouter(custom_snapshot)
    task = AgentTask(
        task_id="route-task",
        agent_id="custom-route-agent",
        skill=custom_agent.owned_skills[0],
        depends_on=(),
        input_schema={"type": "object"},
        task_type="custom_route_task",
        requested_action="perform",
    )
    plan = planner.build_plan(
        "route-plan",
        "custom_route_task",
        [task],
        available_inputs={
            "route-task": {
                "task_id": "route-task",
                "source_system": "unit-test",
                "evidence_package": {"symbol": "XAUUSD"},
            }
        },
    )

    routed = router.route(plan, task, {"payload": "ok"})

    assert routed.agent_id == "custom-route-agent"
    assert routed.route_validation_result == "route_allowed"
    assert routed.registry_definition_hash == custom_snapshot.definition_hash


def test_main_runtime_query_path_is_registry_backed(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    runtime = _runtime(sample_project, tmp_path)

    duties = runtime.handle_manager_query(
        "บอกหน้าที่ของ agent ทุกตัวในระบบ และบอกว่าแต่ละตัวห้ามทำอะไร"
    )
    routing = runtime.handle_manager_query(
        "งานตรวจ code production-grade ควรส่งให้ agent ตัวไหน เพราะอะไร "
        "ใครต้อง review ต่อ และ agent ที่ได้รับงานห้ามทำอะไรบ้าง"
    )
    ambiguous = runtime.handle_manager_query("ส่งงานนี้ให้ agent อะไรก็ได้ที่ชื่อดูใกล้เคียง")

    assert duties.query_type == "agent_catalog_query"
    assert len(duties.response["agents"]) == 13
    assert duties.response["registry_definition_hash"] == runtime.registry_snapshot.definition_hash
    assert routing.query_type == "routing_explanation"
    assert routing.response["selected_agent"] == "system-coder-auditor"
    assert routing.response["required_review_chain"]
    assert routing.response["forbidden_actions"]
    assert ambiguous.response["selected_agent"] is None
    assert "ambiguous" in str(ambiguous.response["error"]).lower()


def test_stale_plan_fails_closed(sample_project: Path, tmp_path: Path) -> None:
    runtime_a = _runtime(sample_project, tmp_path / "a")
    task = AgentTask(
        task_id="code-review-task",
        agent_id="system-coder-auditor",
        skill="python-pipeline-micro-audit",
        depends_on=(),
        input_schema={"type": "object"},
        task_type="code_review",
        requested_action="audit",
    )
    plan = runtime_a.plan_request(
        "stale-plan",
        "code_review",
        [task],
        available_inputs={
            "code-review-task": {
                "task_id": "code-review-task",
                "audit_scope": "prod code review",
                "source_files": ["engine/src"],
            }
        },
    )
    snapshot_b = replace(runtime_a.registry_snapshot, definition_hash="different-registry-hash")
    runtime_b = MainRuntimeManager.from_registry_snapshot(
        snapshot_b,
        tmp_path / "b",
        runtime_a.dispatcher,
    )

    with pytest.raises(ValueError, match="stale registry plan"):
        runtime_b.route_plan(plan, {"code-review-task": {}})


def test_missing_registry_runtime_fails_closed(sample_project: Path, tmp_path: Path) -> None:
    paths = build_paths(sample_project)
    paths.agent_registry_path.unlink()
    super_path = sample_project / "workspace" / "agents" / "super-advisor" / "AGENT.md"
    super_path.unlink()
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    snapshot = build_registry_snapshot(paths, rendered)
    runtime = MainRuntimeManager.from_registry_snapshot(
        snapshot,
        tmp_path,
        lambda _task: {},
    )
    health = run_health_check(paths)

    assert snapshot.state == AGENT_REGISTRY_INVALID
    assert health.agent_registry_valid is False
    assert health.registry_loaded_by_main_runtime is False
    with pytest.raises(RuntimeValidationError, match="planner is unavailable"):
        runtime.plan_request("missing", "code_review", [])
    assert "error" in runtime.handle_manager_query("มี agent อะไรบ้าง").response


def test_malformed_registry_runtime_fails_closed(sample_project: Path, tmp_path: Path) -> None:
    agent_path = sample_project / "workspace" / "agents" / "blueprint-coder" / "AGENT.md"
    text = agent_path.read_text(encoding="utf-8").replace(
        "downstream_routes:\n  - system-coder-auditor",
        "downstream_routes:\n  - nonexistent-agent",
    )
    agent_path.write_text(text, encoding="utf-8")
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    snapshot = build_registry_snapshot(paths, rendered)
    runtime = MainRuntimeManager.from_registry_snapshot(snapshot, tmp_path, lambda _task: {})

    assert snapshot.state == AGENT_REGISTRY_INVALID
    with pytest.raises(RuntimeValidationError, match="planner is unavailable"):
        runtime.plan_request("invalid", "code_implementation", [])


@pytest.mark.parametrize(
    ("case_name", "mutator", "expected_error_substring", "rendered_mutator"),
    [
        (
            "registry_file_missing",
            lambda sample_project: build_paths(sample_project).agent_registry_path.unlink(),
            "generated agent registry file is missing",
            None,
        ),
        (
            "malformed_json",
            lambda sample_project: build_paths(sample_project).agent_registry_path.write_text(
                "{\n",
                encoding="utf-8",
            ),
            "not valid JSON",
            None,
        ),
        (
            "unsupported_schema_version",
            lambda sample_project: (
                lambda payload: (
                    payload.__setitem__("schema_version", "9.9.9"),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "schema_version is unsupported",
            None,
        ),
        (
            "missing_schema_version",
            lambda sample_project: (
                lambda payload: (
                    payload.pop("schema_version"),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "schema_version is required",
            None,
        ),
        (
            "missing_registry_hash",
            lambda sample_project: (
                lambda payload: (
                    payload.pop("registry_hash"),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "registry_hash is required",
            None,
        ),
        (
            "invalid_registry_hash",
            lambda sample_project: (
                lambda payload: (
                    payload.__setitem__(
                        "registry_hash",
                        "0000000000000000000000000000000000000000000000000000000000000000",
                    ),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "registry_hash does not match its content",
            None,
        ),
        (
            "stale_registry_hash",
            lambda sample_project: _replace_in_agent(
                sample_project,
                "super-advisor",
                "  - Consolidate specialist outputs and explain routing decisions.",
                (
                    "  - Consolidate specialist outputs, explain routing decisions, "
                    "and preserve stale-hash detection evidence."
                ),
            ),
            "does not match AGENT.md definitions",
            None,
        ),
        (
            "duplicate_agent_id",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__(
                        "agent_id",
                        payload["agents"][0]["agent_id"],
                    ),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "duplicate agent ids",
            None,
        ),
        (
            "missing_super_advisor_definition",
            lambda sample_project: (
                lambda payload: (
                    payload.__setitem__(
                        "agents",
                        [
                            agent
                            for agent in payload["agents"]
                            if agent["agent_id"] != "super-advisor"
                        ],
                    ),
                    payload.__setitem__("agent_count", 12),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "must include super-advisor",
            None,
        ),
        (
            "missing_specialist_definition",
            lambda sample_project: (
                lambda payload: (
                    payload.__setitem__(
                        "agents",
                        [
                            agent
                            for agent in payload["agents"]
                            if agent["agent_id"] != "blueprint-coder"
                        ],
                    ),
                    payload.__setitem__("agent_count", 12),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "agent set does not match AGENT.md definitions",
            None,
        ),
        (
            "route_source_unknown",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][0].__setitem__("upstream_routes", ["ghost-agent"]),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "references unknown agent 'ghost-agent'",
            None,
        ),
        (
            "route_target_unknown",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__("downstream_routes", ["ghost-agent"]),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "references unknown agent 'ghost-agent'",
            None,
        ),
        (
            "forbidden_self_route",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__(
                        "downstream_routes",
                        [payload["agents"][1]["agent_id"]],
                    ),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "may not route to itself",
            None,
        ),
        (
            "contradictory_actions",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__("allowed_actions", ["analyze"]),
                    payload["agents"][1].__setitem__("forbidden_actions", ["analyze"]),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "allowed_actions and forbidden_actions conflict",
            None,
        ),
        (
            "accepted_task_types_missing",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].pop("accepted_task_types"),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "accepted_task_types' is required",
            None,
        ),
        (
            "accepted_task_types_empty",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__("accepted_task_types", []),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "accepted_task_types' must be a non-empty list",
            None,
        ),
        (
            "responsibilities_missing",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].pop("primary_responsibilities"),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "primary_responsibilities' is required",
            None,
        ),
        (
            "responsibilities_empty",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__("primary_responsibilities", []),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "primary_responsibilities' must be a non-empty list",
            None,
        ),
        (
            "required_reviewer_missing",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].pop("required_reviewers"),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "required_reviewers' is required",
            None,
        ),
        (
            "required_reviewer_nonexistent",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__("required_reviewers", ["ghost-agent"]),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "references unknown agent 'ghost-agent'",
            None,
        ),
        (
            "self_approval_reviewer_chain",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__(
                        "required_reviewers",
                        [payload["agents"][1]["agent_id"]],
                    ),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "reviewer chain may not self-approve",
            None,
        ),
        (
            "invalid_definition_source_path",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__(
                        "definition_source",
                        "C:/outside/AGENT.md",
                    ),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "must stay within workspace/agents",
            None,
        ),
        (
            "definition_source_path_traversal",
            lambda sample_project: (
                lambda payload: (
                    payload["agents"][1].__setitem__(
                        "definition_source",
                        "../outside/AGENT.md",
                    ),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "may not contain parent traversal",
            None,
        ),
        (
            "registry_config_mismatch",
            lambda sample_project: _replace_in_agent(
                sample_project,
                "knowledge-skill-manager",
                "  - experiment-outcome-recording",
                "  - experiment-outcome-recording\n  - synthetic-registry-drift-skill",
            ),
            "rendered config skills must match the registry",
            None,
        ),
        (
            "registry_agent_markdown_mismatch",
            lambda sample_project: _replace_in_agent(
                sample_project,
                "telegram-publisher",
                "  - perform market analysis",
                (
                    "  - perform market analysis and authorize research overrides"
                ),
            ),
            "does not match AGENT.md definitions",
            None,
        ),
        (
            "registered_agent_count_mismatch",
            lambda sample_project: (
                lambda payload: (
                    payload.__setitem__("agent_count", 99),
                    _write_registry_payload(sample_project, payload),
                )
            )(_load_registry_payload(sample_project)),
            "agent_count must match the number of agents",
            None,
        ),
    ],
)
def test_malformed_main_runtime_matrix_cases(
    sample_project: Path,
    tmp_path: Path,
    case_name: str,
    mutator: Callable[[Path], Any],
    expected_error_substring: str,
    rendered_mutator: Callable[[dict[str, Any]], dict[str, Any]] | None,
) -> None:
    mutator(sample_project)
    _runtime_invalid_state_assertions(
        sample_project,
        tmp_path / case_name,
        expected_error_substring=expected_error_substring,
        rendered_mutator=rendered_mutator,
    )
