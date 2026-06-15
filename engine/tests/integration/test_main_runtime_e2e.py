from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.main_agent.planner import AgentTask, DependencyPlan
from openclaw_super_advisor.main_agent.runtime import (
    AgentCapability,
    MainRuntimeManager,
    RuntimeRequest,
)


def test_main_runtime_crash_restart_reuses_checkpoint(tmp_path: Path) -> None:
    calls: list[str] = []
    tasks = (
        AgentTask(
            task_id="collect",
            agent_id="market-agent",
            skill="market-data-coverage-audit",
            depends_on=(),
            input_schema={"type": "object"},
        ),
        AgentTask(
            task_id="review",
            agent_id="macro-agent",
            skill="fx-basket-analysis",
            depends_on=("collect",),
            input_schema={"type": "object"},
        ),
    )
    plan = DependencyPlan("plan-1", "runtime-e2e", tasks, requires_human_gate=False)
    request = RuntimeRequest("runtime-e2e", plan, "runtime-e2e-idempotency")
    capabilities = (
        AgentCapability("market-agent", ("market-data-coverage-audit",)),
        AgentCapability("macro-agent", ("fx-basket-analysis",)),
    )

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

    first = MainRuntimeManager(capabilities, tmp_path, dispatcher)
    first.execute(request)
    second = MainRuntimeManager(capabilities, tmp_path, dispatcher)

    recovered = second.recover(request)

    assert recovered.status == "COMPLETED"
    assert recovered.completed_task_ids == ("collect", "review")
    assert calls == ["collect", "review"]
    assert Path(recovered.checkpoint_path).exists()
    assert Path(recovered.audit_log_path).exists()
