---
name: software-architecture-design
description: Design layered module architecture with enforced dependency direction.
version: 1.2.13
owner_agent: blueprint-coder
purpose: Maintain separation of concerns and prevent circular imports across the codebase.
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

# Skill: software-architecture-design

Owner: blueprint-coder
Phase: P2.4

## Purpose

Design and enforce module-level architecture decisions: layer separation,
dependency direction, public API surface, and elimination of circular imports.
All architecture changes must preserve the advisor-only invariant and keep the
Python pipeline as the single source of truth for market calculations.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "scope_modules": ["string (dotted path)"],
  "architecture_intent": "string",
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Build the import dependency graph for `scope_modules` using `python -m ruff` or
   manual inspection; record any circular imports as pre-existing violations.
2. Identify which layer each module belongs to: `constants` → `models` → `domain` →
   `adapters` → `cli`; flag any upward imports (adapters importing from cli, etc.).
3. Define the target architecture as a layered diagram in the WorkOrderResult diff summary.
4. Apply changes: move code, adjust imports, split or merge modules.
5. Confirm no new public symbol is exported from a lower layer that breaks layer isolation.
6. Confirm `RUNTIME_AGENT_IDS`, `AGENT_SKILL_NAMES`, and `SKILL_OWNERS` in `constants.py`
   remain the authoritative topology source (not duplicated in other modules).
7. Run `python -m ruff check . --select F401,E401,F811` to catch import issues.
8. Run `python -m mypy engine/src --strict` to confirm the new structure is type-safe.

## Gate Checklist

| Gate | Condition |
|---|---|
| No circular imports | ruff F401/F811 clean; manual graph check |
| Layer direction preserved | No upward dependency (lower layer → higher layer) |
| Constants single source | `RUNTIME_AGENT_IDS` defined only in constants.py |
| Topology contract intact | `build_agent_topology` still returns all registered agents |

## Decision Tree

```
Architecture change requested
  ↓
Is there a circular import in scope?
  YES → Resolve by extracting a shared types/protocols module
  NO  → Proceed
        ↓
        Does the change break layer direction?
          YES → Refactor to inject the dependency via constructor or config param
          NO  → Proceed
                ↓
                Does the change rename or remove a public constant used by tests?
                  YES → Update all callers; record in diff summary
                  NO  → PROCEED
```

## Failure Modes

| Mode | Action |
|---|---|
| Circular import cannot be resolved without moving tests | Move shared types to a `_types.py` module; do not move tests |
| Multiple modules export the same constant | Consolidate in `constants.py`; re-export from other modules with a deprecation comment |
| Architecture refactor breaks 5+ callers | Stage as two commits: (1) add new location, (2) migrate callers, (3) remove old location |
