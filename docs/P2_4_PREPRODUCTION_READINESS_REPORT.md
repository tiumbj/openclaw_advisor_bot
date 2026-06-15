# P2.4 Remediation Readiness Report

## Status

- Package version: `1.2.14`
- Phase: `P2.4`
- Work package: `WP-P2_4-NFD001-PROVENANCE-CLEAN-AUDIT`
- Phase status: `REMEDIATION_IN_PROGRESS`
- Audit readiness: `NOT_READY`
- Updated UTC: `2026-06-15T13:00:00Z`
- Audit baseline commit: `4d2cbe3ca01c6c319ad5c57b97c98f0fa0adbe4a`
- Report subject commit: `adebabca2665ea782bef6146fb27ef7d51b5fb12`
- Validated subject commit: `adebabca2665ea782bef6146fb27ef7d51b5fb12`
- Containing commit: resolve with `git log -1 --format=%H -- docs/P2_4_PREPRODUCTION_READINESS_REPORT.md`
- Provenance model: `non-self-referential-v1`

## Verdict

P2.4 remediation remains blocked from soak entry because the browser sandbox helper fails before a usable browser session starts. Telegram operator E2E and market outbound are verified PASS, but they do not satisfy the browser gate.

## Evidence

| Area | State | Evidence |
| --- | --- | --- |
| Non-live validation | PASS_LOCAL | `293 passed, 1 deselected` (272 baseline + 21 new boundary tests; NFD-001 eliminated) |
| Coverage | PASS_LOCAL | `85.89%` total (threshold 85.0%) |
| Skills / agents / routing / config | PASS_LOCAL | `validate-skills --strict` (`74 skills`), `validate-agents --strict` (`13 agents`), `validate-routing --strict`, `render-config --validate --strict` |
| Security scan | PASS_LOCAL | `security-scan --include-history --strict` |
| GitHub remote validation | PASS_REMOTE | Validated subject commit `adebabca2665ea782bef6146fb27ef7d51b5fb12`; CI `27552496423` success; security `27552496438` success |
| Dependency audit | TIMEOUT | `python -m pip_audit`; timed out twice in this workspace window; GitHub dependency scan is authoritative |
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
