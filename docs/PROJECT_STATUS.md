# Project Status

- Project: `openclaw_advisor_bot`
- Current package version: `1.2.11`
- Current phase: `P2.4`
- Current work package: `WP-P2_4-PPA-0001-0010-REMEDIATION`
- Phase status: `REMEDIATION_IN_PROGRESS`
- Audit readiness: `NOT_READY`
- Last update UTC: `2026-06-15T02:00:00Z`
- Audit baseline commit: `d44da0983b38408575ceedfccb00b909862ff9f0`
- Audit report commit: `e725e25cffa0d497920e9dad72521ece5b7ae4f2`
- Remediation commit: `PENDING_COMMIT`
- Production gate: `HUMAN_RELEASE_GATE_CLOSED`

## Gate Truth

| Gate | Status | Evidence |
| --- | --- | --- |
| Version sync | PASS_LOCAL | Package, README, `.env.example`, AGENTS, tests, and 56 skills updated to `1.2.11` |
| Ruff | PASS_LOCAL | `python -m ruff check .` |
| Mypy | PASS_LOCAL | `python -m mypy engine\src` |
| Pip check | PASS_LOCAL | `python -m pip check` |
| Pytest non-live exact | PASS_LOCAL | `python -m pytest -m "not live" -q --basetemp ._tmp\audit-pytest`; `217 passed, 1 deselected` |
| Unit subset | PASS_LOCAL | `python -m pytest engine\tests\unit -q`; `174 passed` |
| Integration subset | PASS_LOCAL | `python -m pytest engine\tests\integration -q`; `37 passed` |
| Security subset | PASS_LOCAL | `python -m pytest engine\tests\security -q`; `6 passed` |
| Full-suite coverage gate | PASS_LOCAL | `217 passed, 1 deselected`; coverage total `87.73%`, threshold `85%` |
| Skill validation | PASS_LOCAL | `openclaw-advisor validate-skills --strict`; resolved project root emitted |
| Agent validation | PASS_LOCAL | `openclaw-advisor validate-agents --strict`; resolved project root emitted |
| Routing validation | PASS_LOCAL | `openclaw-advisor validate-routing --strict`; resolved project root emitted |
| Config validation | PASS_LOCAL | `openclaw-advisor render-config --validate --strict` |
| Security scan | PASS_LOCAL | `openclaw-advisor security-scan --include-history --strict`; active source violations `0` |
| Dependency audit | PASS_LOCAL | `python -m pip_audit`; no known vulnerabilities found |
| Package build | PASS_LOCAL | `python -m build`; built `openclaw_advisor_foundation-1.2.11` artifacts |
| FRED live validation | PASS_LOCAL | `scripts/audit/fred_live_check.py`; credential masked, `DGS10` valid, `DTWEXBGS` stale daily macro |
| OpenClaw gateway/UI script | PARTIAL | websocket/session/agent turn passed; script still reports token consistency/status parse warnings |
| Browser plugin E2E | BLOCKED | in-app Browser bootstrap fails with Windows sandbox ACL `apply deny-read ACLs` |
| GitHub CI/Security | NOT_RUN_FOR_REMEDIATION | Must run after remediation commit is pushed |

## Finding Status

| Finding | Status | Evidence |
| --- | --- | --- |
| PPA-0001 | OPEN | New provenance model/report publication attestation still needs post-push workflow evidence |
| PPA-0002 | PARTIAL | `gateway.auth.token` and `gateway.remote.token` migrated to env SecretRef; `openclaw secrets audit` still finds unrelated local plaintext provider key |
| PPA-0003 | CLOSED_LOCAL | `MainRuntimeManager` implements graph validation, routing, result validation, conflict handling, checkpoint/recovery, pause/resume/stop, idempotency and human release gate; unit/integration tests pass |
| PPA-0004 | CLOSED_LOCAL | Tick/bar schemas and event envelopes enforce explicit provenance/realtime class; computed values require `formula_version`; tests pass |
| PPA-0005 | CLOSED_LOCAL | Exact pytest `--basetemp ._tmp\audit-pytest` passes from repo without manual directory creation |
| PPA-0006 | CLOSED_LOCAL | Functional subset pytest commands pass without coverage fail-under; explicit full-suite coverage gate remains strict |
| PPA-0007 | CLOSED_LOCAL | Root resolver prefers current checkout / `OPENCLAW_ADVISOR_ROOT`, rejects invalid explicit root, and validators emit resolved root |
| PPA-0008 | PARTIAL | Missing command owner and session integrity warnings remediated; Telegram route/message doctor warning remains unresolved in installed OpenClaw runtime |
| PPA-0009 | PARTIAL | Live FRED validation passes; Browser plugin E2E remains blocked by sandbox ACL |
| PPA-0010 | CLOSED_LOCAL | Build/temp/coverage artifacts ignored; env duplicate detector ignores `._tmp` pytest fixtures |

## Current Truth

Remediation is not ready for independent re-audit PASS. Production remains blocked by `HUMAN_RELEASE_GATE_CLOSED`.
