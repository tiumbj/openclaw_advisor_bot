from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Data\OpenClawSuperAdvisor")
DOCS = ROOT / "docs"
ARCHIVE = Path(r"C:\Data\OpenClaw_PreReset_Audit_20260613\OpenClawBot_Legacy.zip")
sys.path.insert(0, str(ROOT / "engine" / "src"))

from openclaw_super_advisor.health import run_health_check  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def write_env_report(report: dict[str, object]) -> None:
    lines = [
        "# Environment Required Report",
        "",
        "| Variable | Status |",
        "| --- | --- |",
    ]
    for name, status in sorted(report["env_status"].items()):
        lines.append(f"| {name} | {status} |")
    (DOCS / "ENV_REQUIRED_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_security_scan() -> None:
    payload = {
        "advisor_only": True,
        "execution_allowed": False,
        "legacy_archive_path": str(ARCHIVE),
        "workspace_env_exists": False,
        "engine_env_exists": False,
        "top_level_env_exists": False,
    }
    (DOCS / "SECURITY_SCAN.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_hash_report() -> None:
    tracked = []
    for path in ROOT.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            tracked.append({"path": str(path), "sha256": sha256(path)})
    (DOCS / "POST_INSTALL_SHA256.json").write_text(json.dumps(tracked, indent=2), encoding="utf-8")


def write_bootstrap_report(report: dict[str, object]) -> None:
    content = [
        "# Cleanroom Bootstrap Report",
        "",
        "Status: bootstrap foundation created",
        "",
        f"- Agent ID: {report['agent_id']}",
        f"- State path: {report['state_dir']}",
        f"- Config path: {report['config_path']}",
        f"- Workspace path: {report['workspace_path']}",
        f"- Legacy archive: {report['legacy_archive_path']}",
        f"- Allowed tools: {', '.join(report['allowed_tools'])}",
    ]
    (DOCS / "CLEANROOM_BOOTSTRAP_REPORT.md").write_text("\n".join(content) + "\n", encoding="utf-8")


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    report = run_health_check()
    payload = {
        "agent_id": report.agent_id,
        "state_dir": report.state_dir,
        "config_path": report.config_path,
        "workspace_path": report.workspace_path,
        "legacy_archive_path": report.legacy_archive_path,
        "allowed_tools": list(report.allowed_tools),
        "env_status": report.env_status,
    }
    write_env_report(payload)
    write_security_scan()
    write_hash_report()
    write_bootstrap_report(payload)


if __name__ == "__main__":
    main()
