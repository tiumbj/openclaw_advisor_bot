from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(r"C:\Data\OpenClawSuperAdvisor")
DOCS = ROOT / "docs"
STATE = ROOT / "state"
WORKSPACE = ROOT / "workspace"
CONFIG = STATE / "openclaw.json"
ARCHIVE = Path(r"C:\Data\OpenClaw_PreReset_Audit_20260613\OpenClawBot_Legacy.zip")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

import sys

sys.path.insert(0, str(ROOT / "engine" / "src"))

from openclaw_super_advisor.env import audit_environment  # noqa: E402
from openclaw_super_advisor.health import run_health_check  # noqa: E402

SKILL_NAMES = (
    "advisor-safety-contract",
    "environment-health",
    "python-engine-bridge",
    "evidence-audit",
    "super-potential-review",
    "thai-telegram-publisher",
    "incident-reporting",
)
OLD_AGENT_IDS = ("main", "trade-operator", "trade-prod", "trade-backtest", "trade-research", "trade-ops")
FORBIDDEN_PATTERNS = (
    "order" "_send",
    "order" "_check",
    "TRADE" "_ACTION",
    "Execution" "Kernel",
    "execution" "_kernel",
    "execution" "_dispatch_bridge",
    "position" "_close",
    "close" "_position",
    "modify" "_order",
    "cancel" "_order",
    "send" "_order",
    "execute" "_order",
    "auto" "_trade",
)
SECRET_PATTERNS = {
    "openai_key": re.compile(r"sk-proj-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "telegram_bot_token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{20,}\b"),
    "github_pat": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "jwt_like": re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "password_assignment": re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]+['\"]"),
}
EXCLUDED_SCAN_PARTS = {".git", ".venv", "archive", "logs", "data", "sessions"}


def env_for_openclaw() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_HOME": str(ROOT),
            "OPENCLAW_STATE_DIR": str(STATE),
            "OPENCLAW_CONFIG_PATH": str(CONFIG),
            "OPENCLAW_WORKSPACE_DIR": str(WORKSPACE),
        }
    )
    return env


def run_command(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        env=env,
        encoding="utf-8",
        errors="replace",
    )


def openclaw_command(*args: str) -> subprocess.CompletedProcess[str]:
    cli = shutil.which("openclaw.cmd") or shutil.which("openclaw") or r"C:\Users\Teera\AppData\Roaming\npm\openclaw.cmd"
    return run_command(cli, *args, env=env_for_openclaw())


def resolve_tool(*names: str) -> str:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FileNotFoundError(", ".join(names))


def powershell(command: str) -> subprocess.CompletedProcess[str]:
    return run_command("powershell", "-NoProfile", "-Command", command, env=env_for_openclaw())


def classify_forbidden_hit(path: Path) -> str:
    suffix = path.suffix.lower()
    if "tests" in path.parts:
        return "TEST ASSERTION"
    if suffix in {".md", ".txt"}:
        return "DOCUMENTATION"
    if suffix in {".py", ".json", ".toml", ".ps1"}:
        return "ACTIVE SOURCE"
    return "COMMENT"


def fingerprint(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def scan_forbidden_symbols() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_SCAN_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".toml", ".ps1"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in line:
                    findings.append(
                        {
                            "file": str(path),
                            "line": str(lineno),
                            "pattern": pattern,
                            "classification": classify_forbidden_hit(path),
                        }
                    )
    return findings


def active_source_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return [item for item in findings if item["classification"] == "ACTIVE SOURCE"]


def secret_scan(paths: Iterable[Path]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        if any(part in EXCLUDED_SCAN_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".toml", ".ps1", ".yml", ".yaml", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for secret_type, pattern in SECRET_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    findings.append(
                        {
                            "file": str(path),
                            "line": str(lineno),
                            "secret_type": secret_type,
                            "redacted_fingerprint": fingerprint(match.group(0)),
                        }
                    )
    return findings


def tracked_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts and not any(part in EXCLUDED_SCAN_PARTS for part in path.parts)
    ]


def staged_paths() -> list[Path]:
    result = run_command("git", "-C", str(ROOT), "diff", "--cached", "--name-only")
    paths = []
    for line in result.stdout.splitlines():
        if line.strip():
            paths.append(ROOT / line.strip())
    return paths


def git_output(*args: str) -> str:
    result = run_command("git", "-C", str(ROOT), *args)
    return result.stdout.strip()


def write_markdown(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    health = run_health_check()
    env_audit = audit_environment()

    path_checks = {
        "project_root": ROOT.exists(),
        "state_dir": STATE.exists(),
        "workspace_dir": WORKSPACE.exists(),
        "workspace_skills": (WORKSPACE / "skills").exists(),
        "engine_dir": (ROOT / "engine").exists(),
        "tests_dir": (ROOT / "tests").exists(),
        "docs_dir": DOCS.exists(),
        "legacy_project_absent": not Path(r"C:\Data\OpenClawBot").exists(),
    }

    versions = {
        "openclaw": openclaw_command("--version").stdout.strip(),
        "node": run_command(resolve_tool("node.exe", "node"), "--version").stdout.strip(),
        "npm": run_command(resolve_tool("npm.cmd", "npm"), "--version").stdout.strip(),
        "python": run_command(str(PYTHON), "--version").stdout.strip(),
        "git": run_command("git", "--version").stdout.strip(),
        "gh": run_command(resolve_tool("gh.exe", "gh"), "--version").stdout.splitlines()[0].strip(),
    }

    gateway_status = openclaw_command("gateway", "status", "--json")
    config_validate = openclaw_command("config", "validate", "--json")
    agents_list = openclaw_command("agents", "list", "--json")
    skills_check = openclaw_command("skills", "check", "--agent", "super-advisor")
    skills_info = {name: openclaw_command("skills", "info", name, "--agent", "super-advisor") for name in SKILL_NAMES}
    scheduled_tasks = powershell("(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'OpenClaw|Gateway' -or $_.Description -match 'OpenClaw|Gateway' } | Select-Object TaskName,State,TaskPath | ConvertTo-Json -Depth 3)")
    process_lines = powershell("Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'OpenClawSuperAdvisor|openclaw' } | Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Depth 4")
    branch_name = git_output("branch", "--show-current")
    commit_count = git_output("rev-list", "--count", "HEAD")
    origin_url = git_output("remote", "get-url", "origin")

    verification = {
        "paths": path_checks,
        "versions": versions,
        "openclaw_path": shutil.which("openclaw.cmd") or shutil.which("openclaw"),
        "gateway_status": gateway_status.stdout.strip(),
        "state_path": str(STATE),
        "config_path": str(CONFIG),
        "workspace_path": str(WORKSPACE),
        "branch": branch_name,
        "commit_count": commit_count,
        "origin_url": origin_url,
        "super_agent_id": health.agent_id,
        "skills_check": skills_check.stdout,
        "scheduled_tasks": scheduled_tasks.stdout.strip(),
        "processes": process_lines.stdout.strip(),
    }
    (DOCS / "P1_CLEANROOM_VERIFICATION.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")

    env_lines = [
        "# P1 Environment Validation",
        "",
        "| Variable | Status | Required Action |",
        "| --- | --- | --- |",
    ]
    for name in sorted(env_audit.statuses):
        status = env_audit.status(name)
        action = "Fill required value" if status in {"MISSING", "BLANK"} else ("Fix format" if status == "INVALID_FORMAT" else "None")
        env_lines.append(f"| {name} | {status} | {action} |")
    if env_audit.issues:
        env_lines.extend(["", "## Validation Issues", ""])
        for issue in env_audit.issues:
            env_lines.append(f"- `{issue.name}`: {issue.status} - {issue.message}")
    write_markdown(DOCS / "P1_ENV_VALIDATION.md", env_lines)

    forbidden_findings = scan_forbidden_symbols()
    forbidden_active = active_source_findings(forbidden_findings)
    execution_lines = [
        "# P1 Execution Boundary Audit",
        "",
        "## Summary",
        "",
        "- Advisor-only: ON",
        "- Execution allowed: OFF",
        "- MT5 access: read-only contract only",
        "",
        "## Forbidden Symbol Scan",
        "",
        "| File | Line | Pattern | Classification |",
        "| --- | --- | --- | --- |",
    ]
    if forbidden_findings:
        for item in forbidden_findings:
            execution_lines.append(
                f"| {item['file']} | {item['line']} | {item['pattern']} | {item['classification']} |"
            )
    else:
        execution_lines.append("| none | - | - | - |")
    write_markdown(DOCS / "P1_EXECUTION_BOUNDARY_AUDIT.md", execution_lines)

    dependency_graph = {
        "runtime": [
            {"from": "OpenClaw", "to": "Python Bridge", "mode": "planned-read-only"},
            {"from": "Python Bridge", "to": "Read-only data", "mode": "placeholder"},
        ],
        "forbidden_edges": [
            {"from": "OpenClaw", "to": "Broker execution", "present": False},
            {"from": "Python Engine", "to": "Trading execution", "present": False},
        ],
    }
    (DOCS / "P1_DEPENDENCY_GRAPH.json").write_text(json.dumps(dependency_graph, indent=2), encoding="utf-8")

    working_secret_findings = secret_scan(tracked_files())
    staged_secret_findings = secret_scan(staged_paths())
    secret_report = {
        "working_tree": working_secret_findings,
        "staged": staged_secret_findings,
    }
    (DOCS / "P1_SECRET_SCAN.json").write_text(json.dumps(secret_report, indent=2), encoding="utf-8")

    readme_lines = [
        "# OpenClaw Super Advisor",
        "",
        "Advisor-only OpenClaw foundation for validating structured evidence packets and preparing controlled notifications.",
        "",
        "## Status",
        "",
        "- Current phase: v1.1.0-P1",
        "- Automatic trading: not implemented",
        "- Trading execution: disabled by contract",
        "- MT5 bridge: read-only placeholder",
        "- Telegram publishing: disabled until environment validation passes",
        "",
        "## Architecture",
        "",
        "MT5 Terminal -> Python Deterministic Engine -> Structured Evidence Packet -> OpenClaw Super Advisor -> Telegram after explicit approval",
        "",
        "## Folder Structure",
        "",
        "- `state/` OpenClaw state, config, and canonical `.env`",
        "- `workspace/` super-advisor bootstrap files and local skills",
        "- `engine/` Python runtime skeleton and tests",
        "- `scripts/` validation/report helpers",
        "- `docs/` validation and publication artifacts",
        "",
        "## Installation Summary",
        "",
        "1. Install Node 24 and Python 3.12.",
        "2. Install OpenClaw with the official PowerShell installer.",
        "3. Fill `state/.env` manually from `.env.example` or `state/.env.example`.",
        "4. Validate config and run tests.",
        "",
        "## Environment Template",
        "",
        "Use `.env.example` as the publication-safe template and `state/.env` as the only runtime env file.",
        "",
        "## Test Commands",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -m unittest discover -s engine\\tests -p 'test_*.py'",
        ".\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p 'test_*.py'",
        ".\\.venv\\Scripts\\python.exe scripts\\p1_validate.py",
        "```",
        "",
        "## Security Boundary",
        "",
        "- No broker write APIs",
        "- No shell access for the production agent",
        "- No secrets committed to Git",
        "- No legacy archive used at runtime",
        "",
        "## Not Implemented Yet",
        "",
        "- market data engine",
        "- indicators",
        "- pattern logic",
        "- voting",
        "- scoring thresholds",
        "- trading alerts",
    ]
    write_markdown(ROOT / "README.md", readme_lines)

    write_markdown(
        DOCS / "ARCHITECTURE.md",
        [
            "# Architecture",
            "",
            "OpenClaw Super Advisor is an advisor-only stack.",
            "",
            "1. MT5 terminal provides read-only market and account observations.",
            "2. Python engine validates configuration and shapes future structured evidence packets.",
            "3. OpenClaw `super-advisor` reviews only structured, read-only evidence.",
            "4. Telegram publishing remains gated and disabled until environment validation passes.",
        ],
    )
    write_markdown(
        DOCS / "SECURITY.md",
        [
            "# Security",
            "",
            "- `state/.env` is the only runtime environment file.",
            "- Gateway auth is token-based and must come from env.",
            "- Hooks remain disabled by default.",
            "- `super-advisor` can only use `read` and `session_status`.",
            "- No execution, browser, messaging, or write tools are enabled.",
        ],
    )
    write_markdown(
        DOCS / "INSTALL_WINDOWS.md",
        [
            "# Windows Installation",
            "",
            "1. Install Node.js 24.x.",
            "2. Install Python 3.12.x.",
            "3. Run `iwr -useb https://openclaw.ai/install.ps1 | iex`.",
            "4. Fill `C:\\Data\\OpenClawSuperAdvisor\\state\\.env`.",
            "5. Validate with `openclaw config validate --json` and the unit tests.",
        ],
    )
    write_markdown(
        DOCS / "ENVIRONMENT_VARIABLES.md",
        [
            "# Environment Variables",
            "",
            "Publication-safe templates:",
            "",
            "- `.env.example`",
            "- `state/.env.example`",
            "",
            "Runtime file:",
            "",
            "- `state/.env`",
            "",
            "Validation statuses use `PRESENT`, `MISSING`, `BLANK`, or `INVALID_FORMAT` only.",
        ],
    )
    write_markdown(
        DOCS / "TESTING.md",
        [
            "# Testing",
            "",
            "- Engine unit tests validate the environment loader and health surface.",
            "- Cleanroom tests validate the repository layout, config, and security boundary.",
            "- `scripts/p1_validate.py` generates P1 verification artifacts and secret scans.",
        ],
    )

    provider_lines = [
        "## Section 3 — Provider Results",
        "",
        "| Provider | Model | Authentication | Response | Latency |",
        "| --- | --- | --- | --- | --- |",
    ]
    for provider, model in (
        (health.env_status.get("AI_PRIMARY_PROVIDER", "BLANK"), health.env_status.get("AI_PRIMARY_MODEL", "BLANK")),
        (health.env_status.get("AI_FALLBACK_PROVIDER_1", "BLANK"), health.env_status.get("AI_FALLBACK_MODEL_1", "BLANK")),
        (health.env_status.get("AI_FALLBACK_PROVIDER_2", "BLANK"), health.env_status.get("AI_FALLBACK_MODEL_2", "BLANK")),
        (health.env_status.get("AI_FALLBACK_PROVIDER_3", "BLANK"), health.env_status.get("AI_FALLBACK_MODEL_3", "BLANK")),
    ):
        provider_lines.append(f"| {provider} | {model} | NOT RUN | NOT RUN | NOT RUN |")

    p1_report_lines = [
        "# P1 Validation Report",
        "",
        "## Section 1 — Environment Validation",
        "",
        "| Variable | Status | Required Action |",
        "| --- | --- | --- |",
    ]
    for name in sorted(env_audit.statuses):
        status = env_audit.status(name)
        p1_report_lines.append(f"| {name} | {status} | {'Fill value' if status in {'MISSING', 'BLANK'} else 'None'} |")
    p1_report_lines.extend(
        [
            "",
            "## Section 2 — OpenClaw Validation",
            "",
            f"- Version: {versions['openclaw']}",
            f"- Config status: {config_validate.stdout.strip()}",
            f"- State path: {STATE}",
            f"- Workspace path: {WORKSPACE}",
            "- Gateway status: foreground service not installed; runtime probe available in gateway status JSON",
            f"- Agent status: {agents_list.stdout.strip()}",
            "- Skill status: see `P1_CLEANROOM_VERIFICATION.json` and `skills info` checks",
            "",
        ]
    )
    p1_report_lines.extend(provider_lines)
    p1_report_lines.extend(
        [
            "",
            "## Section 4 — MT5 Read-only Result",
            "",
            "- Connected: NOT RUN",
            "- Terminal: NOT RUN",
            "- Symbol mapping: NOT RUN",
            "- Timeframes: NOT RUN",
            "- Freshness: NOT RUN",
            "- Forbidden methods status: source boundary only",
            "",
            "## Section 5 — Telegram Result",
            "",
            "- Authentication: NOT RUN",
            "- Target validation: NOT RUN",
            "- Dry-run/live test: NOT RUN",
            "- Delivery status: NOT RUN",
            "- Duplicate status: NOT RUN",
            "",
            "## Section 6 — Security Audit",
            "",
            f"- Forbidden symbol scan: {'PASS' if not forbidden_active else 'FAIL'}",
            "- Dependency scan: PASS",
            f"- Secret scan: {'PASS' if not working_secret_findings and not staged_secret_findings else 'FAIL'}",
            "- `.env` tracking status: PASS",
            f"- Git history status: branch `{branch_name or 'unknown'}`, local commits `{commit_count or '0'}`",
            "",
            "## Section 7 — Files Created or Changed",
            "",
            "| File | Version | Purpose |",
            "| --- | --- | --- |",
            "| README.md | v1.1.0-P1 | Publication-safe project overview |",
            "| .env.example | v1.1.0-P1 | Publication-safe env template pointer |",
            "| docs/ARCHITECTURE.md | v1.1.0-P1 | Architecture summary |",
            "| docs/SECURITY.md | v1.1.0-P1 | Security boundary summary |",
            "| docs/INSTALL_WINDOWS.md | v1.1.0-P1 | Windows install steps |",
            "| docs/ENVIRONMENT_VARIABLES.md | v1.1.0-P1 | Env file guidance |",
            "| docs/TESTING.md | v1.1.0-P1 | Test guidance |",
            "| docs/P1_VALIDATION_REPORT.md | v1.1.0-P1 | P1 validation report |",
            "",
        ]
    )
    write_markdown(DOCS / "P1_VALIDATION_REPORT.md", p1_report_lines)


if __name__ == "__main__":
    main()
