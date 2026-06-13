from __future__ import annotations

import json
from pathlib import Path

from openclaw_super_advisor.cli import main


def _run(command: list[str]) -> dict[str, object]:
    import sys
    from io import StringIO

    buffer = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = buffer
        exit_code = main(command)
    finally:
        sys.stdout = stdout
    assert exit_code == 0
    return json.loads(buffer.getvalue())


def test_cli_validation_commands(sample_project: Path) -> None:
    root = str(sample_project)
    env_file = str(sample_project / "state" / ".env")
    env_example = str(sample_project / ".env.example")

    health = _run(["health", "--project-root", root])
    env = _run(["validate-env", "--project-root", root, "--env-file", env_file])
    skills = _run(["validate-skills", "--project-root", root, "--env-file", env_example])
    security = _run(["security-scan", "--project-root", root])
    rendered = _run(
        ["render-config", "--project-root", root, "--env-file", env_example, "--validate"]
    )

    assert health["runtime_agent_id"] == "super-advisor"
    assert env["valid"] is True
    assert skills["valid"] is True
    assert security["summary"]["pass"] is True
    assert rendered["validation"]["valid"] is True
