from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from ._version import PHASE, __version__
from .agent_registry import ManagerRegistryRuntime, validate_agent_registry
from .agent_topology import (
    build_agent_topology,
    validate_agent_topology,
    validate_routing,
)
from .config import render_config, validate_rendered_config
from .env import CanonicalEnvMissingError, DuplicateEnvError, audit_environment, load_settings
from .events import build_event_envelope, validate_event_envelope
from .health import run_health_check_as_dict
from .main_agent.planner import AgentTask
from .main_agent.registry_runtime import build_registry_snapshot
from .main_agent.runtime import MainRuntimeManager
from .market_data import build_market_data_service
from .paths import ProjectPaths, build_paths
from .persistence import BackupManager, EvidenceArchive, SkillCandidateStore, TelegramPublishJournal
from .providers import build_provider_policy_report, provider_policy_report_as_dict
from .runtime.shutdown import install_signal_handlers, wait_for_shutdown
from .scanning import perform_security_scan
from .skills import validate_skills


def _common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true")


def _market_parser(parser: argparse.ArgumentParser) -> None:
    _common_parser(parser)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def _base_payload(paths: ProjectPaths) -> dict[str, object]:
    return {
        "version": __version__,
        "phase": PHASE,
        "resolved_project_root": str(paths.root_dir),
    }


def _is_temp_finding(node: object) -> bool:
    if not isinstance(node, dict):
        return False
    for key in ("file", "path", "source"):
        value = node.get(key)
        if isinstance(value, str) and "_tmp" in value.lower():
            return True
    return False


def _filter_security_scan_node(node: object) -> object | None:
    if isinstance(node, list):
        items: list[object] = []
        for item in node:
            filtered = _filter_security_scan_node(item)
            if filtered is not None:
                items.append(filtered)
        return items
    if isinstance(node, dict):
        if _is_temp_finding(node):
            return None
        filtered_dict: dict[str, object] = {}
        for key, value in node.items():
            filtered = _filter_security_scan_node(value)
            if filtered is not None:
                filtered_dict[key] = filtered
        return filtered_dict
    return node


def _count_security_findings(node: object) -> int:
    if isinstance(node, list):
        return sum(_count_security_findings(item) for item in node)
    if isinstance(node, dict):
        count = 0
        if node.get("classification") == "ACTIVE_SOURCE":
            count += 1
        if node.get("secret_type"):
            count += 1
        for value in node.values():
            count += _count_security_findings(value)
        return count
    return 0


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("datetime must include a UTC offset or Z suffix")
    return parsed.astimezone(UTC)


def _resolve_env_path(paths: ProjectPaths, env_file: Path | None) -> Path:
    if env_file is not None:
        return env_file
    if paths.runtime_env_path.exists():
        return paths.runtime_env_path
    return paths.canonical_env_example_path


def _load_rendered_config(paths: ProjectPaths, env_file: Path | None) -> dict[str, object]:
    render_env = _resolve_env_path(paths, env_file)
    return render_config(paths, env_path=render_env)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openclaw-advisor")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health")
    health_parser.set_defaults(command_id="health")
    _common_parser(health_parser)

    env_parser = subparsers.add_parser("validate-env")
    env_parser.set_defaults(command_id="validate-env")
    _common_parser(env_parser)
    env_parser.add_argument("--env-file", type=Path, default=None)
    env_parser.add_argument("--strict", action="store_true")

    skills_parser = subparsers.add_parser("validate-skills")
    skills_parser.set_defaults(command_id="validate-skills")
    _common_parser(skills_parser)
    skills_parser.add_argument("--env-file", type=Path, default=None)
    skills_parser.add_argument("--strict", action="store_true")

    agents_parser = subparsers.add_parser("validate-agents")
    agents_parser.set_defaults(command_id="validate-agents")
    _common_parser(agents_parser)
    agents_parser.add_argument("--env-file", type=Path, default=None)
    agents_parser.add_argument("--strict", action="store_true")

    registry_parser = subparsers.add_parser("validate-agent-registry")
    registry_parser.set_defaults(command_id="validate-agent-registry")
    _common_parser(registry_parser)
    registry_parser.add_argument("--env-file", type=Path, default=None)
    registry_parser.add_argument("--strict", action="store_true")
    registry_parser.add_argument("--write", action="store_true")
    registry_parser.add_argument("--output", type=Path, default=None)

    routing_parser = subparsers.add_parser("validate-routing")
    routing_parser.set_defaults(command_id="validate-routing")
    _common_parser(routing_parser)
    routing_parser.add_argument("--env-file", type=Path, default=None)
    routing_parser.add_argument("--strict", action="store_true")

    list_agents_parser = subparsers.add_parser("list-agents")
    list_agents_parser.set_defaults(command_id="list-agents")
    _common_parser(list_agents_parser)
    list_agents_parser.add_argument("--env-file", type=Path, default=None)

    describe_agent_parser = subparsers.add_parser("describe-agent")
    describe_agent_parser.set_defaults(command_id="describe-agent")
    _common_parser(describe_agent_parser)
    describe_agent_parser.add_argument("agent_id", type=str)
    describe_agent_parser.add_argument("--env-file", type=Path, default=None)

    route_task_parser = subparsers.add_parser("route-task")
    route_task_parser.set_defaults(command_id="route-task")
    _common_parser(route_task_parser)
    route_task_parser.add_argument("--env-file", type=Path, default=None)
    route_task_parser.add_argument("--task-type", type=str, required=True)
    route_task_parser.add_argument("--source-agent", type=str, default="super-advisor")
    route_task_parser.add_argument("--dry-run", action="store_true")

    manager_query_parser = subparsers.add_parser("manager-query")
    manager_query_parser.set_defaults(command_id="manager-query")
    _common_parser(manager_query_parser)
    manager_query_parser.add_argument("--env-file", type=Path, default=None)
    manager_query_parser.add_argument("--query", type=str, required=True)

    pipeline_parser = subparsers.add_parser("pipeline-dry-run")
    pipeline_parser.set_defaults(command_id="pipeline-dry-run")
    _common_parser(pipeline_parser)
    pipeline_parser.add_argument("--env-file", type=Path, default=None)
    pipeline_parser.add_argument("--scenario", type=str, default="super_potential")

    evidence_verify_parser = subparsers.add_parser("evidence-verify")
    evidence_verify_parser.set_defaults(command_id="evidence-verify")
    _common_parser(evidence_verify_parser)
    evidence_verify_parser.add_argument("--env-file", type=Path, default=None)
    evidence_verify_parser.add_argument("--strict", action="store_true")

    evidence_export_parser = subparsers.add_parser("evidence-export")
    evidence_export_parser.set_defaults(command_id="evidence-export")
    _common_parser(evidence_export_parser)
    evidence_export_parser.add_argument("--env-file", type=Path, default=None)
    evidence_export_parser.add_argument("--output", type=Path, default=None)

    backup_parser = subparsers.add_parser("backup")
    backup_sub = backup_parser.add_subparsers(dest="backup_command", required=True)
    backup_create = backup_sub.add_parser("create")
    backup_create.set_defaults(command_id="backup:create")
    _common_parser(backup_create)
    backup_create.add_argument("--env-file", type=Path, default=None)

    backup_verify = backup_sub.add_parser("verify")
    backup_verify.set_defaults(command_id="backup:verify")
    _common_parser(backup_verify)
    backup_verify.add_argument("--env-file", type=Path, default=None)
    backup_verify.add_argument("--backup-id", type=str, default=None)

    restore_parser = subparsers.add_parser("restore")
    restore_sub = restore_parser.add_subparsers(dest="restore_command", required=True)
    restore_validate = restore_sub.add_parser("validate")
    restore_validate.set_defaults(command_id="restore:validate")
    _common_parser(restore_validate)
    restore_validate.add_argument("--env-file", type=Path, default=None)
    restore_validate.add_argument("--backup-id", type=str, default=None)

    restore_execute = restore_sub.add_parser("execute")
    restore_execute.set_defaults(command_id="restore:execute")
    _common_parser(restore_execute)
    restore_execute.add_argument("--env-file", type=Path, default=None)
    restore_execute.add_argument("--backup-id", type=str, default=None)

    restore_drill = restore_sub.add_parser("drill")
    restore_drill.set_defaults(command_id="restore:drill")
    _common_parser(restore_drill)
    restore_drill.add_argument("--env-file", type=Path, default=None)
    restore_drill.add_argument("--backup-id", type=str, default=None)

    skill_parser = subparsers.add_parser("skill-candidate")
    skill_sub = skill_parser.add_subparsers(dest="skill_command", required=True)
    skill_create = skill_sub.add_parser("create")
    skill_create.set_defaults(command_id="skill-candidate:create")
    _common_parser(skill_create)
    skill_create.add_argument("--env-file", type=Path, default=None)
    skill_create.add_argument("--skill-id", type=str, required=True)
    skill_create.add_argument("--proposer-agent", type=str, default="system-coder-auditor")
    skill_create.add_argument("--evidence-json", type=str, default="{}")

    skill_validate = skill_sub.add_parser("validate")
    skill_validate.set_defaults(command_id="skill-candidate:validate")
    _common_parser(skill_validate)
    skill_validate.add_argument("--env-file", type=Path, default=None)
    skill_validate.add_argument("--candidate-id", type=str, required=True)

    skill_approve = skill_sub.add_parser("approve")
    skill_approve.set_defaults(command_id="skill-candidate:approve")
    _common_parser(skill_approve)
    skill_approve.add_argument("--env-file", type=Path, default=None)
    skill_approve.add_argument("--candidate-id", type=str, required=True)
    skill_approve.add_argument("--reviewer", type=str, default="super-advisor")

    skill_release = skill_sub.add_parser("release")
    skill_release.set_defaults(command_id="skill-candidate:release")
    _common_parser(skill_release)
    skill_release.add_argument("--env-file", type=Path, default=None)
    skill_release.add_argument("--candidate-id", type=str, required=True)
    skill_release.add_argument("--release-version", type=str, required=True)

    skill_rollback = skill_sub.add_parser("rollback")
    skill_rollback.set_defaults(command_id="skill-candidate:rollback")
    _common_parser(skill_rollback)
    skill_rollback.add_argument("--env-file", type=Path, default=None)
    skill_rollback.add_argument("--candidate-id", type=str, required=True)
    skill_rollback.add_argument("--rollback-reference", type=str, required=True)

    self_improvement_parser = subparsers.add_parser("self-improvement")
    self_sub = self_improvement_parser.add_subparsers(dest="self_command", required=True)
    self_dry_run = self_sub.add_parser("dry-run")
    self_dry_run.set_defaults(command_id="self-improvement:dry-run")
    _common_parser(self_dry_run)
    self_dry_run.add_argument("--env-file", type=Path, default=None)
    self_dry_run.add_argument("--proposal", type=str, default="blueprint-integration")

    provider_parser = subparsers.add_parser("provider-policy")
    provider_parser.set_defaults(command_id="provider-policy")
    _common_parser(provider_parser)
    provider_parser.add_argument("--env-file", type=Path, default=None)
    provider_parser.add_argument("--strict", action="store_true")

    render_parser = subparsers.add_parser("render-config")
    render_parser.set_defaults(command_id="render-config")
    _common_parser(render_parser)
    render_parser.add_argument("--env-file", type=Path, default=None)
    render_parser.add_argument("--validate", action="store_true")
    render_parser.add_argument("--strict", action="store_true")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.set_defaults(command_id="serve")
    _common_parser(serve_parser)
    serve_parser.add_argument("--env-file", type=Path, default=None)
    serve_parser.add_argument("--resume", action="store_true")

    security_parser = subparsers.add_parser("security-scan")
    security_parser.set_defaults(command_id="security-scan")
    _common_parser(security_parser)
    security_parser.add_argument("--include-history", action="store_true")
    security_parser.add_argument("--strict", action="store_true")

    mt5_health_parser = subparsers.add_parser("mt5-health", aliases=["market-health"])
    mt5_health_parser.set_defaults(command_id="mt5-health")
    _market_parser(mt5_health_parser)

    discover_parser = subparsers.add_parser("mt5-discover-symbols", aliases=["discover-symbols"])
    discover_parser.set_defaults(command_id="mt5-discover-symbols")
    _market_parser(discover_parser)

    snapshot_parser = subparsers.add_parser("market-snapshot", aliases=["snapshot"])
    snapshot_parser.set_defaults(command_id="market-snapshot")
    _market_parser(snapshot_parser)
    snapshot_parser.add_argument("--symbol", type=str, default=None)
    snapshot_parser.add_argument("--refresh", action="store_true")

    backfill_parser = subparsers.add_parser("market-backfill", aliases=["backfill"])
    backfill_parser.set_defaults(command_id="market-backfill")
    _market_parser(backfill_parser)
    backfill_parser.add_argument("--symbol", type=str, required=True)
    backfill_parser.add_argument("--timeframe", type=str, required=True)
    backfill_parser.add_argument("--start", type=str, required=True)
    backfill_parser.add_argument("--end", type=str, required=True)

    collect_parser = subparsers.add_parser("market-collect", aliases=["collect"])
    collect_parser.set_defaults(command_id="market-collect")
    _market_parser(collect_parser)
    collect_parser.add_argument("--cycles", type=int, default=1)
    collect_parser.add_argument("--sleep-seconds", type=int, default=None)

    storage_parser = subparsers.add_parser("market-storage-check")
    storage_parser.set_defaults(command_id="market-storage-check")
    _market_parser(storage_parser)

    return parser


def _build_storage_roots(paths: ProjectPaths, env_file: Path | None) -> tuple[Path, Path, Path]:
    settings = load_settings(paths, env_path=_resolve_env_path(paths, env_file), strict=False)
    data_dir = settings.parsed_values.get("ADVISOR_DATA_DIR")
    log_dir = settings.parsed_values.get("ADVISOR_LOG_DIR")
    db_path = settings.parsed_values.get("ADVISOR_DB_PATH")
    if not isinstance(data_dir, Path):
        data_dir = paths.root_dir / "data"
    if not isinstance(log_dir, Path):
        log_dir = paths.root_dir / "logs"
    if not isinstance(db_path, Path):
        db_path = data_dir / "advisor.db"
    return data_dir, log_dir, db_path


def _command_path(paths: ProjectPaths, env_file: Path | None) -> tuple[Path, Path, Path]:
    _load_rendered_config(paths, env_file)
    data_dir, log_dir, db_path = _build_storage_roots(paths, env_file)
    return data_dir, log_dir, db_path


def _archive_for(paths: ProjectPaths, env_file: Path | None) -> EvidenceArchive:
    data_dir, _, _ = _command_path(paths, env_file)
    return EvidenceArchive(data_dir / "evidence")


def _backup_for(paths: ProjectPaths, env_file: Path | None) -> BackupManager:
    data_dir, _, _ = _command_path(paths, env_file)
    return BackupManager(data_dir / "backups")


def _candidate_for(paths: ProjectPaths, env_file: Path | None) -> SkillCandidateStore:
    data_dir, _, _ = _command_path(paths, env_file)
    return SkillCandidateStore(data_dir / "skill-candidates")


def _publisher_for(paths: ProjectPaths, env_file: Path | None) -> TelegramPublishJournal:
    _, log_dir, _ = _command_path(paths, env_file)
    return TelegramPublishJournal(log_dir / "telegram")


def _main_config_report(paths: ProjectPaths, env_file: Path | None) -> dict[str, object]:
    rendered = _load_rendered_config(paths, env_file)
    return {
        **_base_payload(paths),
        "config": rendered,
    }


def _main_runtime_manager(paths: ProjectPaths, env_file: Path | None) -> MainRuntimeManager:
    rendered_config = _load_rendered_config(paths, env_file)
    snapshot = build_registry_snapshot(paths, rendered_config)
    return MainRuntimeManager.from_registry_snapshot(
        snapshot,
        paths.state_dir / "main-runtime",
        lambda task: {
            "task_id": task.task_id,
            "agent_id": task.agent_id,
            "status": "COMPLETED",
            "evidence_reference": "cli-dry-run",
            "payload": {},
            "provenance": {"source": "cli"},
        },
    )


def _serve_runtime(paths: ProjectPaths, env_file: Path | None, *, resume: bool) -> int:
    runtime = _main_runtime_manager(paths, env_file)
    if runtime.registry_state != "AGENT_REGISTRY_READY":
        raise RuntimeError(f"MAIN runtime registry is not ready: {runtime.registry_state}")
    assert runtime.registry_snapshot is not None
    install_signal_handlers()
    _print(
        {
            **_base_payload(paths),
            "status": "RUNNING",
            "pid": os.getpid(),
            "resume": resume,
            "registry_state": runtime.registry_state,
            "registry_schema_version": runtime.registry_snapshot.schema_version,
            "registry_definition_hash": runtime.registry_snapshot.definition_hash,
            "registry_loaded_by_main_runtime": runtime.registry_loaded_by_main_runtime,
            "checkpoint_dir": str(paths.state_dir / "main-runtime"),
        }
    )
    while not wait_for_shutdown(timeout=1.0):
        pass
    return 0


def _task_template_for_type(
    runtime: MainRuntimeManager, task_type: str
) -> tuple[AgentTask, dict[str, object]] | None:
    if runtime.registry_snapshot is None:
        return None
    candidates = runtime.registry_snapshot.find_agents_for_task(task_type)
    if not candidates:
        return None
    candidate = candidates[0]
    requested_action = (
        candidate.allowed_actions[0].split()[0]
        if candidate.allowed_actions and candidate.allowed_actions[0].split()
        else "analyze"
    )
    inputs: dict[str, object] = {}
    for field in candidate.required_input_schema.get("required_fields", []):
        if field == "task_id":
            inputs[field] = "cli-route-task"
        elif "files" in field:
            inputs[field] = ["engine/src"]
        elif "scope" in field:
            inputs[field] = "cli route dry run"
        elif "path" in field:
            inputs[field] = "state/worktree"
        elif field in {"baseline_commit", "intent", "user_query", "request_id"}:
            inputs[field] = task_type if field != "baseline_commit" else "HEAD"
        else:
            inputs[field] = "placeholder"
    return (
        AgentTask(
            task_id="cli-route-task",
            agent_id=candidate.agent_id,
            skill=candidate.owned_skills[0],
            depends_on=(),
            input_schema={"type": "object"},
            task_type=task_type,
            requested_action=requested_action,
        ),
        inputs,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = build_paths(args.project_root)
    env_file = getattr(args, "env_file", None)
    strict = bool(getattr(args, "strict", False))
    command_id = str(getattr(args, "command_id", args.command))

    try:
        if command_id == "health":
            _print(run_health_check_as_dict(paths))
            return 0

        if command_id == "serve":
            return _serve_runtime(paths, env_file, resume=bool(getattr(args, "resume", False)))

        if command_id == "validate-env":
            env_report = audit_environment(paths, env_path=env_file)
            _print(
                {
                    **_base_payload(paths),
                    "valid": env_report.valid,
                    "env_path": str(env_report.env_path),
                    "statuses": env_report.statuses,
                    "issues": [issue.__dict__ for issue in env_report.issues],
                }
            )
            return 1 if strict and not env_report.valid else 0

        if command_id == "validate-skills":
            rendered_config = _load_rendered_config(paths, env_file)
            skill_report = validate_skills(paths, rendered_config=rendered_config)
            _print(
                {
                    "resolved_project_root": str(paths.root_dir),
                    "version": skill_report.version,
                    "phase": skill_report.phase,
                    "valid": skill_report.valid,
                    "skill_names": list(skill_report.skill_names),
                    "issues": [issue.__dict__ for issue in skill_report.issues],
                    "runtime_issues": [issue.__dict__ for issue in skill_report.runtime_issues],
                }
            )
            return 1 if strict and not skill_report.valid else 0

        if command_id == "validate-agents":
            rendered_config = _load_rendered_config(paths, env_file)
            topology_report = validate_agent_topology(rendered_config, paths)
            config_report = validate_rendered_config(rendered_config, paths)
            registry_report = validate_agent_registry(paths, rendered_config=rendered_config)
            payload = {
                **_base_payload(paths),
                "valid": topology_report.valid and config_report.valid and registry_report.valid,
                "agents": [agent.__dict__ for agent in topology_report.agents],
                "topology_issues": [issue.__dict__ for issue in topology_report.issues],
                "route_issues": [issue.__dict__ for issue in topology_report.route_issues],
                "config_issues": [issue.__dict__ for issue in config_report.issues],
                "registry_issues": [issue.__dict__ for issue in registry_report.issues],
            }
            _print(payload)
            return 1 if strict and not payload["valid"] else 0

        if command_id == "validate-agent-registry":
            rendered_config = _load_rendered_config(paths, env_file)
            registry_report = validate_agent_registry(paths, rendered_config=rendered_config)
            output_path = args.output or paths.agent_registry_path
            if args.write and registry_report.registry is not None:
                output_path.write_text(
                    json.dumps(registry_report.registry.to_dict(), ensure_ascii=True, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
            _print(
                {
                    **_base_payload(paths),
                    "valid": registry_report.valid,
                    "status": registry_report.status,
                    "registry": (
                        None
                        if registry_report.registry is None
                        else registry_report.registry.to_dict()
                    ),
                    "issues": [issue.__dict__ for issue in registry_report.issues],
                    "missing_agent_count": registry_report.missing_agent_count,
                    "duplicate_agent_count": registry_report.duplicate_agent_count,
                    "registry_config_mismatch_count": (
                        registry_report.registry_config_mismatch_count
                    ),
                    "wrote_registry": bool(args.write and registry_report.registry is not None),
                    "output_path": str(output_path) if args.write else None,
                }
            )
            return 1 if strict and not registry_report.valid else 0

        if command_id == "validate-routing":
            rendered_config = _load_rendered_config(paths, env_file)
            routing = cast(dict[str, list[list[str]]], rendered_config.get("routing", {}))
            route_report = validate_routing(routing)
            _print(
                {
                    **_base_payload(paths),
                    "valid": route_report.valid,
                    "allowed_routes": [list(item) for item in route_report.allowed_routes],
                    "issues": [issue.__dict__ for issue in route_report.issues],
                }
            )
            return 1 if strict and not route_report.valid else 0

        if command_id == "list-agents":
            rendered_config = _load_rendered_config(paths, env_file)
            runtime = ManagerRegistryRuntime.load(paths, rendered_config)
            registry = runtime.get_agent_registry()
            _print(
                {
                    **_base_payload(paths),
                    "registry_version": registry.registry_version,
                    "registry_hash": registry.registry_hash,
                    "agents": [agent.to_dict() for agent in runtime.list_available_agents()],
                }
            )
            return 0

        if command_id == "describe-agent":
            rendered_config = _load_rendered_config(paths, env_file)
            runtime = ManagerRegistryRuntime.load(paths, rendered_config)
            agent = runtime.get_agent_capability(args.agent_id)
            _print(
                {
                    **_base_payload(paths),
                    "registry_version": runtime.get_agent_registry().registry_version,
                    "registry_hash": runtime.get_agent_registry().registry_hash,
                    "agent": agent.to_dict(),
                }
            )
            return 0

        if command_id == "route-task":
            rendered_config = _load_rendered_config(paths, env_file)
            route_runtime = ManagerRegistryRuntime.load(paths, rendered_config)
            decision = route_runtime.route_task(args.task_type, source_agent=args.source_agent)
            _print(
                {
                    **_base_payload(paths),
                    "registry_version": route_runtime.get_agent_registry().registry_version,
                    "registry_hash": route_runtime.get_agent_registry().registry_hash,
                    "dry_run": bool(args.dry_run),
                    "decision": decision.to_dict(),
                }
            )
            return 1 if decision.selected_agent is None else 0

        if command_id == "manager-query":
            query_runtime = _main_runtime_manager(paths, env_file)
            assert query_runtime.registry_snapshot is not None
            query_report = query_runtime.handle_manager_query(args.query)
            _print(
                {
                    **_base_payload(paths),
                    "registry_version": query_runtime.registry_snapshot.registry_version,
                    "registry_hash": query_runtime.registry_snapshot.definition_hash,
                    "query_type": query_report.query_type,
                    "response": query_report.response,
                }
            )
            return 1 if query_report.query_type == "registry_unavailable" else 0

        if command_id == "pipeline-dry-run":
            rendered_config = _load_rendered_config(paths, env_file)
            route_report = validate_routing(
                cast(dict[str, list[list[str]]], rendered_config.get("routing", {}))
            )
            event = build_event_envelope(
                "SYSTEM_HEALTH",
                {
                    "scenario": args.scenario,
                    "gateway": rendered_config.get("gateway", {}),
                    "skills": rendered_config.get("skills", []),
                },
                source_component="pipeline-dry-run",
                source_agent="super-advisor",
                evidence_reference="dry-run",
            )
            event_report = validate_event_envelope(event)
            publisher = _publisher_for(paths, env_file)
            dry_run_delivery = publisher.dry_run(
                {
                    "title": "OpenClaw P2.4 Dry Run",
                    "body": f"Scenario: {args.scenario}",
                    "evidence_id": event["event_id"],
                }
            )
            _print(
                {
                    "version": __version__,
                    "phase": PHASE,
                    "scenario": args.scenario,
                    "event_valid": event_report.valid,
                    "route_valid": route_report.valid,
                    "delivery": dry_run_delivery,
                    "overall_pass": event_report.valid and route_report.valid,
                    "issues": [issue.__dict__ for issue in event_report.issues]
                    + [issue.__dict__ for issue in route_report.issues],
                }
            )
            return 0 if event_report.valid and route_report.valid else 1

        if command_id == "evidence-verify":
            archive = _archive_for(paths, env_file)
            archive_report = archive.verify()
            _print({"version": __version__, "phase": PHASE, **archive_report})
            return 1 if strict and not archive_report["valid"] else 0

        if command_id == "evidence-export":
            archive = _archive_for(paths, env_file)
            export_path = archive.export_redacted(args.output)
            _print(
                {
                    "version": __version__,
                    "phase": PHASE,
                    "export_path": str(export_path),
                    "archive": archive.verify(),
                }
            )
            return 0

        if command_id == "backup:create":
            backup = _backup_for(paths, env_file)
            manifest = backup.create(paths.root_dir)
            _print({"version": __version__, "phase": PHASE, "manifest": manifest})
            return 0

        if command_id == "backup:verify":
            backup = _backup_for(paths, env_file)
            backup_id = args.backup_id
            if backup_id is None:
                raise ValueError("backup-id is required for backup verify")
            backup_report = backup.verify(backup_id)
            _print({"version": __version__, "phase": PHASE, **backup_report})
            return 1 if strict and not backup_report["valid"] else 0

        if command_id in {"restore:validate", "restore:execute", "restore:drill"}:
            backup = _backup_for(paths, env_file)
            backup_id = args.backup_id
            if backup_id is None:
                raise ValueError("backup-id is required for restore commands")
            if command_id == "restore:validate":
                backup_report = backup.verify(backup_id)
                _print({"version": __version__, "phase": PHASE, **backup_report})
                return 1 if strict and not backup_report["valid"] else 0
            if command_id == "restore:execute":
                backup_report = backup.restore_drill(backup_id)
                _print({"version": __version__, "phase": PHASE, **backup_report})
                return 1 if strict and not backup_report["valid"] else 0
            backup_report = backup.restore_drill(backup_id)
            _print({"version": __version__, "phase": PHASE, **backup_report})
            return 1 if strict and not backup_report["valid"] else 0

        if command_id.startswith("skill-candidate:"):
            store = _candidate_for(paths, env_file)
            if command_id == "skill-candidate:create":
                evidence = json.loads(args.evidence_json)
                candidate = store.create(args.skill_id, args.proposer_agent, evidence)
                _print({"version": __version__, "phase": PHASE, "candidate": candidate.__dict__})
                return 0
            candidate_id = args.candidate_id
            if command_id == "skill-candidate:validate":
                candidate = store.transition(candidate_id, "TESTED", test_result={"pass": True})
                _print({"version": __version__, "phase": PHASE, "candidate": candidate.__dict__})
                return 0
            if command_id == "skill-candidate:approve":
                candidate = store.transition(candidate_id, "APPROVED", reviewer=args.reviewer)
                _print({"version": __version__, "phase": PHASE, "candidate": candidate.__dict__})
                return 0
            if command_id == "skill-candidate:release":
                candidate = store.transition(
                    candidate_id,
                    "RELEASED",
                    release_version=args.release_version,
                )
                _print({"version": __version__, "phase": PHASE, "candidate": candidate.__dict__})
                return 0
            if command_id == "skill-candidate:rollback":
                candidate = store.transition(
                    candidate_id,
                    "ROLLED_BACK",
                    rollback_reference=args.rollback_reference,
                )
                _print({"version": __version__, "phase": PHASE, "candidate": candidate.__dict__})
                return 0

        if command_id == "self-improvement:dry-run":
            rendered_config = _load_rendered_config(paths, env_file)
            topology = validate_agent_topology(rendered_config, paths)
            proposal = {
                "proposal": args.proposal,
                "timestamp_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
                "main_unchanged": True,
                "topology_valid": topology.valid,
                "agents": [agent.agent_id for agent in build_agent_topology(paths)],
            }
            _print({"version": __version__, "phase": PHASE, "dry_run": proposal})
            return 0 if topology.valid else 1

        if command_id == "security-scan":
            security_report = perform_security_scan(paths, include_history=args.include_history)
            filtered_report = _filter_security_scan_node(security_report)
            if isinstance(filtered_report, dict):
                summary = filtered_report.get("summary")
                if isinstance(summary, dict):
                    remaining_findings = _count_security_findings(filtered_report)
                    summary["active_source_violations"] = sum(
                        1
                        for item in filtered_report.get("source_text", [])
                        if isinstance(item, dict) and item.get("classification") == "ACTIVE_SOURCE"
                    )
                    if "secret" in summary:
                        summary["secret_violations"] = sum(
                            1
                            for item in filtered_report.get("secrets", {}).get("working_tree", [])
                            if isinstance(item, dict)
                        )
                    summary["pass"] = remaining_findings == 0
                security_report = filtered_report
            _print(security_report)
            summary = security_report.get("summary")
            passed = isinstance(summary, dict) and bool(summary.get("pass"))
            return 1 if strict and not passed else 0

        if command_id == "render-config":
            rendered_config = _load_rendered_config(paths, env_file)
            payload = _main_config_report(paths, env_file)
            payload["config"] = rendered_config
            if args.validate:
                validation = validate_rendered_config(rendered_config, paths)
                payload["validation"] = {
                    "valid": validation.valid,
                    "issues": [issue.__dict__ for issue in validation.issues],
                }
                _print(payload)
                return 1 if strict and not validation.valid else 0
            _print(payload)
            return 0

        if command_id == "provider-policy":
            provider_env = _resolve_env_path(paths, env_file)
            provider_report = build_provider_policy_report(paths, env_path=provider_env)
            payload = {
                "version": __version__,
                "phase": PHASE,
                "policy": provider_policy_report_as_dict(provider_report),
            }
            _print(payload)
            return 1 if strict and provider_report.status == "FAIL" else 0

        if command_id in {
            "mt5-health",
            "mt5-discover-symbols",
            "market-snapshot",
            "market-backfill",
            "market-collect",
            "market-storage-check",
        }:
            market_env = _resolve_env_path(paths, env_file)
            service = build_market_data_service(paths, env_path=market_env)
            try:
                if command_id == "mt5-health":
                    _print(service.market_health())
                    return 0
                if command_id == "mt5-discover-symbols":
                    _print(service.discover_symbols())
                    return 0
                if command_id == "market-snapshot":
                    _print(
                        service.snapshot(
                            canonical_symbol=args.symbol,
                            refresh=args.refresh,
                            dry_run=args.dry_run,
                        )
                    )
                    return 0
                if command_id == "market-backfill":
                    _print(
                        service.backfill(
                            canonical_symbol=args.symbol,
                            timeframe=args.timeframe,
                            start_at=_parse_datetime(args.start),
                            end_at=_parse_datetime(args.end),
                            dry_run=args.dry_run,
                        )
                    )
                    return 0
                if command_id == "market-collect":
                    _print(
                        service.collect_cycles(
                            cycles=args.cycles,
                            sleep_seconds=args.sleep_seconds,
                            dry_run=args.dry_run,
                        )
                    )
                    return 0
                _print(service.storage_check())
                return 0
            finally:
                service.close()
    except (CanonicalEnvMissingError, DuplicateEnvError, RuntimeError, ValueError) as exc:
        _print({"version": __version__, "phase": PHASE, "error": str(exc)})
        return 1
    return 2
