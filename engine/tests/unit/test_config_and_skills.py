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
    assert len(rendered["agents"]["list"]) == 13  # type: ignore[index]
    tools = rendered["tools"]  # type: ignore[index]
    assert tools["allow"] == ["read", "session_status"]
    assert tools["exec"]["mode"] == "deny"
    assert tools["agentToAgent"]["enabled"] is False
    assert tools["elevated"]["enabled"] is False
    assert tools["sandbox"]["tools"]["allow"] == ["read", "session_status"]
    assert "memory_search" in tools["deny"]
    assert "sessions_yield" in tools["deny"]


def test_skill_validation_checks_frontmatter_and_runtime(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    report = validate_skills(paths, rendered_config=rendered)
    assert report.valid
    assert not report.issues
    assert not report.runtime_issues
