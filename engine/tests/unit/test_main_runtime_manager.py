from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.main_agent.planner import AgentTask, DependencyPlan
from openclaw_super_advisor.main_agent.registry_runtime import build_registry_snapshot
from openclaw_super_advisor.main_agent.runtime import (
    HumanReleaseGateClosedError,
    MainRuntimeManager,
    RuntimeRequest,
    RuntimeValidationError,
)
from openclaw_super_advisor.paths import build_paths


def _runtime(sample_project: Path, checkpoint_dir: Path) -> MainRuntimeManager:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    snapshot = build_registry_snapshot(paths, rendered)
    return MainRuntimeManager.from_registry_snapshot(snapshot, checkpoint_dir, _dispatcher)


def _task(
    task_id: str,
    *,
    agent_id: str = "market-data-integrity-agent",
    skill: str = "stale-data-detection",
    task_type: str = "data_freshness_investigation",
    requested_action: str = "validate",
    depends_on: tuple[str, ...] = (),
) -> AgentTask:
    return AgentTask(
        task_id=task_id,
        agent_id=agent_id,
        skill=skill,
        depends_on=depends_on,
        input_schema={"type": "object"},
        task_type=task_type,
        requested_action=requested_action,
    )


def _plan(manager: MainRuntimeManager, tasks: list[AgentTask]) -> DependencyPlan:
    available_inputs: dict[str, dict[str, object]] = {}
    for task in tasks:
        agent = manager.registry_snapshot.get_agent(task.agent_id)
        inputs: dict[str, object] = {}
        for field in agent.required_input_schema.get("required_fields", []):
            if field == "task_id":
                inputs[field] = task.task_id
            elif "files" in field:
                inputs[field] = ["engine/src"]
            elif field == "evidence_package":
                inputs[field] = {"source": "runtime unit test"}
            elif field == "source_system":
                inputs[field] = "unit-test"
            elif field == "correlation_inputs":
                inputs[field] = {"symbol": "DXY"}
            elif field == "macro_context":
                inputs[field] = "risk-off"
            elif field == "symbol":
                inputs[field] = "XAUUSD"
            elif field == "audit_scope":
                inputs[field] = "runtime unit test"
            else:
                inputs[field] = "placeholder"
        available_inputs[task.task_id] = inputs
    return manager.plan_request(
        "plan-1",
        tasks[0].task_type or "unit-test",
        tasks,
        available_inputs=available_inputs,
    )


def _request(plan: DependencyPlan) -> RuntimeRequest:
    return RuntimeRequest("req-1", plan, "idem-1")


def _dispatcher(task: AgentTask) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "agent_id": task.agent_id,
        "status": "COMPLETED",
        "evidence_reference": f"evidence-{task.task_id}",
        "payload": {f"evidence.{task.task_id}": "ok"},
        "provenance": {"source": "unit-test"},
    }


def test_runtime_orders_dependencies_and_dispatches_once(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def dispatcher(task: AgentTask) -> dict[str, object]:
        calls.append(task.task_id)
        return _dispatcher(task)

    manager = _runtime(sample_project, tmp_path)
    manager.dispatcher = dispatcher
    plan = _plan(
        manager,
        [
            _task("a"),
            _task(
                "b",
                agent_id="intermarket-macro-agent",
                skill="fx-basket-analysis",
                task_type="intermarket_macro_analysis",
                requested_action="analyze",
                depends_on=("a",),
            ),
        ],
    )

    report = manager.execute(_request(plan))
    second_report = manager.execute(_request(plan))

    assert report.status == "COMPLETED"
    assert report.completed_task_ids == ("a", "b")
    assert calls == ["a", "b"]
    assert second_report.dispatch_count == 2


def test_runtime_rejects_unknown_dependency(sample_project: Path, tmp_path: Path) -> None:
    manager = _runtime(sample_project, tmp_path)
    plan = DependencyPlan(
        "plan-1",
        "unit-test",
        (_task("a", depends_on=("missing",)),),
        requires_human_gate=False,
        registry_schema_version=manager.registry_snapshot.schema_version,
        registry_definition_hash=manager.registry_snapshot.definition_hash,
    )

    with pytest.raises(RuntimeValidationError, match="unknown dependency"):
        manager.execute(_request(plan))


def test_runtime_rejects_dependency_cycle(sample_project: Path, tmp_path: Path) -> None:
    manager = _runtime(sample_project, tmp_path)
    plan = DependencyPlan(
        "plan-1",
        "unit-test",
        (_task("a", depends_on=("b",)), _task("b", depends_on=("a",))),
        requires_human_gate=False,
        registry_schema_version=manager.registry_snapshot.schema_version,
        registry_definition_hash=manager.registry_snapshot.definition_hash,
    )

    with pytest.raises(RuntimeValidationError, match="cycle"):
        manager.execute(_request(plan))


def test_runtime_rejects_unavailable_capability(sample_project: Path, tmp_path: Path) -> None:
    manager = _runtime(sample_project, tmp_path)
    plan = DependencyPlan(
        "plan-1",
        "unit-test",
        (_task("a", agent_id="unknown-agent"),),
        requires_human_gate=False,
        registry_schema_version=manager.registry_snapshot.schema_version,
        registry_definition_hash=manager.registry_snapshot.definition_hash,
    )

    with pytest.raises(RuntimeValidationError, match="unavailable capability"):
        manager.execute(_request(plan))


def test_runtime_enforces_max_hops(sample_project: Path, tmp_path: Path) -> None:
    manager = _runtime(sample_project, tmp_path)
    plan = _plan(
        manager,
        [
            _task("a"),
            _task(
                "b",
                agent_id="intermarket-macro-agent",
                skill="fx-basket-analysis",
                task_type="intermarket_macro_analysis",
                requested_action="analyze",
            ),
        ],
    )

    with pytest.raises(RuntimeValidationError, match="max_hops"):
        manager.execute(RuntimeRequest("req-1", plan, "idem-1", max_hops=1))


def test_runtime_fails_closed_on_invalid_result(sample_project: Path, tmp_path: Path) -> None:
    def dispatcher(task: AgentTask) -> dict[str, object]:
        result = _dispatcher(task)
        result["evidence_reference"] = ""
        return result

    manager = _runtime(sample_project, tmp_path)
    manager.dispatcher = dispatcher

    report = manager.execute(_request(_plan(manager, [_task("a")])))

    assert report.status == "FAILED"
    assert report.failed_task_ids == ("a",)


def test_runtime_detects_conflict_deterministically(sample_project: Path, tmp_path: Path) -> None:
    def dispatcher(task: AgentTask) -> dict[str, object]:
        result = _dispatcher(task)
        result["payload"] = {"evidence.signal": "same" if task.task_id == "a" else "different"}
        return result

    manager = _runtime(sample_project, tmp_path)
    manager.dispatcher = dispatcher
    plan = _plan(
        manager,
        [
            _task("a"),
            _task(
                "b",
                agent_id="intermarket-macro-agent",
                skill="fx-basket-analysis",
                task_type="intermarket_macro_analysis",
                requested_action="analyze",
                depends_on=("a",),
            ),
        ],
    )

    report = manager.execute(_request(plan))

    assert report.status == "CONFLICT"
    assert report.conflict_task_ids == ("b",)


def test_runtime_pause_resume_and_recovery(sample_project: Path, tmp_path: Path) -> None:
    calls: list[str] = []

    def dispatcher(task: AgentTask) -> dict[str, object]:
        calls.append(task.task_id)
        return _dispatcher(task)

    manager = _runtime(sample_project, tmp_path)
    manager.dispatcher = dispatcher
    plan = _plan(manager, [_task("a")])
    request = _request(plan)
    manager.pause(request)
    assert manager.execute(request).status == "PAUSED"

    resumed = manager.resume(request)
    recovered = _runtime(sample_project, tmp_path).recover(request)

    assert resumed.status == "COMPLETED"
    assert recovered.completed_task_ids == ("a",)
    assert calls == ["a"]


def test_runtime_blocks_release_when_human_gate_closed(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    manager = _runtime(sample_project, tmp_path)
    plan = _plan(manager, [_task("a")])

    with pytest.raises(HumanReleaseGateClosedError):
        manager.execute(RuntimeRequest("req-1", plan, "idem-1", action="release"))
