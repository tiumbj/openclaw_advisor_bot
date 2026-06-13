from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from openclaw_super_advisor._version import PHASE, __version__  # noqa: E402
from openclaw_super_advisor.config import render_config, validate_rendered_config  # noqa: E402
from openclaw_super_advisor.env import audit_environment  # noqa: E402
from openclaw_super_advisor.health import run_health_check_as_dict  # noqa: E402
from openclaw_super_advisor.paths import build_paths  # noqa: E402
from openclaw_super_advisor.scanning import perform_security_scan, write_scan_report  # noqa: E402
from openclaw_super_advisor.skills import validate_skills  # noqa: E402


def main() -> None:
    paths = build_paths(ROOT)
    paths.docs_dir.mkdir(parents=True, exist_ok=True)
    env_report = audit_environment(paths)
    rendered_config = render_config(paths, env_path=paths.canonical_env_example_path)
    config_report = validate_rendered_config(rendered_config, paths)
    skill_report = validate_skills(paths, rendered_config=rendered_config)
    security_report = perform_security_scan(paths, include_history=True)
    health_report = run_health_check_as_dict(paths)

    (paths.docs_dir / "P1_1_ENV_VALIDATION.json").write_text(
        json.dumps(
            {
                "version": __version__,
                "phase": PHASE,
                "valid": env_report.valid,
                "statuses": env_report.statuses,
                "issues": [issue.__dict__ for issue in env_report.issues],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (paths.docs_dir / "P1_1_RENDERED_CONFIG.json").write_text(
        json.dumps(
            {
                "version": __version__,
                "phase": PHASE,
                "config": rendered_config,
                "validation": {
                    "valid": config_report.valid,
                    "issues": [issue.__dict__ for issue in config_report.issues],
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (paths.docs_dir / "P1_1_SKILLS_VALIDATION.json").write_text(
        json.dumps(
            {
                "version": skill_report.version,
                "phase": skill_report.phase,
                "valid": skill_report.valid,
                "skills": list(skill_report.skill_names),
                "issues": [issue.__dict__ for issue in skill_report.issues],
                "runtime_issues": [issue.__dict__ for issue in skill_report.runtime_issues],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_scan_report(paths.docs_dir / "P1_1_SECURITY_SCAN.json", security_report)
    (paths.docs_dir / "P1_1_HEALTH.json").write_text(
        json.dumps(health_report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
