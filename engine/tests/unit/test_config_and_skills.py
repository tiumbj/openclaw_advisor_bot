from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.config import render_config, validate_rendered_config
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.skills import validate_skills


def test_rendered_config_is_read_only(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    report = validate_rendered_config(rendered, paths)
    assert report.valid
    assert rendered["tools"] == {
        "allow": ["read", "session_status"],
        "deny": [
            "group:runtime",
            "group:web",
            "group:ui",
            "group:automation",
            "group:messaging",
            "group:plugins",
            "group:memory",
            "group:sessions",
            "write",
            "edit",
            "apply_patch",
            "exec",
            "process",
            "code_execution",
            "browser",
            "canvas",
            "gateway",
            "message",
            "subagents",
        ],
        "exec": {"mode": "deny"},
        "message": {"allowCrossContextSend": False, "actions": {"allow": []}},
        "agentToAgent": {"enabled": False},
        "elevated": {"enabled": False},
        "sandbox": {"tools": {"allow": ["read", "session_status"]}},
    }


def test_skill_validation_checks_frontmatter_and_runtime(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    report = validate_skills(paths, rendered_config=rendered)
    assert report.valid
    assert not report.issues
    assert not report.runtime_issues
