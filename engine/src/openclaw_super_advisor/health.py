from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ._version import PHASE, __version__
from .agent_topology import build_agent_topology, validate_agent_topology, validate_routing
from .config import render_config, validate_rendered_config
from .env import EnvAuditReport, audit_environment
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


def run_health_check(paths: ProjectPaths) -> HealthReport:
    env_report: EnvAuditReport = audit_environment(paths)
    rendered_config = render_config(paths, env_path=paths.canonical_env_example_path)
    config_report = validate_rendered_config(rendered_config, paths)
    skill_report: SkillValidationReport = validate_skills(paths, rendered_config=rendered_config)
    topology_report = validate_agent_topology(rendered_config, paths)
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
    }
