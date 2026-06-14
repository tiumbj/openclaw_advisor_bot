"""MAIN Planner — decomposes user requests into specialist agent task plans.

MAIN must never call a specialist agent by hardcoded name in an ad-hoc manner.
Instead, the Planner interprets the request type and emits a structured DependencyPlan
that specifies which agents run, in what order, with what evidence requirements.

Blueprint §3.2: Planner and Dependency Resolution
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..constants import RUNTIME_AGENT_IDS


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    agent_id: str
    skill: str
    depends_on: tuple[str, ...]
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class DependencyPlan:
    plan_id: str
    request_type: str
    tasks: tuple[AgentTask, ...]
    requires_human_gate: bool


class MainPlanner:
    """Decomposes incoming requests into dependency-ordered agent task plans.

    Only specialist agents in RUNTIME_AGENT_IDS may be referenced.
    MAIN (super-advisor) does not appear in plans — it is the orchestrator.
    """

    SPECIALIST_IDS = frozenset(a for a in RUNTIME_AGENT_IDS if a != "super-advisor")

    def validate_agent(self, agent_id: str) -> None:
        if agent_id not in self.SPECIALIST_IDS:
            raise ValueError(
                f"agent {agent_id!r} is not a registered specialist; "
                f"MAIN cannot delegate to unknown agents"
            )

    def build_plan(self, plan_id: str, request_type: str, tasks: list[AgentTask]) -> DependencyPlan:
        for task in tasks:
            self.validate_agent(task.agent_id)
        requires_gate = any("release" in t.skill.lower() for t in tasks)
        return DependencyPlan(
            plan_id=plan_id,
            request_type=request_type,
            tasks=tuple(tasks),
            requires_human_gate=requires_gate,
        )
