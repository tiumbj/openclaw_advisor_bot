from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

MARKDOWN_REPORTS = [
    REPO_ROOT / "docs" / "PROJECT_STATUS.md",
    REPO_ROOT / "docs" / "IMPLEMENTATION_LEDGER.md",
    REPO_ROOT / "docs" / "P2_4_PREPRODUCTION_BLUEPRINT.md",
    REPO_ROOT / "docs" / "P2_4_BLUEPRINT_COMPLIANCE_MATRIX.md",
    REPO_ROOT / "docs" / "P2_4_PREPRODUCTION_READINESS_REPORT.md",
    REPO_ROOT / "docs" / "P2_4_PIPELINE_WIRING_AUDIT.md",
    REPO_ROOT / "docs" / "P2_4_AGENT_SKILL_MATRIX.md",
    REPO_ROOT / "docs" / "P2_4_TELEGRAM_MESSAGE_AUDIT.md",
    REPO_ROOT / "docs" / "P2_4_LEARNING_BACKUP_AUDIT.md",
    REPO_ROOT / "docs" / "P2_4_SELF_IMPROVEMENT_READINESS.md",
    REPO_ROOT / "docs" / "P2_4_POST_PATCH_AUDIT.md",
]

JSON_REPORTS = [
    REPO_ROOT / "docs" / "PROJECT_STATUS.json",
    REPO_ROOT / "docs" / "P2_4_PREPRODUCTION_BLUEPRINT.json",
    REPO_ROOT / "docs" / "P2_4_BLUEPRINT_COMPLIANCE_MATRIX.json",
    REPO_ROOT / "docs" / "P2_4_PREPRODUCTION_READINESS_REPORT.json",
    REPO_ROOT / "docs" / "P2_4_REPORT_PROVENANCE.json",
]

REQUIRED_STATUS_FIELDS = {
    "current_phase",
    "current_work_package",
    "phase_status",
    "implementation_commit",
    "status_report_commit",
    "observed_remote_head",
    "working_tree_status",
    "ci_status",
    "security_status",
    "groq_removal_status",
    "supported_providers",
    "selected_provider",
    "provider_static_validation",
    "real_provider_test",
    "gateway_status",
    "agent_status",
    "credit_blocker",
    "next_action",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"Authorization\s*:", re.IGNORECASE),
)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def test_markdown_reports_have_real_line_breaks() -> None:
    for path in MARKDOWN_REPORTS:
        data = _read_bytes(path)
        assert b"\n" in data, path
        assert b"\r\n" not in data, path


def test_json_reports_parse_and_are_pretty_printed() -> None:
    for path in JSON_REPORTS:
        text = path.read_text(encoding="utf-8")
        parsed = json.loads(text)
        assert isinstance(parsed, dict), path
        assert "\n  " in text, path
        assert text.endswith("\n"), path


def test_implementation_ledger_is_append_only() -> None:
    ledger = (REPO_ROOT / "docs" / "IMPLEMENTATION_LEDGER.md").read_text(encoding="utf-8")
    entries = [int(match.group(1)) for match in re.finditer(r"^## Entry (\d+)$", ledger, re.M)]
    assert entries == sorted(entries), entries
    assert len(entries) == len(set(entries)), entries
    assert entries[-1] == max(entries), entries


def test_status_file_contains_required_fields() -> None:
    status = json.loads((REPO_ROOT / "docs" / "PROJECT_STATUS.json").read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_STATUS_FIELDS.difference(status))
    assert not missing, missing


def test_reports_do_not_contain_secrets() -> None:
    report_paths = MARKDOWN_REPORTS + JSON_REPORTS
    for path in report_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"{path}: {pattern.pattern}"
