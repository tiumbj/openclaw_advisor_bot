from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ._version import PHASE, __version__
from .agent_registry import validate_agent_registry
from .agent_topology import build_agent_topology, validate_agent_topology, validate_routing
from .config import render_config, validate_rendered_config
from .env import EnvAuditReport, audit_environment
from .main_agent.registry_runtime import build_registry_snapshot
from .main_agent.runtime import MainRuntimeManager
from .paths import ProjectPaths
from .skills import SkillValidationReport, validate_skills


@dataclass(frozen=True)
class HealthReport:
    version: str
    phase: str
    project_root: str
    env_valid: bool
    env_status: dict[str, str]
    config_valid: bool
    skills_valid: bool
    runtime_agent_id: str
    runtime_agent_ids: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    routing_valid: bool
    topology_valid: bool
    agent_registry_status: str
    agent_registry_valid: bool
    registry_schema_version: str
    registry_definition_hash: str
    registry_agent_count: int
    registry_missing_agent_count: int
    registry_duplicate_agent_count: int
    registry_route_issue_count: int
    registry_config_mismatch_count: int
    registry_source: str
    registry_loaded_by_main_runtime: bool
    registry_last_validation_result: str
    registry_validation_errors: tuple[str, ...]


def run_health_check(paths: ProjectPaths) -> HealthReport:
    env_report: EnvAuditReport = audit_environment(paths)
    rendered_config = render_config(paths, env_path=paths.canonical_env_example_path)
    config_report = validate_rendered_config(rendered_config, paths)
    skill_report: SkillValidationReport = validate_skills(paths, rendered_config=rendered_config)
    topology_report = validate_agent_topology(rendered_config, paths)
    registry_report = validate_agent_registry(
        paths,
        rendered_config=rendered_config,
        require_generated_file=True,
    )
    snapshot = build_registry_snapshot(paths, rendered_config)
    runtime = MainRuntimeManager.from_registry_snapshot(
        snapshot,
        paths.state_dir / "health-main-runtime",
        lambda task: {
            "task_id": task.task_id,
            "agent_id": task.agent_id,
            "status": "COMPLETED",
            "evidence_reference": "health-check",
            "payload": {},
            "provenance": {"source": "health"},
        },
    )
    routing_section = rendered_config.get("routing")
    route_report = validate_routing(cast(dict[str, list[list[str]]] | None, routing_section))
    agent_ids = tuple(agent.agent_id for agent in build_agent_topology(paths))
    return HealthReport(
        version=__version__,
        phase=PHASE,
        project_root=str(paths.root_dir),
        env_valid=env_report.valid,
        env_status=dict(env_report.statuses),
        config_valid=config_report.valid,
        skills_valid=skill_report.valid,
        runtime_agent_id="super-advisor",
        runtime_agent_ids=agent_ids,
        allowed_tools=("read", "session_status"),
        routing_valid=route_report.valid,
        topology_valid=topology_report.valid,
        agent_registry_status=registry_report.status,
        agent_registry_valid=registry_report.valid,
        registry_schema_version=snapshot.schema_version,
        registry_definition_hash=snapshot.definition_hash,
        registry_agent_count=len(snapshot.agents),
        registry_missing_agent_count=snapshot.missing_agent_count,
        registry_duplicate_agent_count=snapshot.duplicate_agent_count,
        registry_route_issue_count=snapshot.route_issue_count,
        registry_config_mismatch_count=snapshot.config_mismatch_count,
        registry_source=snapshot.source_path,
        registry_loaded_by_main_runtime=runtime.registry_loaded_by_main_runtime,
        registry_last_validation_result=snapshot.last_validation_result,
        registry_validation_errors=snapshot.validation_errors,
    )


def run_health_check_as_dict(paths: ProjectPaths) -> dict[str, object]:
    report = run_health_check(paths)
    return {
        "version": report.version,
        "phase": report.phase,
        "project_root": report.project_root,
        "env_valid": report.env_valid,
        "env_status": report.env_status,
        "config_valid": report.config_valid,
        "skills_valid": report.skills_valid,
        "runtime_agent_id": report.runtime_agent_id,
        "runtime_agent_ids": list(report.runtime_agent_ids),
        "allowed_tools": list(report.allowed_tools),
        "routing_valid": report.routing_valid,
        "topology_valid": report.topology_valid,
        "agent_registry_status": report.agent_registry_status,
        "agent_registry_valid": report.agent_registry_valid,
        "registry_state": report.agent_registry_status,
        "registry_schema_version": report.registry_schema_version,
        "registry_definition_hash": report.registry_definition_hash,
        "registry_agent_count": report.registry_agent_count,
        "registry_missing_agent_count": report.registry_missing_agent_count,
        "registry_duplicate_agent_count": report.registry_duplicate_agent_count,
        "registry_route_issue_count": report.registry_route_issue_count,
        "registry_config_mismatch_count": report.registry_config_mismatch_count,
        "registry_source": report.registry_source,
        "registry_loaded_by_main_runtime": report.registry_loaded_by_main_runtime,
        "registry_last_validation_result": report.registry_last_validation_result,
        "registry_validation_errors": list(report.registry_validation_errors),
    }
