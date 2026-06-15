from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.main_agent.planner import AgentTask, DependencyPlan
from openclaw_super_advisor.main_agent.runtime import (
    AgentCapability,
    HumanReleaseGateClosedError,
    MainRuntimeManager,
    RuntimeRequest,
    RuntimeValidationError,
)


def _capabilities() -> tuple[AgentCapability, ...]:
    return (
        AgentCapability("market-agent", ("market-data-coverage-audit",)),
        AgentCapability("macro-agent", ("fx-basket-analysis",)),
    )


def _task(
    task_id: str,
    agent_id: str = "market-agent",
    depends_on: tuple[str, ...] = (),
) -> AgentTask:
    return AgentTask(
        task_id=task_id,
        agent_id=agent_id,
        skill="fx-basket-analysis" if agent_id == "macro-agent" else "market-data-coverage-audit",
        depends_on=depends_on,
        input_schema={"type": "object"},
    )


def _request(plan: DependencyPlan) -> RuntimeRequest:
    return RuntimeRequest("req-1", plan, "idem-1")


def _plan(tasks: tuple[AgentTask, ...]) -> DependencyPlan:
    return DependencyPlan("plan-1", "unit-test", tasks, requires_human_gate=False)


def _dispatcher(task: AgentTask) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "agent_id": task.agent_id,
        "status": "COMPLETED",
        "evidence_reference": f"evidence-{task.task_id}",
        "payload": {f"evidence.{task.task_id}": "ok"},
        "provenance": {"source": "unit-test"},
    }


def test_runtime_orders_dependencies_and_dispatches_once(tmp_path: Path) -> None:
    calls: list[str] = []

    def dispatcher(task: AgentTask) -> dict[str, object]:
        calls.append(task.task_id)
        return _dispatcher(task)

    manager = MainRuntimeManager(_capabilities(), tmp_path, dispatcher)
    plan = _plan((_task("a"), _task("b", "macro-agent", ("a",))))

    report = manager.execute(_request(plan))
    second_report = manager.execute(_request(plan))

    assert report.status == "COMPLETED"
    assert report.completed_task_ids == ("a", "b")
    assert calls == ["a", "b"]
    assert second_report.dispatch_count == 2


def test_runtime_rejects_unknown_dependency(tmp_path: Path) -> None:
    manager = MainRuntimeManager(_capabilities(), tmp_path, _dispatcher)
    plan = _plan((_task("a", depends_on=("missing",)),))

    with pytest.raises(RuntimeValidationError, match="unknown dependency"):
        manager.execute(_request(plan))


def test_runtime_rejects_dependency_cycle(tmp_path: Path) -> None:
    manager = MainRuntimeManager(_capabilities(), tmp_path, _dispatcher)
    plan = _plan((_task("a", depends_on=("b",)), _task("b", depends_on=("a",))))

    with pytest.raises(RuntimeValidationError, match="cycle"):
        manager.execute(_request(plan))


def test_runtime_rejects_unavailable_capability(tmp_path: Path) -> None:
    manager = MainRuntimeManager(
        (AgentCapability("market-agent", ("other",)),),
        tmp_path,
        _dispatcher,
    )
    plan = _plan((_task("a"),))

    with pytest.raises(RuntimeValidationError, match="does not provide skill"):
        manager.execute(_request(plan))


def test_runtime_enforces_max_hops(tmp_path: Path) -> None:
    manager = MainRuntimeManager(_capabilities(), tmp_path, _dispatcher)
    plan = _plan((_task("a"), _task("b", "macro-agent")))

    with pytest.raises(RuntimeValidationError, match="max_hops"):
        manager.execute(RuntimeRequest("req-1", plan, "idem-1", max_hops=1))


def test_runtime_fails_closed_on_invalid_result(tmp_path: Path) -> None:
    def dispatcher(task: AgentTask) -> dict[str, object]:
        result = _dispatcher(task)
        result["evidence_reference"] = ""
        return result

    manager = MainRuntimeManager(_capabilities(), tmp_path, dispatcher)

    report = manager.execute(_request(_plan((_task("a"),))))

    assert report.status == "FAILED"
    assert report.failed_task_ids == ("a",)


def test_runtime_detects_conflict_deterministically(tmp_path: Path) -> None:
    def dispatcher(task: AgentTask) -> dict[str, object]:
        result = _dispatcher(task)
        result["payload"] = {"evidence.signal": "same" if task.task_id == "a" else "different"}
        return result

    manager = MainRuntimeManager(_capabilities(), tmp_path, dispatcher)
    plan = _plan((_task("a"), _task("b", "macro-agent", ("a",))))

    report = manager.execute(_request(plan))

    assert report.status == "CONFLICT"
    assert report.conflict_task_ids == ("b",)


def test_runtime_pause_resume_and_recovery(tmp_path: Path) -> None:
    calls: list[str] = []

    def dispatcher(task: AgentTask) -> dict[str, object]:
        calls.append(task.task_id)
        return _dispatcher(task)

    plan = _plan((_task("a"),))
    request = _request(plan)
    manager = MainRuntimeManager(_capabilities(), tmp_path, dispatcher)
    manager.pause(request)
    assert manager.execute(request).status == "PAUSED"

    resumed = manager.resume(request)
    recovered = MainRuntimeManager(_capabilities(), tmp_path, dispatcher).recover(request)

    assert resumed.status == "COMPLETED"
    assert recovered.completed_task_ids == ("a",)
    assert calls == ["a"]


def test_runtime_blocks_release_when_human_gate_closed(tmp_path: Path) -> None:
    manager = MainRuntimeManager(_capabilities(), tmp_path, _dispatcher)
    plan = _plan((_task("a"),))

    with pytest.raises(HumanReleaseGateClosedError):
        manager.execute(RuntimeRequest("req-1", plan, "idem-1", action="release"))
