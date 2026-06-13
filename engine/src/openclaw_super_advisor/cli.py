from __future__ import annotations

import argparse
import json
from pathlib import Path

from ._version import PHASE, __version__
from .config import render_config, validate_rendered_config
from .env import CanonicalEnvMissingError, DuplicateEnvError, audit_environment
from .health import run_health_check_as_dict
from .paths import build_paths
from .scanning import perform_security_scan
from .skills import validate_skills


def _common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openclaw-advisor")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health")
    _common_parser(health_parser)

    env_parser = subparsers.add_parser("validate-env")
    _common_parser(env_parser)
    env_parser.add_argument("--env-file", type=Path, default=None)
    env_parser.add_argument("--strict", action="store_true")

    skills_parser = subparsers.add_parser("validate-skills")
    _common_parser(skills_parser)
    skills_parser.add_argument("--env-file", type=Path, default=None)
    skills_parser.add_argument("--strict", action="store_true")

    security_parser = subparsers.add_parser("security-scan")
    _common_parser(security_parser)
    security_parser.add_argument("--include-history", action="store_true")
    security_parser.add_argument("--strict", action="store_true")

    render_parser = subparsers.add_parser("render-config")
    _common_parser(render_parser)
    render_parser.add_argument("--env-file", type=Path, default=None)
    render_parser.add_argument("--validate", action="store_true")
    render_parser.add_argument("--strict", action="store_true")

    return parser


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = build_paths(args.project_root)
    env_file = args.env_file if hasattr(args, "env_file") else None
    strict = bool(getattr(args, "strict", False))
    try:
        if args.command == "health":
            _print(run_health_check_as_dict(paths))
            return 0
        if args.command == "validate-env":
            env_report = audit_environment(paths, env_path=env_file)
            env_payload = {
                "version": __version__,
                "phase": PHASE,
                "valid": env_report.valid,
                "env_path": str(env_report.env_path),
                "statuses": env_report.statuses,
                "issues": [issue.__dict__ for issue in env_report.issues],
            }
            _print(env_payload)
            return 1 if strict and not env_report.valid else 0
        if args.command == "validate-skills":
            skill_env = env_file or paths.canonical_env_example_path
            rendered_config = render_config(paths, env_path=skill_env)
            skill_report = validate_skills(paths, rendered_config=rendered_config)
            skill_payload = {
                "version": skill_report.version,
                "phase": skill_report.phase,
                "valid": skill_report.valid,
                "skill_names": list(skill_report.skill_names),
                "issues": [issue.__dict__ for issue in skill_report.issues],
                "runtime_issues": [issue.__dict__ for issue in skill_report.runtime_issues],
            }
            _print(skill_payload)
            return 1 if strict and not skill_report.valid else 0
        if args.command == "security-scan":
            security_report = perform_security_scan(paths, include_history=args.include_history)
            _print(security_report)
            summary = security_report.get("summary")
            passed = False
            if isinstance(summary, dict):
                passed = bool(summary.get("pass"))
            return 1 if strict and not passed else 0
        if args.command == "render-config":
            render_env = env_file or paths.canonical_env_example_path
            rendered_config = render_config(paths, env_path=render_env)
            render_payload: dict[str, object] = {
                "version": __version__,
                "phase": PHASE,
                "config": rendered_config,
            }
            if args.validate:
                validation = validate_rendered_config(rendered_config, paths)
                render_payload["validation"] = {
                    "valid": validation.valid,
                    "issues": [issue.__dict__ for issue in validation.issues],
                }
                _print(render_payload)
                return 1 if strict and not validation.valid else 0
            _print(render_payload)
            return 0
    except (CanonicalEnvMissingError, DuplicateEnvError, RuntimeError, ValueError) as exc:
        _print({"version": __version__, "phase": PHASE, "error": str(exc)})
        return 1
    return 2
