from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..agent_registry import (
    AGENT_REGISTRY_READY,
    AgentCapabilityRecord,
    AgentCapabilityRegistry,
    validate_agent_registry,
)
from ..paths import ProjectPaths


@dataclass(frozen=True)
class RegistrySnapshot:
    state: str
    schema_version: str
    definition_hash: str
    registry_version: str
    source_path: str
    loaded_by_main_runtime: bool
    last_validation_result: str
    missing_agent_count: int
    duplicate_agent_count: int
    config_mismatch_count: int
    route_issue_count: int
    validation_errors: tuple[str, ...]
    agents: tuple[AgentCapabilityRecord, ...]

    @classmethod
    def from_registry(
        cls,
        registry: AgentCapabilityRegistry,
        *,
        state: str,
        source_path: str,
        last_validation_result: str,
        missing_agent_count: int,
        duplicate_agent_count: int,
        config_mismatch_count: int,
        route_issue_count: int,
        validation_errors: tuple[str, ...],
        loaded_by_main_runtime: bool,
    ) -> RegistrySnapshot:
        return cls(
            state=state,
            schema_version=registry.schema_version,
            definition_hash=registry.registry_hash,
            registry_version=registry.registry_version,
            source_path=source_path,
            loaded_by_main_runtime=loaded_by_main_runtime,
            last_validation_result=last_validation_result,
            missing_agent_count=missing_agent_count,
            duplicate_agent_count=duplicate_agent_count,
            config_mismatch_count=config_mismatch_count,
            route_issue_count=route_issue_count,
            validation_errors=validation_errors,
            agents=registry.agents,
        )

    @classmethod
    def invalid(
        cls,
        *,
        state: str,
        source_path: str,
        last_validation_result: str,
        missing_agent_count: int,
        duplicate_agent_count: int,
        config_mismatch_count: int,
        route_issue_count: int,
        validation_errors: tuple[str, ...],
    ) -> RegistrySnapshot:
        return cls(
            state=state,
            schema_version="",
            definition_hash="",
            registry_version="",
            source_path=source_path,
            loaded_by_main_runtime=False,
            last_validation_result=last_validation_result,
            missing_agent_count=missing_agent_count,
            duplicate_agent_count=duplicate_agent_count,
            config_mismatch_count=config_mismatch_count,
            route_issue_count=route_issue_count,
            validation_errors=validation_errors,
            agents=(),
        )

    def require_ready(self) -> None:
        if self.state != AGENT_REGISTRY_READY:
            detail = "; ".join(self.validation_errors) or self.state
            raise RuntimeError(f"agent registry is not ready for MAIN runtime: {detail}")

    def get_agent(self, agent_id: str) -> AgentCapabilityRecord:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        raise KeyError(agent_id)

    def list_available_agents(self) -> tuple[AgentCapabilityRecord, ...]:
        return tuple(agent for agent in self.agents if agent.current_availability == "AVAILABLE")

    def find_agents_for_task(self, task_type: str) -> tuple[AgentCapabilityRecord, ...]:
        return tuple(agent for agent in self.agents if task_type in agent.accepted_task_types)


def build_registry_snapshot(
    paths: ProjectPaths,
    rendered_config: dict[str, object],
) -> RegistrySnapshot:
    report = validate_agent_registry(
        paths,
        rendered_config=rendered_config,
        require_generated_file=True,
    )
    route_issue_count = sum(
        1
        for issue in report.issues
        if issue.rule
        in {
            "unknown_agent",
            "review_chain_mismatch",
            "unknown_route_agent",
            "unknown_escalation_target",
            "forbidden_self_route",
            "self_approval_reviewer_chain",
        }
    )
    validation_errors = tuple(f"{issue.path}: {issue.message}" for issue in report.issues)
    if report.registry is None or not report.valid:
        return RegistrySnapshot.invalid(
            state=report.status,
            source_path=str(paths.agent_registry_path),
            last_validation_result="FAIL",
            missing_agent_count=report.missing_agent_count,
            duplicate_agent_count=report.duplicate_agent_count,
            config_mismatch_count=report.registry_config_mismatch_count,
            route_issue_count=route_issue_count,
            validation_errors=validation_errors,
        )
    return RegistrySnapshot.from_registry(
        report.registry,
        state=report.status,
        source_path=str(paths.agent_registry_path),
        last_validation_result="PASS",
        missing_agent_count=report.missing_agent_count,
        duplicate_agent_count=report.duplicate_agent_count,
        config_mismatch_count=report.registry_config_mismatch_count,
        route_issue_count=route_issue_count,
        validation_errors=validation_errors,
        loaded_by_main_runtime=True,
    )


def required_fields_from_schema(schema: dict[str, Any]) -> tuple[str, ...]:
    fields = schema.get("required_fields", [])
    if not isinstance(fields, list):
        return ()
    return tuple(str(field) for field in fields if isinstance(field, str) and field)
