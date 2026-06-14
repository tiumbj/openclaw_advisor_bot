from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor._version import PHASE
from openclaw_super_advisor.health import run_health_check
from openclaw_super_advisor.paths import build_paths


def test_health_report_summary(sample_project: Path) -> None:
    report = run_health_check(build_paths(sample_project))
    assert report.version == "1.2.8"
    assert report.phase == PHASE
    assert report.config_valid
    assert report.skills_valid
    assert report.allowed_tools == ("read", "session_status")
