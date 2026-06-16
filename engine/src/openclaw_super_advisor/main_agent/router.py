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

from .planner import AgentTask, DependencyPlan
from .registry_runtime import RegistrySnapshot


@dataclass(frozen=True)
class RoutedTask:
    task_id: str
    agent_id: str
    skill: str
    route_type: str
    payload: dict[str, Any]
    registry_schema_version: str
    registry_definition_hash: str
    selected_agent_definition_version: str
    route_validation_result: str
    required_reviewers: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    human_release_gate_required: bool


class AgentRouter:
    """Routes tasks from a dependency plan to the correct specialist agent.

    Route types are reporting labels only; registry contracts remain the source of authority.
    """

    def __init__(
        self,
        registry_snapshot: RegistrySnapshot,
        *,
        source_agent: str = "super-advisor",
    ) -> None:
        self.registry_snapshot = registry_snapshot
        self.source_agent = source_agent

    @staticmethod
    def _classify_route(task_type: str) -> str:
        if any(token in task_type for token in ("market", "data", "intermarket", "microstructure")):
            return "REALTIME"
        if any(token in task_type for token in ("code", "security", "review")):
            return "CODE_AUDIT"
        return "GENERAL"

    def route(self, plan: DependencyPlan, task: AgentTask, payload: dict[str, Any]) -> RoutedTask:
        self.registry_snapshot.require_ready()
        if task not in plan.tasks:
            raise ValueError(f"task {task.task_id!r} is not in plan {plan.plan_id!r}")
        if plan.registry_definition_hash != self.registry_snapshot.definition_hash:
            raise ValueError("stale registry plan cannot be routed under a different registry hash")
        agent = self.registry_snapshot.get_agent(task.agent_id)
        task_type = task.task_type or plan.request_type
        if task_type not in agent.accepted_task_types:
            raise ValueError(f"agent {task.agent_id!r} does not accept task_type {task_type!r}")
        source_agent = self.registry_snapshot.get_agent(self.source_agent)
        if task.agent_id not in source_agent.downstream_routes:
            raise ValueError(
                f"route from {self.source_agent!r} to {task.agent_id!r} is not allowed"
            )
        requested_action = task.requested_action.strip().lower()
        if requested_action and any(
            requested_action in forbidden.lower() for forbidden in agent.forbidden_actions
        ):
            raise ValueError(f"forbidden action requested for {task.agent_id!r}")
        if requested_action and not any(
            requested_action in allowed.lower() for allowed in agent.allowed_actions
        ):
            raise ValueError(f"requested action {task.requested_action!r} is not allowed")
        if not agent.required_reviewers:
            raise ValueError(f"agent {task.agent_id!r} is missing required reviewers")
        if any(reviewer == task.agent_id for reviewer in agent.required_reviewers):
            raise ValueError(f"agent {task.agent_id!r} cannot self-approve")
        if agent.human_release_gate_required and not plan.requires_human_gate:
            raise ValueError("human release gate requirement cannot be bypassed")
        return RoutedTask(
            task_id=task.task_id,
            agent_id=task.agent_id,
            skill=task.skill,
            route_type=self._classify_route(task_type),
            payload=payload,
            registry_schema_version=self.registry_snapshot.schema_version,
            registry_definition_hash=self.registry_snapshot.definition_hash,
            selected_agent_definition_version=agent.definition_version,
            route_validation_result="route_allowed",
            required_reviewers=agent.required_reviewers,
            forbidden_actions=agent.forbidden_actions,
            human_release_gate_required=agent.human_release_gate_required,
        )

    def route_all(
        self, plan: DependencyPlan, payloads: dict[str, dict[str, Any]]
    ) -> list[RoutedTask]:
        return [self.route(plan, task, payloads.get(task.task_id, {})) for task in plan.tasks]
