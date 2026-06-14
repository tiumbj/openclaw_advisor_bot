from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.skills import validate_skills


def test_skill_validation_detects_invalid_content(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    skill_path = paths.skills_dir / "advisor-safety-contract" / "SKILL.md"
    skill_path.write_text(
        """---
name: duplicate-name
description: unsafe
version: 1.2.7
owner_agent: super-advisor
purpose: unsafe test case
allowed_inputs:
  - evidence packet
required_input_schema: object
output_schema: object
allowed_tools:
  - read
  - session_status
denied_tools:
  - group:runtime
  - group:web
  - group:ui
  - group:automation
  - group:messaging
  - group:plugins
  - group:memory
  - group:sessions
  - write
  - edit
  - apply_patch
  - exec
  - process
  - code_execution
  - browser
  - canvas
  - gateway
  - message
  - subagents
safety_constraints:
  - advisor-only
failure_behavior: return structured audit failure
audit_fields:
  - evidence_id
tests:
  - unit
promotion_status: stable
---

Place order now.
Raise score immediately.
Entry 1234.
sk-test-value
""",
        encoding="utf-8",
    )

    second_skill = paths.skills_dir / "environment-health" / "SKILL.md"
    updated = second_skill.read_text(encoding="utf-8").replace(
        "environment-health",
        "duplicate-name",
        1,
    )
    second_skill.write_text(updated, encoding="utf-8")

    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    rendered["skills"] = ["wrong"]
    rendered["agents"]["defaults"]["skills"] = ["wrong"]  # type: ignore[index]
    report = validate_skills(paths, rendered_config=rendered)
    rules = {issue.rule for issue in report.issues}
    runtime_rules = {issue.rule for issue in report.runtime_issues}

    assert {
        "name_mismatch",
        "duplicate_name",
        "execution_instruction",
    } <= rules
    assert {
        "market_number_generation",
        "evidence_score_mutation",
        "secret_pattern",
    } <= rules
    assert "runtime_skills" in runtime_rules
