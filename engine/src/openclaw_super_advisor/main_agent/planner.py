"""MAIN Planner — decomposes user requests into specialist agent task plans.

MAIN must never call a specialist agent by hardcoded name in an ad-hoc manner.
Instead, the Planner interprets the request type and emits a structured DependencyPlan
that specifies which agents run, in what order, with what evidence requirements.

Blueprint §3.2: Planner and Dependency Resolution
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .registry_runtime import RegistrySnapshot, required_fields_from_schema


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    agent_id: str
    skill: str
    depends_on: tuple[str, ...]
    input_schema: dict[str, Any]
    task_type: str = ""
    requested_action: str = "analyze"


@dataclass(frozen=True)
class PlanningDecision:
    task_id: str
    request_type: str
    selected_agent: str
    registry_definition_hash: str
    selection_reason: str
    matched_accepted_task_type: str
    rejected_candidate_agents: tuple[dict[str, str], ...]
    required_inputs: tuple[str, ...]
    output_contract: dict[str, Any]
    required_reviewers: tuple[str, ...]
    downstream_route: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    human_release_gate_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_type": self.request_type,
            "selected_agent": self.selected_agent,
            "registry_definition_hash": self.registry_definition_hash,
            "selection_reason": self.selection_reason,
            "matched_accepted_task_type": self.matched_accepted_task_type,
            "rejected_candidate_agents": list(self.rejected_candidate_agents),
            "required_inputs": list(self.required_inputs),
            "output_contract": self.output_contract,
            "required_reviewers": list(self.required_reviewers),
            "downstream_route": list(self.downstream_route),
            "forbidden_actions": list(self.forbidden_actions),
            "human_release_gate_required": self.human_release_gate_required,
        }


@dataclass(frozen=True)
class DependencyPlan:
    plan_id: str
    request_type: str
    tasks: tuple[AgentTask, ...]
    requires_human_gate: bool
    registry_schema_version: str = ""
    registry_definition_hash: str = ""
    planning_decisions: tuple[PlanningDecision, ...] = field(default_factory=tuple)


class MainPlanner:
    """Decomposes incoming requests into dependency-ordered agent task plans.

    MAIN (super-advisor) does not appear in plans — it is the orchestrator.
    """

    def __init__(
        self,
        registry_snapshot: RegistrySnapshot,
        *,
        source_agent: str = "super-advisor",
    ) -> None:
        self.registry_snapshot = registry_snapshot
        self.source_agent = source_agent

    def validate_agent(
        self,
        task: AgentTask,
        *,
        request_type: str,
        available_inputs: dict[str, Any] | None,
    ) -> PlanningDecision:
        self.registry_snapshot.require_ready()
        available_inputs = available_inputs or {}
        rejected: list[dict[str, str]] = []
        selected_task_type = task.task_type or request_type
        selected_agent = self.registry_snapshot.get_agent(task.agent_id)
        if selected_agent.agent_id == self.source_agent:
            raise ValueError("MAIN cannot self-delegate")
        if selected_agent.current_availability != "AVAILABLE":
            raise ValueError(f"agent {task.agent_id!r} is not available")
        for candidate in self.registry_snapshot.list_available_agents():
            if candidate.agent_id == self.source_agent:
                rejected.append({"agent_id": candidate.agent_id, "reason": "orchestrator_only"})
                continue
            if selected_task_type not in candidate.accepted_task_types:
                rejected.append(
                    {"agent_id": candidate.agent_id, "reason": "task_type_not_accepted"}
                )
                continue
            if candidate.agent_id != task.agent_id:
                rejected.append({"agent_id": candidate.agent_id, "reason": "not_selected_for_task"})
                continue
        if selected_task_type not in selected_agent.accepted_task_types:
            raise ValueError(
                f"agent {task.agent_id!r} does not accept task_type {selected_task_type!r}"
            )
        required_inputs = required_fields_from_schema(selected_agent.required_input_schema)
        missing_inputs = tuple(field for field in required_inputs if field not in available_inputs)
        if missing_inputs:
            raise ValueError(
                f"agent {task.agent_id!r} missing required inputs: {', '.join(missing_inputs)}"
            )
        requested_action = task.requested_action.strip().lower()
        if requested_action and any(
            requested_action in forbidden.lower() for forbidden in selected_agent.forbidden_actions
        ):
            raise ValueError(
                f"agent {task.agent_id!r} forbidden action requested: {task.requested_action!r}"
            )
        if requested_action and not any(
            requested_action in allowed.lower() for allowed in selected_agent.allowed_actions
        ):
            raise ValueError(
                f"agent {task.agent_id!r} does not allow action {task.requested_action!r}"
            )
        source_agent = self.registry_snapshot.get_agent(self.source_agent)
        if task.agent_id not in source_agent.downstream_routes:
            raise ValueError(
                f"route from {self.source_agent!r} to {task.agent_id!r} is not allowed"
            )
        if any(
            reviewer == task.agent_id for reviewer in selected_agent.required_reviewers
        ) or selected_agent.self_approval_allowed:
            raise ValueError(f"agent {task.agent_id!r} cannot self-approve")
        return PlanningDecision(
            task_id=task.task_id,
            request_type=request_type,
            selected_agent=task.agent_id,
            registry_definition_hash=self.registry_snapshot.definition_hash,
            selection_reason=(
                f"{task.agent_id} accepts task_type {selected_task_type!r}, "
                f"received all required inputs, and is reachable from {self.source_agent!r}"
            ),
            matched_accepted_task_type=selected_task_type,
            rejected_candidate_agents=tuple(rejected),
            required_inputs=required_inputs,
            output_contract=selected_agent.output_contract,
            required_reviewers=selected_agent.required_reviewers,
            downstream_route=selected_agent.downstream_routes,
            forbidden_actions=selected_agent.forbidden_actions,
            human_release_gate_required=selected_agent.human_release_gate_required,
        )

    def build_plan(
        self,
        plan_id: str,
        request_type: str,
        tasks: list[AgentTask],
        *,
        available_inputs: dict[str, dict[str, Any]] | None = None,
    ) -> DependencyPlan:
        available_inputs = available_inputs or {}
        decisions = tuple(
            self.validate_agent(
                task,
                request_type=request_type,
                available_inputs=available_inputs.get(task.task_id),
            )
            for task in tasks
        )
        requires_gate = any(decision.human_release_gate_required for decision in decisions)
        return DependencyPlan(
            plan_id=plan_id,
            request_type=request_type,
            tasks=tuple(tasks),
            requires_human_gate=requires_gate,
            registry_schema_version=self.registry_snapshot.schema_version,
            registry_definition_hash=self.registry_snapshot.definition_hash,
            planning_decisions=decisions,
        )
