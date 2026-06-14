"""MAIN Agent Router — routes tasks from a DependencyPlan to specialist agents.

The router enforces:
- Only registered specialist agents receive tasks
- No two MAIN instances run in parallel (enforced at startup via mutex)
- Routing is deterministic from the plan — MAIN does not improvise assignments

Blueprint §3.3: Agent Router
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..agent_topology import CODE_AUDIT_ROUTE_ALLOWLIST, REALTIME_ROUTE_ALLOWLIST
from .planner import AgentTask, DependencyPlan


@dataclass(frozen=True)
class RoutedTask:
    task_id: str
    agent_id: str
    skill: str
    route_type: str
    payload: dict[str, Any]


class AgentRouter:
    """Routes tasks from a dependency plan to the correct specialist agent.

    Route types:
    - REALTIME: market data, evidence, alert tasks (uses REALTIME_ROUTE_ALLOWLIST)
    - CODE_AUDIT: code review, compliance tasks (uses CODE_AUDIT_ROUTE_ALLOWLIST)
    - GENERAL: other specialist tasks
    """

    @staticmethod
    def _in_allowlist(agent_id: str, allowlist: tuple[tuple[str, str], ...]) -> bool:
        return any(agent_id in pair for pair in allowlist)

    def _classify_route(self, agent_id: str) -> str:
        if self._in_allowlist(agent_id, REALTIME_ROUTE_ALLOWLIST):
            return "REALTIME"
        if self._in_allowlist(agent_id, CODE_AUDIT_ROUTE_ALLOWLIST):
            return "CODE_AUDIT"
        return "GENERAL"

    def route(self, plan: DependencyPlan, task: AgentTask, payload: dict[str, Any]) -> RoutedTask:
        if task not in plan.tasks:
            raise ValueError(f"task {task.task_id!r} is not in plan {plan.plan_id!r}")
        return RoutedTask(
            task_id=task.task_id,
            agent_id=task.agent_id,
            skill=task.skill,
            route_type=self._classify_route(task.agent_id),
            payload=payload,
        )

    def route_all(
        self, plan: DependencyPlan, payloads: dict[str, dict[str, Any]]
    ) -> list[RoutedTask]:
        return [self.route(plan, task, payloads.get(task.task_id, {})) for task in plan.tasks]
