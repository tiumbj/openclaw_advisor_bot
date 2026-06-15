# P2.4 Remediation Readiness Report

## Status

- Package version: `1.2.13`
- Phase: `P2.4`
- Work package: `WP-P2_4-BROWSER-SANDBOX-PROVENANCE-RECONCILIATION`
- Phase status: `REMEDIATION_IN_PROGRESS`
- Audit readiness: `NOT_READY`
- Updated UTC: `2026-06-15T08:35:00Z`
- Audit baseline commit: `4d2cbe3ca01c6c319ad5c57b97c98f0fa0adbe4a`
- Audit report commit: `SELF_REFERENTIAL_EVIDENCE_RECONCILIATION_COMMIT_SEE_GIT_HEAD`

## Verdict

P2.4 remediation remains blocked from soak entry because the browser sandbox helper fails before a usable browser session starts. Telegram operator E2E and market outbound are verified PASS, but they do not satisfy the browser gate.

## Evidence

| Area | State | Evidence |
| --- | --- | --- |
| Non-live validation | PASS_LOCAL | `272 passed, 1 deselected` |
| Coverage | PASS_LOCAL | `85.81%` total coverage |
| Skills / agents / routing / config | PASS_LOCAL | `validate-skills --strict`, `validate-agents --strict`, `validate-routing --strict`, `render-config --validate --strict` |
| Security scan | PASS_LOCAL | `security-scan --include-history --strict` |
| Dependency audit | TIMEOUT | `python -m pip_audit`; timed out twice in this workspace window |
| Telegram operator E2E | PASS_LOCAL | operator flow verified |
| Market bot outbound | PASS_LOCAL | outbound channel verified |
| Browser plugin E2E | BLOCKED_UPSTREAM | Codex-launched `node_repl.exe` fails in Windows sandbox bootstrap with `helper_unknown_error: apply deny-read ACLs` |
| Browser root cause | UPSTREAM_CODEX_RUNTIME_DEFECT | Failure is upstream to repository code |
| Browser failure subclass | HELPER_ERROR_PROPAGATION_BUG | Native failure is translated to a generic helper error |
| Full soak | NOT_READY_FOR_SOAK | Required browser E2E remains blocked |
| Production gate | CLOSED | `HUMAN_RELEASE_GATE_CLOSED` |

## Required Closure

1. Reconcile browser sandbox escalation evidence in the repository.
2. Push the documentation/evidence commit and verify the GitHub workflow conclusions.
3. Keep browser disabled for production until a human-approved upstream fix exists.
4. Do not start the 24-hour soak.
