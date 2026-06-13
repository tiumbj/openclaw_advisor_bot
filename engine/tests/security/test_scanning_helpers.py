from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.scanning import (
    _classify_path,
    _iter_files,
    _module_constants,
    _resolve_import,
    _resolve_string,
    perform_security_scan,
    scan_ast_for_file,
    scan_git_history,
    scan_paths_for_secrets,
    staged_paths,
    tracked_runtime_state_violations,
    write_scan_report,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def test_scanning_helpers_and_git_modes(sample_project: Path) -> None:
    root = sample_project
    paths = build_paths(root)
    report_path = root / "docs" / "scan.json"

    assert _classify_path(root / "docs" / "x.md") == "DOCUMENTATION"
    assert _classify_path(root / "engine" / "tests" / "x.py") == "TEST_ONLY"
    assert _classify_path(root / "app.py") == "ACTIVE_SOURCE"
    assert _resolve_import("demo.module") == "demo.module"
    assert _resolve_import(".relative") is None

    node = ast.parse('NAME = "order" "_send"\n').body[0]
    assert isinstance(node, ast.Assign)
    constants = _module_constants(ast.parse('NAME = "order" "_send"\n'))
    assert _resolve_string(node.value, constants) == "order_send"
    assert _resolve_string(ast.parse("name", mode="eval").body, constants) is None

    (root / "safe.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "docs" / "secret.txt").write_text("ghp_12345678901234567890\n", encoding="utf-8")
    (root / "state" / "openclaw.json").write_text("{}\n", encoding="utf-8")

    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")

    staged_secret = root / "staged.txt"
    staged_secret.write_text("ghp_abcdefghijabcdefghij\n", encoding="utf-8")
    _git(root, "add", "staged.txt")

    history_findings = scan_git_history(paths)
    working_findings = scan_paths_for_secrets([root / "docs" / "secret.txt"], "working_tree")
    staged = staged_paths(paths)
    tracked = tracked_runtime_state_violations(paths)
    ast_findings = scan_ast_for_file(root / "safe.py")

    assert list(_iter_files(paths))
    assert history_findings
    assert working_findings[0].secret_type == "github_pat"
    assert staged and staged[0].name == "staged.txt"
    assert tracked == ["state\\.env", "state\\openclaw.json"]
    assert ast_findings == []

    report = perform_security_scan(paths, include_history=True)
    write_scan_report(report_path, report)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["runtime_state_tracking"]["tracked_forbidden_paths"] == [
        "state\\.env",
        "state\\openclaw.json",
    ]
    assert saved["secrets"]["history"]
