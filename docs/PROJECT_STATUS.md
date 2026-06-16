# Project Status

- Project: `openclaw_advisor_bot`
- Package version: `1.2.15`
- Phase: `P2.4`
- Current work package: `WP-P2_4-NFD002-AGENT-REGISTRY`
- Phase status: `REMEDIATION_IN_PROGRESS`
- Audit readiness: `NOT_READY`
- Audit gate: `BROWSER_SANDBOX_BLOCKED_UPSTREAM`
- Last update UTC: `2026-06-16T00:00:00Z`
- Audit baseline commit: `4d2cbe3ca01c6c319ad5c57b97c98f0fa0adbe4a`
- Report subject commit: `4274a0fc203ef173f11cd91c375d730cac6605a0`
- Validated subject commit: `4274a0fc203ef173f11cd91c375d730cac6605a0`
- Containing commit: resolve with `git log -1 --format=%H -- docs/PROJECT_STATUS.md`
- Provenance model: `non-self-referential-v1`
- Production gate: `HUMAN_RELEASE_GATE_CLOSED`

## Runtime Truth

| Gate | Status | Evidence |
| --- | --- | --- |
| Version sync | PASS_LOCAL | Package and phase metadata aligned to `1.2.15` / `P2.4` |
| Pip check | PASS_LOCAL | `python -m pip check` |
| Ruff | PASS_LOCAL | `python -m ruff check .` |
| Mypy | PASS_LOCAL | `python -m mypy engine\src` |
| Pytest non-live | PASS_LOCAL | `357 passed, 1 deselected` (baseline + Registry control-plane tests + SCA-001 regression test in 1.2.15; NFD-001 eliminated, NFD-002 Registry added) |
| Coverage gate | PASS_LOCAL | `85.20%` total (threshold 85.0%) |
| Skill validation | PASS_LOCAL | `openclaw-advisor validate-skills --strict`; `74 skills` |
| Agent validation | PASS_LOCAL | `openclaw-advisor validate-agents --strict`; `13 agents` |
| Agent registry validation | PASS_LOCAL | `openclaw-advisor validate-agent-registry --strict`; generated registry in sync with `workspace/agents/*/AGENT.md` |
| Routing validation | PASS_LOCAL | `openclaw-advisor validate-routing --strict` |
| Config validation | PASS_LOCAL | `openclaw-advisor render-config --validate --strict` |
| Security scan | PASS_LOCAL | `openclaw-advisor security-scan --include-history --strict` |
| Dependency audit | PASS_LOCAL | `python -m pip_audit --cache-dir /tmp/pip-audit-cache`; no known vulnerabilities found (local cache permission issue resolved with clean cache dir) |
| Telegram operator E2E | PASS_LOCAL | Operator flow verified |
| Market bot outbound | PASS_LOCAL | Outbound channel verified |
| Browser plugin E2E | BLOCKED_UPSTREAM | Codex-launched `node_repl.exe` fails in Windows sandbox bootstrap with `helper_unknown_error: apply deny-read ACLs` |
| Browser root cause | UPSTREAM_CODEX_RUNTIME_DEFECT | Failure occurs before user JavaScript / browser session |
| Browser failure subclass | HELPER_ERROR_PROPAGATION_BUG | Native error is collapsed to generic helper failure |
| GitHub CI/security | PASS_REMOTE | Validated subject commit `7a996e1b3b1d259bcdc376690510f943e0177bef`; CI `27601171398` success; security `27601171429` success |
| HUMAN_RELEASE_GATE | CLOSED | Required before production promotion |

## Findings

| Finding | Status | Evidence |
| --- | --- | --- |
| NFD-001 | CLOSED_LOCAL | `consume_event()` `now_utc` parameter injection; 21 deterministic boundary tests in `test_event_consumer_clock.py` |
| NFD-002 | CLOSED_REMOTE | Authoritative Agent Capability Registry implemented; 357 non-live tests pass; CI `27601171398` and security `27601171429` success on SHA `7a996e1b`; SCA-001 tuple decomposition bug found and closed inline |
| PPA-0001 | CLOSED_LOCAL | Non-self-referential provenance model adopted; `observed_remote_head`/`implementation_commit`/`status_report_commit`/`remediation_commit` removed |
| PPA-0002 | CLOSED_LOCAL | Gateway token paths are reconciled for the current runtime state |
| PPA-0003 | CLOSED_LOCAL | MAIN runtime manager tests remain green |
| PPA-0004 | CLOSED_LOCAL | Provenance and formula versioning remain enforced |
| PPA-0005 | CLOSED_LOCAL | Exact pytest temp-path invocation remains valid |
| PPA-0006 | CLOSED_LOCAL | Non-live coverage gate remains explicit and passing |
| PPA-0007 | CLOSED_LOCAL | Isolated Git worktree + dedicated venv confirms source import isolation |
| PPA-0008 | CLOSED_LOCAL | Session integrity warnings are remediated in the current runtime state |
| PPA-0009 | BLOCKED_UPSTREAM | Browser plugin E2E remains blocked by Codex sandbox bootstrap failure |
| PPA-0010 | CLOSED_LOCAL | Build/temp/coverage artifacts remain ignored correctly |

## Current Truth

Browser sandbox failure is classified as `BROWSER_SANDBOX_BLOCKED_UPSTREAM`, `UPSTREAM_CODEX_RUNTIME_DEFECT`, and `HELPER_ERROR_PROPAGATION_BUG`. Full soak is `NOT_READY_FOR_SOAK`. Remote validation is scoped to subject commit `4274a0fc203ef173f11cd91c375d730cac6605a0`. This document cannot embed its own containing commit SHA; resolve externally with `git log -1 --format=%H -- docs/PROJECT_STATUS.md`.
