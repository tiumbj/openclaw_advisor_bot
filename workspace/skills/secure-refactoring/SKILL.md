---
name: secure-refactoring
description: Remove secrets, block FORBIDDEN_SYMBOLS, and harden path and privilege boundaries.
version: 1.2.13
owner_agent: blueprint-coder
purpose: Eliminate security findings flagged by scanning, pip_audit, or the security-compliance-agent.
allowed_inputs:
  - CodeWorkOrder
required_input_schema: object
output_schema: object
allowed_tools:
  - read
  - session_status
  - write
  - edit
  - apply_patch
denied_tools:
  - group:runtime
  - group:web
  - group:ui
  - group:automation
  - group:messaging
  - group:plugins
  - group:memory
  - group:sessions
  - process
  - code_execution
  - browser
  - canvas
  - gateway
  - message
  - subagents
  - memory_search
  - memory_get
  - sessions_list
  - sessions_history
  - sessions_send
  - sessions_spawn
  - sessions_yield
safety_constraints:
  - isolated-worktree-only
  - no secret access
  - no push/merge/deploy
  - no self-approval
  - human-release-gate-closed
failure_behavior: return WorkOrderResult with acceptance_criteria_unmet populated
audit_fields:
  - task_id
  - baseline_commit
  - changed_files
tests:
  - unit
  - integration
promotion_status: p2.4-hardening
---

# Skill: secure-refactoring

Owner: blueprint-coder
Phase: P2.4

## Purpose

Refactor Python source code to harden security boundaries: remove hardcoded
secrets, enforce deny-lists, eliminate path traversal vulnerabilities, and
ensure no FORBIDDEN_SYMBOL is reachable from any code path.  All refactoring
must preserve existing test coverage — no test may be removed to make the
refactoring appear to pass.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "security_finding": "string (description of the vulnerability or hardening target)",
  "affected_files": ["string (relative path)"],
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Read the full `security_finding` and classify it: secret exposure, path traversal,
   injection, privilege escalation, or advisor-only violation.
2. For secret exposure: replace any hardcoded value with an env-var reference via
   `load_settings()`; confirm the variable is in `.env.example` but NOT in `.env`.
3. For FORBIDDEN_SYMBOL: trace every call path that reaches the symbol; add a deny
   check at each call site; add a test that confirms the symbol is unreachable via
   the public API.
4. For path traversal: confirm all file open operations use `paths.root_dir / relative`
   and never construct paths from unvalidated user input.
5. For privilege escalation: confirm no agent other than blueprint-coder has `write`,
   `edit`, or `apply_patch` in its `AGENT_ALLOWED_TOOLS`.
6. Run `python -m pytest engine/tests/security/` — all security tests must pass.
7. Run the custom `validate-secrets` CLI command; confirm zero findings.
8. Run `python -m pip_audit`; document new findings in the WorkOrderResult (do not
   suppress or ignore them).

## Gate Checklist

| Gate | Condition |
|---|---|
| No hardcoded secrets | grep for SECRET_PATTERN returns zero hits in changed files |
| FORBIDDEN_SYMBOLS blocked | Unit test confirms public API cannot call forbidden symbol |
| Path traversal mitigated | All file ops use root_dir / relative construction |
| Security tests pass | engine/tests/security/ passes with zero failures |
| pip_audit findings documented | All findings listed in WorkOrderResult; not suppressed |

## Decision Tree

```
Security finding received
  ↓
Is severity CRITICAL?
  YES → Fix before any other change in this work order; do not proceed without passing gate
  NO  → Apply fix proportional to severity
        ↓
        Does fix require removing a test to pass?
          YES → REJECT the approach; find an alternative that keeps the test
          NO  → Proceed; run security tests
```

## Failure Modes

| Mode | Action |
|---|---|
| Secret found in committed history | Report to human (cannot rewrite history); add to FORBIDDEN_TRACKED_PATHS |
| FORBIDDEN_SYMBOL called by a library | Add a wrapper that raises AdvisorOnlyViolation; do not modify the library |
| pip_audit shows CRITICAL vulnerability | Document; human release gate MUST review before merge |
