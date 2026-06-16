---
name: logic-conflict-remediation
description: Resolve contradictory decisions between agents or pipeline stages.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Apply canonical tie-break rules to produce a single authoritative decision from conflicting outputs.
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

# Skill: logic-conflict-remediation

Owner: blueprint-coder
Phase: P2.4

## Purpose

Identify and resolve logic conflicts between agents, skills, or pipeline stages
where two components produce contradictory decisions for the same input.  The
canonical resolution rule is: Python-computed evidence outranks agent-advisory
text; newer formula_version outranks older; explicit REJECT outranks HOLD outranks
PROCEED.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "conflict_description": "string",
  "component_a": "string (agent_id or skill_name)",
  "component_b": "string (agent_id or skill_name)",
  "conflicting_output_a": "object (the decision from component A)",
  "conflicting_output_b": "object (the decision from component B)",
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Reproduce the conflict by writing a test that feeds the same input to both
   components and asserts that their outputs differ.
2. Determine which component's output is authoritative using the resolution rule:
   python > agent; newer formula_version > older; REJECT > HOLD > PROCEED.
3. If the authoritative component is correct: fix the non-authoritative component
   to align with the authoritative one.
4. If both components are incorrect: escalate to the relevant skill owners for review;
   do not guess which is right.
5. If the conflict is in routing (two routes compete for the same event): apply the
   route allowlist; the allowlist is always authoritative.
6. Write a regression test that confirms the conflict is resolved and cannot recur.
7. Update the relevant SKILL.md with the tie-break rule if it was not previously documented.

## Gate Checklist

| Gate | Condition |
|---|---|
| Conflict reproduced | Test shows both outputs before fix |
| Resolution rule applied | Documented: which rule applied and why |
| Regression test | Test confirms conflict cannot recur |
| SKILL.md updated | Tie-break rule documented in the affected skill |
| No new conflict | Full test suite passes; no new conflicting decision paths |

## Decision Tree

```
Logic conflict identified
  ↓
Is one output from the Python pipeline and the other from an agent?
  YES → Python pipeline wins; fix the agent output
  NO  → Do both outputs carry formula_version?
          YES → Newer formula_version wins
          NO  → Apply REJECT > HOLD > PROCEED rule
                ↓
                Is the winning output actually correct?
                  YES → Fix the losing component
                  NO  → Escalate to human; do not auto-resolve when both are wrong
```

## Failure Modes

| Mode | Action |
|---|---|
| Resolution rule is ambiguous | Add a test that freezes the expected output; document the decision in WorkOrderResult |
| Conflict recurs after fix | The fix addressed a symptom; go back to root cause debugging |
| Conflict is between two Python modules | Use formula_version tie-break; if equal, flag for human review |
