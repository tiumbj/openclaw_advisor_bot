from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Audit report payloads intentionally preserve exact command strings and evidence excerpts.
# Keep long evidence strings readable in the generated report source.
# ruff: noqa: E501


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "pre_production_audit"
BASELINE_COMMIT = "d44da0983b38408575ceedfccb00b909862ff9f0"
GENERATED_AT_UTC = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return (result.stdout or result.stderr).strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload.setdefault("baseline_commit", BASELINE_COMMIT)
    payload.setdefault("generated_at_utc", GENERATED_AT_UTC)
    payload["evidence_hash_sha256"] = sha256_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    )
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def write_md(path: Path, title: str, body: str) -> None:
    evidence_hash = sha256_text(
        json.dumps(
            {
                "baseline_commit": BASELINE_COMMIT,
                "generated_at_utc": GENERATED_AT_UTC,
                "title": title,
                "body": body,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    text = (
        f"# {title}\n\n"
        f"- Baseline commit: `{BASELINE_COMMIT}`\n"
        f"- Generated UTC: `{GENERATED_AT_UTC}`\n"
        f"- Evidence hash SHA256: `{evidence_hash}`\n\n"
        f"{body.rstrip()}\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def finding(
    finding_id: str,
    severity: str,
    category: str,
    component: str,
    expected: str,
    actual: str,
    evidence: list[str],
    impact: str,
    remediation: str,
) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "severity": severity,
        "category": category,
        "blueprint_requirement_id": "P2.4-PRE-PRODUCTION-AUDIT",
        "component": component,
        "files": [],
        "functions_or_lines": [],
        "expected_behavior": expected,
        "actual_behavior": actual,
        "reproduction_steps": evidence,
        "evidence": evidence,
        "root_cause": actual,
        "impact": impact,
        "exploitability_or_failure_probability": "Observed during independent audit.",
        "remediation": remediation,
        "verification_required": [
            "Re-run independent audit command evidence from a clean checkout.",
            "Verify GitHub CI and security on the remediation commit.",
        ],
        "status": "OPEN",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    current_head = run(["git", "rev-parse", "HEAD"])
    origin_head = run(["git", "rev-parse", "origin/main"])
    branch = run(["git", "branch", "--show-current"])

    findings = [
        finding(
            "PPA-0001",
            "HIGH",
            "report-truth",
            "P2.4 status reports",
            "Committed reports must identify the actual audited HEAD and final GitHub run IDs.",
            "PROJECT_STATUS.json still records observed_remote_head, implementation_commit, and "
            "github_gates for 286224e while actual HEAD is d44da09.",
            [
                "git rev-parse HEAD -> d44da0983b38408575ceedfccb00b909862ff9f0",
                "docs/PROJECT_STATUS.json observed_remote_head -> 286224ec29e0a6881ed3a7003db5b63ec3ba233e",
                "docs/PROJECT_STATUS.json github_gates -> runs 27516318293/27516318322 on 286224e",
                "actual final runs observed before audit -> 27516473364/27516473368 on d44da09",
            ],
            "A next auditor cannot rely on Git reports alone to reconstruct final provenance.",
            "Update reports from generated evidence after the final status commit, then re-run CI/security.",
        ),
        finding(
            "PPA-0002",
            "HIGH",
            "runtime-security",
            "OpenClaw runtime configuration",
            "Runtime config must keep secret-bearing fields out of plaintext-readable config.",
            "openclaw doctor warns that state/openclaw.json contains plaintext secret-bearing "
            "gateway.auth.token.",
            [
                "openclaw doctor -> WARNING: openclaw.json contains plaintext secret-bearing config fields",
                "affected path reported by doctor: gateway.auth.token",
            ],
            "Agents or tools with config read access may expose runtime auth material.",
            "Migrate gateway token to SecretRef or OpenClaw secret store and verify with deep security audit.",
        ),
        finding(
            "PPA-0003",
            "HIGH",
            "architecture-runtime",
            "MAIN agent manager",
            "MAIN must be a runtime orchestrator with capability-based routing, validation, conflict "
            "resolution, max hops, pause/stop/resume, and recovery idempotency.",
            "Production source exposes only simple MainPlanner and AgentRouter helpers; no executable "
            "MAIN runtime loop, result validator, conflict resolver, recovery resume, or idempotent "
            "dispatch path was found.",
            [
                "engine/src/openclaw_super_advisor/main_agent/planner.py has build_plan only",
                "engine/src/openclaw_super_advisor/main_agent/router.py classifies routes by allowlist membership",
                "rg did not identify MAIN result validator or conflict resolver implementation",
            ],
            "Blueprint requirements for MAIN runtime behavior are not proven by production code.",
            "Implement and test the MAIN runtime manager before release-gate consideration.",
        ),
        finding(
            "PPA-0004",
            "HIGH",
            "data-provenance",
            "Market data schemas",
            "All market numerics must carry provenance including realtime_class.",
            "TickRecord and BarRecord contain data_quality but no realtime_class field.",
            [
                "engine/src/openclaw_super_advisor/market_data/schemas.py TickRecord fields omit realtime_class",
                "engine/src/openclaw_super_advisor/market_data/schemas.py BarRecord fields omit realtime_class",
                "workspace/skills/data-provenance-contract requires realtime_class",
            ],
            "Agents and downstream logic cannot reliably distinguish realtime, stale, unknown, and daily macro data.",
            "Add realtime_class/provenance to schemas and enforce it in ingestion, storage, and event validation.",
        ),
        finding(
            "PPA-0005",
            "MEDIUM",
            "clean-validation",
            "Pytest command reproducibility",
            "Required audit command must run from clean checkout exactly as specified.",
            "python -m pytest -m \"not live\" -q --basetemp .\\_tmp\\audit-pytest fails when .\\_tmp "
            "does not already exist.",
            [
                "exact command returned FileNotFoundError for .\\_tmp\\audit-pytest",
                "after creating .\\_tmp in audit clone, the same test selection passed: 197 passed, 1 deselected",
            ],
            "Required validation is not directly reproducible without an undocumented setup step.",
            "Make the command create its parent temp directory or document and automate the setup in CI/audit scripts.",
        ),
        finding(
            "PPA-0006",
            "MEDIUM",
            "test-configuration",
            "Required pytest subsets",
            "Required unit, integration, and security subset commands should be runnable audit gates.",
            "Running each subset alone fails the global coverage fail-under gate even when tests pass.",
            [
                "python -m pytest engine\\tests\\unit -q -> 155 passed but coverage 87.06 in one run; "
                "parallel run demonstrated coverage pollution risk",
                "python -m pytest engine\\tests\\integration -q -> 36 passed but coverage 76.81, exit 1",
                "python -m pytest engine\\tests\\security -q -> 6 passed but coverage 21.74, exit 1",
            ],
            "The required validation list cannot be interpreted unambiguously as independent gates.",
            "Separate coverage-gated full suite from subset functional gates or combine coverage across subsets.",
        ),
        finding(
            "PPA-0007",
            "MEDIUM",
            "audit-isolation",
            "OpenClaw advisor CLI validators",
            "Clean clone validation must operate on the checkout under audit.",
            "Advisor validator outputs resolved paths to C:\\Data\\OpenClawSuperAdvisor instead of the "
            "isolated clone path, indicating editable-install/root resolution contamination.",
            [
                "openclaw-advisor validate-agents --strict output paths point to C:\\Data\\OpenClawSuperAdvisor\\state",
                "command was run from C:\\Data\\OpenClawSuperAdvisor\\_audit_workspace",
            ],
            "A clean-checkout audit can silently validate the wrong working tree or state directory.",
            "Require OPENCLAW_ADVISOR_ROOT or reinstall package from the checkout before validators run.",
        ),
        finding(
            "PPA-0008",
            "MEDIUM",
            "runtime-health",
            "OpenClaw doctor and agent tool policy",
            "Runtime health checks should have no unresolved warnings before pre-production approval.",
            "openclaw doctor reports missing command owner, message tool unavailable for telegram route, "
            "stale/missing session transcript state, and minimal profile policy warnings.",
            [
                "openclaw doctor reports command owner not configured",
                "openclaw doctor reports super-advisor routed from telegram but message tool unavailable",
                "openclaw doctor reports recent sessions missing transcripts and orphan transcript file",
            ],
            "Operational ownership, Telegram behavior, and forensic session integrity are not release-ready.",
            "Resolve doctor warnings or explicitly accept them with risk owner and compensating controls.",
        ),
        finding(
            "PPA-0009",
            "MEDIUM",
            "required-live-evidence",
            "FRED and browser live evidence",
            "Pre-production PASS requires live FRED validation and browser E2E evidence.",
            "No FRED_API_KEY/live FRED result was available in audit evidence; Browser plugin bootstrap "
            "failed with sandbox ACL before in-app browser E2E could run.",
            [
                "FRED_API_KEY not configured in committed .env.example and no live credential evidence recorded",
                "Browser plugin node runtime failed: windows sandbox apply deny-read ACLs",
                "script-level UI E2E passed, but browser-plugin E2E was not obtained",
            ],
            "Live data and browser readiness cannot be approved.",
            "Provide live FRED credential in secure runtime and rerun browser plugin E2E in an environment "
            "where the plugin can start.",
        ),
        finding(
            "PPA-0010",
            "LOW",
            "build-cleanliness",
            "Package build",
            "Audit/build commands should not leave untracked generated artifacts unless ignored or cleaned.",
            "python -m build generated dist/ and egg-info artifacts in the audit clone.",
            [
                "git status --short in audit clone after build -> M docs/P2_COVERAGE.json, ?? dist/",
            ],
            "Repeated audit runs can accumulate local noise and obscure source changes.",
            "Update ignore/cleanup policy for generated build and coverage outputs.",
        ),
    ]

    severity_counts: dict[str, int] = {}
    for item in findings:
        severity_counts[item["severity"]] = severity_counts.get(item["severity"], 0) + 1

    verdict = "PRE_PRODUCTION_AUDIT_FAIL - REMEDIATION_REQUIRED"
    common = {
        "baseline": {
            "branch": branch,
            "baseline_commit": BASELINE_COMMIT,
            "current_head_at_generation": current_head,
            "origin_main_at_generation": origin_head,
            "package_version": "1.2.10",
            "phase": "P2.4",
        },
        "verdict": verdict,
        "severity_counts": severity_counts,
        "command_evidence": [
            {"command": "python -m pip check", "status": "PASS"},
            {"command": "python -m ruff check .", "status": "PASS"},
            {"command": "python -m mypy engine\\src", "status": "PASS"},
            {
                "command": "python -m pytest -m \"not live\" -q --basetemp .\\_tmp\\audit-pytest",
                "status": "FAIL_THEN_PASS_AFTER_PARENT_TEMP_CREATED",
            },
            {"command": "python -m build", "status": "PASS_WITH_SETuptools_LICENSE_DEPRECATION"},
            {"command": "python -m pip_audit", "status": "PASS"},
            {"command": "openclaw-advisor security-scan --include-history --strict", "status": "PASS"},
            {"command": ".\\scripts\\Start-OpenClawUI.ps1", "status": "PASS"},
            {"command": ".\\scripts\\Test-OpenClawUI.ps1", "status": "PASS"},
            {"command": "openclaw doctor", "status": "WARNINGS_PRESENT"},
        ],
    }

    write_json(OUT / "FINDINGS.json", {**common, "findings": findings})
    findings_md = "\n\n".join(
        f"## {f['finding_id']} {f['severity']} - {f['category']}\n\n"
        f"- Component: `{f['component']}`\n"
        f"- Expected: {f['expected_behavior']}\n"
        f"- Actual: {f['actual_behavior']}\n"
        f"- Impact: {f['impact']}\n"
        f"- Remediation: {f['remediation']}\n"
        f"- Status: `{f['status']}`\n"
        for f in findings
    )
    write_md(OUT / "FINDINGS.md", "Independent Pre-production Audit Findings", findings_md)

    summary_body = (
        f"Verdict: `{verdict}`\n\n"
        f"Severity counts: `{json.dumps(severity_counts, sort_keys=True)}`\n\n"
        "The audit did not patch production implementation. Required live FRED evidence and "
        "browser-plugin E2E evidence were not available. Multiple HIGH and MEDIUM findings remain open."
    )
    write_md(OUT / "EXECUTIVE_SUMMARY.md", "Independent Pre-production Audit Executive Summary", summary_body)
    write_json(OUT / "FINAL_VERDICT.json", {**common, "decision": verdict, "pass_allowed": False})

    traceability = {
        **common,
        "traceability": [
            {
                "requirement": "MAIN runtime orchestration",
                "implementation": "planner/router helpers only",
                "evidence": "PPA-0003",
                "risk": "HIGH",
            },
            {
                "requirement": "Data numerics carry realtime_class provenance",
                "implementation": "TickRecord/BarRecord omit realtime_class",
                "evidence": "PPA-0004",
                "risk": "HIGH",
            },
            {
                "requirement": "FRED live validation",
                "implementation": "unit tests only, no live credential evidence",
                "evidence": "PPA-0009",
                "risk": "MEDIUM",
            },
            {
                "requirement": "Runtime operator readiness",
                "implementation": "doctor warnings remain",
                "evidence": "PPA-0008",
                "risk": "MEDIUM",
            },
        ],
    }
    write_json(OUT / "BLUEPRINT_TRACEABILITY.json", traceability)
    write_md(
        OUT / "BLUEPRINT_TRACEABILITY.md",
        "Blueprint Traceability",
        "\n".join(
            f"- `{row['requirement']}` -> {row['implementation']} -> {row['evidence']} -> {row['risk']}"
            for row in traceability["traceability"]
        ),
    )

    write_json(OUT / "TEST_EVIDENCE.json", common)
    write_md(
        OUT / "TEST_EVIDENCE.md",
        "Test Evidence",
        "\n".join(f"- `{e['command']}`: `{e['status']}`" for e in common["command_evidence"]),
    )
    write_json(OUT / "RUNTIME_E2E.json", {**common, "runtime_e2e": "script_ui_pass_browser_plugin_blocked"})
    write_md(
        OUT / "RUNTIME_E2E.md",
        "Runtime E2E",
        "Script-level gateway and UI E2E passed. Browser plugin E2E was blocked by sandbox ACL.",
    )

    category_payloads = {
        "AGENT_ISOLATION_AUDIT.json": ["PPA-0003", "PPA-0007", "PPA-0008"],
        "SKILL_SEMANTIC_AUDIT.json": ["PPA-0004", "PPA-0009"],
        "DATA_PIPELINE_AUDIT.json": ["PPA-0004", "PPA-0009"],
        "INTERMARKET_AUDIT.json": ["PPA-0009"],
        "RECOVERY_CHAOS_AUDIT.json": ["PPA-0008", "PPA-0009"],
        "PERSISTENCE_AUDIT.json": ["PPA-0008"],
        "BACKUP_RESTORE_AUDIT.json": ["PPA-0008", "PPA-0009"],
        "SECURITY_AUDIT.json": ["PPA-0002", "PPA-0008"],
        "PERFORMANCE_SOAK_AUDIT.json": ["PPA-0009"],
    }
    for filename, refs in category_payloads.items():
        write_json(
            OUT / filename,
            {
                **common,
                "referenced_findings": refs,
                "status": "FAIL" if any(ref != "PPA-0010" for ref in refs) else "WARN",
            },
        )

    backlog = "\n".join(
        f"- `{f['finding_id']}` `{f['severity']}` {f['component']}: {f['remediation']}"
        for f in findings
        if f["severity"] != "LOW"
    )
    write_md(OUT / "REMEDIATION_BACKLOG.md", "Remediation Backlog", backlog)
    write_md(
        OUT / "AI_HANDOFF_STATUS.md",
        "AI Handoff Status",
        "Independent audit verdict is remediation required. Do not start human release gate until "
        "OPEN findings are remediated and re-audited.",
    )
    write_json(
        OUT / "AI_HANDOFF_STATUS.json",
        {**common, "next_action": "remediate_open_findings_then_reaudit"},
    )

    files = sorted(p for p in OUT.iterdir() if p.is_file())
    manifest_entries = []
    for file_path in files:
        manifest_entries.append(
            {
                "path": str(file_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
            }
        )
    write_json(
        OUT / "AUDIT_MANIFEST.json",
        {
            **common,
            "files": manifest_entries,
            "report_count": len(manifest_entries) + 1,
        },
    )


if __name__ == "__main__":
    main()
