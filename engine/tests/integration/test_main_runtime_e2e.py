from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.main_agent.planner import AgentTask
from openclaw_super_advisor.main_agent.registry_runtime import build_registry_snapshot
from openclaw_super_advisor.main_agent.runtime import (
    MainRuntimeManager,
    RuntimeRequest,
)
from openclaw_super_advisor.paths import build_paths


def test_main_runtime_crash_restart_reuses_checkpoint(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    snapshot = build_registry_snapshot(paths, rendered)
    manager = MainRuntimeManager.from_registry_snapshot(snapshot, tmp_path, lambda _task: {})
    tasks = [
        AgentTask(
            task_id="collect",
            agent_id="market-data-integrity-agent",
            skill="stale-data-detection",
            depends_on=(),
            input_schema={"type": "object"},
            task_type="data_freshness_investigation",
            requested_action="validate",
        ),
        AgentTask(
            task_id="review",
            agent_id="intermarket-macro-agent",
            skill="fx-basket-analysis",
            depends_on=("collect",),
            input_schema={"type": "object"},
            task_type="intermarket_macro_analysis",
            requested_action="analyze",
        ),
    ]
    plan = manager.plan_request(
        "plan-1",
        "data_freshness_investigation",
        tasks,
        available_inputs={
            "collect": {
                "task_id": "collect",
                "symbol": "XAUUSD",
                "source_system": "integration-test",
                "evidence_package": {"window": "current-session"},
            },
            "review": {
                "task_id": "review",
                "symbol": "DXY",
                "evidence_package": {"window": "macro-session"},
                "source_freshness": "fresh",
            },
        },
    )
    request = RuntimeRequest("runtime-e2e", plan, "runtime-e2e-idempotency")

    def dispatcher(task: AgentTask) -> dict[str, object]:
        calls.append(task.task_id)
        return {
            "task_id": task.task_id,
            "agent_id": task.agent_id,
            "status": "COMPLETED",
            "evidence_reference": f"evidence-{task.task_id}",
            "payload": {f"evidence.{task.task_id}": "ok"},
            "provenance": {"source": "integration-test"},
        }

    first = MainRuntimeManager.from_registry_snapshot(snapshot, tmp_path, dispatcher)
    first.execute(request)
    second = MainRuntimeManager.from_registry_snapshot(snapshot, tmp_path, dispatcher)

    recovered = second.recover(request)

    assert recovered.status == "COMPLETED"
    assert recovered.completed_task_ids == ("collect", "review")
    assert calls == ["collect", "review"]
    assert Path(recovered.checkpoint_path).exists()
    assert Path(recovered.audit_log_path).exists()
