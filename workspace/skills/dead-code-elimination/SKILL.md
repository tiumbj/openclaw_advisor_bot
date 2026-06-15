---
name: dead-code-elimination
description: Remove confirmed-dead code paths supported by static analysis and coverage evidence.
version: 1.2.13
owner_agent: blueprint-coder
purpose: Reduce cognitive load and security surface by eliminating unreachable symbols with evidence.
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

# Skill: dead-code-elimination

Owner: blueprint-coder
Phase: P2.4

## Purpose

Identify and remove confirmed-dead code paths: unreachable branches, unused
imports, unused functions, unused constants, and deprecated symbols that have
been replaced.  Dead code must be confirmed dead by static analysis AND test
coverage evidence before removal — never remove code solely because it looks
unused.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "target_module": "string (dotted path)",
  "dead_code_evidence": "string (ruff F401/F811 report or coverage report)",
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Run `python -m ruff check . --select F401,F811,F841` to identify unused
   imports, redefined names, and unused local variables.
2. Run `python -m pytest --cov=openclaw_super_advisor --cov-report=term-missing`
   to identify uncovered branches (look for `->` lines in the missing report).
3. For each candidate dead symbol: search all files in `engine/src/` and `engine/tests/`
   for any reference to the symbol; if found, it is NOT dead.
4. Confirm the symbol is not referenced in any SKILL.md, AGENT.md, or template file.
5. Remove the symbol; run the full test suite; confirm no test regresses.
6. Document each removed symbol in the WorkOrderResult with: module, line, reason confirmed dead.

## Gate Checklist

| Gate | Condition |
|---|---|
| Static analysis confirms unused | ruff F401/F811/F841 reports the symbol as unused |
| No hidden references | grep across engine/ and workspace/ finds zero references |
| Coverage confirms uncovered | coverage report shows 0 hits for the branch/function |
| Test suite intact | All tests pass after removal |
| WorkOrderResult documents removals | Each removed symbol listed with evidence |

## Decision Tree

```
Dead code candidate identified
  ↓
Does ruff report it as unused?
  NO  → Not dead by static analysis; do not remove
  YES → Does grep find any reference in engine/ or workspace/?
          YES → Not dead; it is used dynamically or from SKILL.md; do not remove
          NO  → Does coverage show 0 hits?
                  NO  → Branch is executed; do not remove
                  YES → Confirm removal is safe; remove; run tests
```

## Failure Modes

| Mode | Action |
|---|---|
| Symbol removed but test breaks | Restore; the grep missed a dynamic reference (e.g., `getattr(mod, name)`) |
| Coverage shows hits but ruff says unused | Coverage wins; do not remove; investigate why ruff is wrong |
| Removing import breaks mypy | The import was a type-only import; add `if TYPE_CHECKING:` guard instead |
