---
name: release-and-rollback-planning
description: Produce release checklist and rollback plan for human review; never open the release gate.
version: 1.2.14
owner_agent: blueprint-coder
purpose: Document all quality gates and rollback steps so a human reviewer can safely execute the release.
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

# Skill: release-and-rollback-planning

Owner: blueprint-coder
Phase: P2.4

## Purpose

Produce a structured release checklist and rollback plan for every work order
that passes blueprint compliance, audit, and security review.  Blueprint-coder
cannot execute the release — only a human reviewer may open the HUMAN_RELEASE_GATE.
This skill produces the checklist; it does not perform the release.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "worktree_branch": "string (blueprint/<task_id>)",
  "changed_files": ["string"],
  "test_outcome": "PASS | FAIL | PARTIAL",
  "lint_outcome": "CLEAN | VIOLATIONS",
  "mypy_outcome": "CLEAN | ERRORS",
  "acceptance_criteria_met": ["string"],
  "acceptance_criteria_unmet": ["string"]
}
```

## Procedure

1. Confirm `test_outcome == "PASS"`, `lint_outcome == "CLEAN"`, `mypy_outcome == "CLEAN"`,
   and `acceptance_criteria_unmet` is empty before producing the release checklist.
   If any of these is not satisfied, produce a BLOCKED checklist with reasons.
2. Produce the release checklist:
   a. Gate 1 — system-coder-auditor review: PASSED (verified by route)
   b. Gate 2 — security-compliance-agent review: PASSED (verified by route)
   c. Gate 3 — 24h soak period: PENDING (human must wait)
   d. Gate 4 — HUMAN_RELEASE_GATE: CLOSED (human must open manually)
   e. Gate 5 — merge to main: BLOCKED UNTIL GATE 4 OPEN
3. Produce the rollback plan:
   a. `git revert <commit_range>` — reverts the blueprint commit without destroying history
   b. Re-run `python -m pytest` after revert to confirm rollback is clean
   c. Notify human operator of rollback via standard incident channel
4. Include both the checklist and rollback plan in the WorkOrderResult.

## Gate Checklist

| Gate | Condition |
|---|---|
| All acceptance_criteria met | acceptance_criteria_unmet is empty |
| All quality gates PASS | test=PASS, lint=CLEAN, mypy=CLEAN |
| human_release_gate_required | Must be True in the CodeWorkOrder |
| HUMAN_RELEASE_GATE | Remains CLOSED in this document; human opens it |
| Rollback plan | Specific `git revert` command included; tested in worktree |

## Decision Tree

```
Release checklist requested
  ↓
All acceptance criteria met?
  NO  → Produce BLOCKED checklist; list unmet criteria; STOP
  YES → All quality gates pass?
          NO  → Produce BLOCKED checklist; list failing gates; STOP
          YES → Produce release checklist with all gates; include rollback plan
                ↓
                Add to WorkOrderResult; route to system-coder-auditor
                HUMAN_RELEASE_GATE = CLOSED
```

## Failure Modes

| Mode | Action |
|---|---|
| Some acceptance criteria met but not all | Produce PARTIAL checklist; list unmet criteria explicitly |
| Rollback `git revert` cannot be applied cleanly | Document the conflict; provide manual rollback steps |
| human tries to open release gate via agent | Reject; HUMAN_RELEASE_GATE can only be opened by a human outside the agent system |

## Hard Constraint

**HUMAN_RELEASE_GATE must remain CLOSED.**
Blueprint-coder produces a release checklist as evidence for human review.
It cannot set AUDIT_READINESS to READY or HUMAN_RELEASE_GATE to OPEN.
Final verdict: REMEDIATION_IN_PROGRESS / AUDIT_READINESS=NOT_READY / HUMAN_RELEASE_GATE=CLOSED.
