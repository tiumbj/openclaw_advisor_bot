---
name: runtime-pipeline-wiring
description: Wire agents, routes, skills, and constants into the runtime topology.
version: 1.2.14
owner_agent: blueprint-coder
purpose: Ensure RUNTIME_AGENT_IDS, allowlists, and config template remain consistent after wiring changes.
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

# Skill: runtime-pipeline-wiring

Owner: blueprint-coder
Phase: P2.4

## Purpose

Wire agents, routes, event consumers, and skill registrations into the runtime pipeline.
Changes here affect how the 13-agent topology receives, processes, and routes evidence.
Every wiring change must pass the full `validate_agent_topology` and `validate_routing`
checks before being included in a WorkOrderResult.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "wiring_target": "string (agent_id, route_name, or skill_name)",
  "wiring_intent": "ADD | REMOVE | MODIFY",
  "affected_constants": ["string (e.g. RUNTIME_AGENT_IDS, REALTIME_ROUTE_ALLOWLIST)"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Identify which constant(s) must change: `RUNTIME_AGENT_IDS`, `AGENT_SKILL_NAMES`,
   `REALTIME_ROUTE_ALLOWLIST`, `CODE_AUDIT_ROUTE_ALLOWLIST`, or `CODE_WORK_ORDER_ROUTE_ALLOWLIST`.
2. For ADD operations: confirm the new agent/skill/route does not conflict with the
   existing topology; confirm no disallowed route is introduced.
3. For REMOVE operations: confirm no existing test, SKILL.md, or route depends on the
   removed element; list all callers.
4. For MODIFY operations: confirm the change is backward compatible or all callers are updated.
5. Update `constants.py` first (the source of truth), then `agent_topology.py`, then the
   config template, then AGENTS.md.
6. Run `python -m pytest engine/tests/unit/test_blueprint_runtime.py` — all assertions must pass.
7. Run `python -m pytest engine/tests/unit/test_config_and_skills.py` — all assertions must pass.
8. Run `validate_agent_topology` and `validate_routing` programmatically; confirm `valid=True`.

## Gate Checklist

| Gate | Condition |
|---|---|
| Constants first | constants.py updated before agent_topology.py |
| Template synced | config/openclaw.template.json matches constants |
| AGENTS.md synced | Specialist agent table matches RUNTIME_AGENT_IDS |
| Unit tests pass | test_blueprint_runtime + test_config_and_skills pass |
| validate_agent_topology | Returns AgentTopologyReport(valid=True) |
| validate_routing | Returns RouteValidationReport(valid=True) |

## Decision Tree

```
Wiring change requested
  ↓
Is this an ADD of a new agent?
  YES → Add to RUNTIME_AGENT_IDS, AGENT_SKILL_NAMES, AGENT_ALLOWED_TOOLS,
        AGENT_DENIED_TOOLS, _agent_specs(), template, AGENTS.md
  NO  → Is this a route change?
          YES → Update the relevant *_ROUTE_ALLOWLIST constant AND template routing section
          NO  → Apply targeted change, then verify all 6 gates
```

## Failure Modes

| Mode | Action |
|---|---|
| template routing out of sync | Update template to match constants; run validate_routing |
| AGENTS.md missing new agent | Update the Specialist Agents table in AGENTS.md |
| test count assertion fails (== N) | Update the count assertion to match new RUNTIME_AGENT_IDS length |
