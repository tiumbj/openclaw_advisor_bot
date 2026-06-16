---
name: root-cause-debugging
description: Identify root cause before patching; include a regression test that catches the bug.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Prevent symptom patching by requiring a root cause statement before any fix is applied.
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

# Skill: root-cause-debugging

Owner: blueprint-coder
Phase: P2.4

## Purpose

Identify the root cause of a bug or test failure before writing any fix.
Blueprint-coder must not patch symptoms.  Every fix must be preceded by a root
cause statement that references the specific line(s), invariant(s), or assumption(s)
that were violated.  The fix must also include a regression test that would have
caught the bug before the fix was written.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "failing_test_or_symptom": "string",
  "error_message": "string",
  "stack_trace": "string",
  "affected_files": ["string (relative path)"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Read the full stack trace; identify the innermost frame that belongs to
   `engine/src/openclaw_super_advisor/`.
2. Read the identified source file; find the specific line where the invariant breaks.
3. Write a root cause statement: "The bug is at `file:line` because `assumption` was
   violated when `condition`."
4. Write a minimal failing test that reproduces the bug on the baseline commit.
5. Confirm the test fails on baseline (expected: FAIL).
6. Apply the fix; confirm the test passes (expected: PASS).
7. Confirm the fix does not break any other test in `engine/tests/`.
8. Include the root cause statement in the WorkOrderResult diff summary.

## Gate Checklist

| Gate | Condition |
|---|---|
| Root cause statement | Written before any code change; references specific file:line |
| Regression test | Written before the fix; fails on baseline; passes after fix |
| No symptom patching | Fix addresses the root cause, not just the error message |
| Full test suite | All tests pass after fix; no previously-passing test regresses |

## Decision Tree

```
Bug report received
  ↓
Does the stack trace point inside engine/src/?
  YES → Trace to innermost openclaw frame; write root cause statement
  NO  → Is it a test infrastructure issue (conftest, fixture, path)?
          YES → Fix the test setup; document in WorkOrderResult
          NO  → Escalate to human; blueprint-coder does not debug library internals
                ↓
Root cause identified
  ↓
Is the fix a one-line change?
  YES → Check for similar patterns in the same module (may be systemic)
  NO  → Break into smallest possible change that fixes the root cause
```

## Failure Modes

| Mode | Action |
|---|---|
| Stack trace is truncated | Add `--tb=long` to pytest invocation; re-run to get full trace |
| Root cause is in a third-party library | Add a workaround wrapper; file a comment with the library version |
| Fix introduces a new test failure | Revert; identify why the fix was too broad; narrow the scope |
| Multiple root causes found | Fix them in priority order; one commit per root cause |
