from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ._version import PHASE, __version__
from .config import render_config, validate_rendered_config
from .env import CanonicalEnvMissingError, DuplicateEnvError, audit_environment
from .health import run_health_check_as_dict
from .market_data import build_market_data_service
from .paths import build_paths
from .scanning import perform_security_scan
from .skills import validate_skills


def _common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true")


def _market_parser(parser: argparse.ArgumentParser) -> None:
    _common_parser(parser)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")


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

    security_parser = subparsers.add_parser("security-scan")
    security_parser.set_defaults(command_id="security-scan")
    _common_parser(security_parser)
    security_parser.add_argument("--include-history", action="store_true")
    security_parser.add_argument("--strict", action="store_true")

    render_parser = subparsers.add_parser("render-config")
    render_parser.set_defaults(command_id="render-config")
    _common_parser(render_parser)
    render_parser.add_argument("--env-file", type=Path, default=None)
    render_parser.add_argument("--validate", action="store_true")
    render_parser.add_argument("--strict", action="store_true")

    mt5_health_parser = subparsers.add_parser("mt5-health", aliases=["market-health"])
    mt5_health_parser.set_defaults(command_id="mt5-health")
    _market_parser(mt5_health_parser)

    discover_parser = subparsers.add_parser(
        "mt5-discover-symbols",
        aliases=["discover-symbols"],
    )
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


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("datetime must include a UTC offset or Z suffix")
    return parsed.astimezone(UTC)


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
        if command_id == "validate-env":
            env_report = audit_environment(paths, env_path=env_file)
            _print(
                {
                    "version": __version__,
                    "phase": PHASE,
                    "valid": env_report.valid,
                    "env_path": str(env_report.env_path),
                    "statuses": env_report.statuses,
                    "issues": [issue.__dict__ for issue in env_report.issues],
                }
            )
            return 1 if strict and not env_report.valid else 0
        if command_id == "validate-skills":
            skill_env = env_file or paths.canonical_env_example_path
            rendered_config = render_config(paths, env_path=skill_env)
            skill_report = validate_skills(paths, rendered_config=rendered_config)
            _print(
                {
                    "version": skill_report.version,
                    "phase": skill_report.phase,
                    "valid": skill_report.valid,
                    "skill_names": list(skill_report.skill_names),
                    "issues": [issue.__dict__ for issue in skill_report.issues],
                    "runtime_issues": [issue.__dict__ for issue in skill_report.runtime_issues],
                }
            )
            return 1 if strict and not skill_report.valid else 0
        if command_id == "security-scan":
            security_report = perform_security_scan(paths, include_history=args.include_history)
            _print(security_report)
            summary = security_report.get("summary")
            passed = isinstance(summary, dict) and bool(summary.get("pass"))
            return 1 if strict and not passed else 0
        if command_id == "render-config":
            render_env = env_file or paths.canonical_env_example_path
            rendered_config = render_config(paths, env_path=render_env)
            payload: dict[str, object] = {
                "version": __version__,
                "phase": PHASE,
                "config": rendered_config,
            }
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
        if command_id in {
            "mt5-health",
            "mt5-discover-symbols",
            "market-snapshot",
            "market-backfill",
            "market-collect",
            "market-storage-check",
        }:
            market_env = env_file or paths.runtime_env_path
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
