---
name: blueprint-compliance-engineering
description: Verify code changes conform to agent topology, routing, and advisor-only constraints.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Block any work order result that violates the Blueprint before forwarding to auditor.
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

# Skill: blueprint-compliance-engineering

Owner: blueprint-coder
Phase: P2.4

## Purpose

Verify that every code change produced by blueprint-coder conforms to the Blueprint:
agent topology, routing allowlists, skill ownership, tool permissions, and the
advisor-only invariant.  A WorkOrderResult must not be forwarded to system-coder-auditor
until blueprint compliance is confirmed.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "changed_files": ["string (relative path)"],
  "scope": ["string (authorised scope from CodeWorkOrder)"],
  "blueprint_sections_affected": ["RUNTIME_AGENT_IDS", "AGENT_SKILL_NAMES", "routing", "..."]
}
```

## Procedure

1. Compare `changed_files` against `scope` from the CodeWorkOrder; flag any file outside scope.
2. If `constants.py` was modified:
   a. Confirm `RUNTIME_AGENT_IDS` is a tuple (not a list).
   b. Confirm every `agent_id` in `RUNTIME_AGENT_IDS` is listed in `AGENT_SKILL_NAMES`.
   c. Confirm `AGENT_ALLOWED_TOOLS` and `AGENT_DENIED_TOOLS` define a record for every agent.
3. If `agent_topology.py` was modified:
   a. Confirm `_agent_specs()` defines a spec for every agent in `RUNTIME_AGENT_IDS`.
   b. Confirm `REALTIME_ROUTE_ALLOWLIST`, `CODE_AUDIT_ROUTE_ALLOWLIST`, and
      `CODE_WORK_ORDER_ROUTE_ALLOWLIST` are exactly as declared in the Blueprint.
   c. Confirm `build_agent_topology` returns `len(RUNTIME_AGENT_IDS)` agents.
4. If any skill file was added or modified:
   a. Confirm the skill is listed in `AGENT_SKILL_NAMES` for the correct owner agent.
   b. Confirm the skill SKILL.md has: Purpose, Input Schema, Procedure, Gate Checklist,
      Decision Tree, Failure Modes.
5. Confirm `FORBIDDEN_SYMBOLS` are not introduced by any change.
6. Confirm no change introduces a new `write`, `edit`, or `exec` permission for agents other
   than blueprint-coder.
7. Confirm the advisor-only invariant: no change calls `order_send`, `position_close`,
   `TRADE_ACTION`, or any execution symbol listed in `FORBIDDEN_SYMBOLS`.

## Gate Checklist

| Gate | Condition |
|---|---|
| Scope compliance | All changed files are within CodeWorkOrder.scope |
| Topology integrity | RUNTIME_AGENT_IDS length unchanged or expected change documented |
| Routing correctness | All three route allowlists match declared constants |
| Skill ownership | Every new skill has one and only one owner agent |
| Advisor-only | No FORBIDDEN_SYMBOLS introduced in any changed file |
| Permission boundaries | No new write/exec permissions for read-only agents |

## Decision Tree

```
Compliance check requested
  ↓
Any changed file outside CodeWorkOrder.scope?
  YES → REJECT: out-of-scope change; list violations in WorkOrderResult
  NO  → Proceed through each gate
         ↓
         Any FORBIDDEN_SYMBOL introduced?
           YES → REJECT immediately; cannot proceed
           NO  → Continue
                 ↓
                 All gate checks pass? → PROCEED to system-coder-auditor
                 Any gate fails?       → REJECT with itemised violations
```

## Failure Modes

| Mode | Action |
|---|---|
| File modified outside scope | REJECT; include unauthorised path in WorkOrderResult.acceptance_criteria_unmet |
| Routing allowlist mismatch | REJECT; restore original allowlist and document the conflict |
| FORBIDDEN_SYMBOL introduced | REJECT immediately; this is a hard security violation |
| Skill added without owner | REJECT; add the skill to AGENT_SKILL_NAMES before committing |
