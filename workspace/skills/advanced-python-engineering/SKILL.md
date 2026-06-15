---
name: advanced-python-engineering
description: Write production-grade typed Python with strict ruff and mypy compliance.
version: 1.2.13
owner_agent: blueprint-coder
purpose: Ensure every module satisfies strict type safety, lint, and frozen-dataclass invariants.
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

# Skill: advanced-python-engineering

Owner: blueprint-coder
Phase: P2.4

## Purpose

Write production-grade Python code that satisfies strict type safety, ruff lint,
and mypy strictness requirements.  Apply modern Python idioms where they reduce
defect surface: dataclasses, frozen types, structural pattern matching, protocol
classes, and `from __future__ import annotations` for forward references.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "target_module": "string (dotted path, e.g. openclaw_super_advisor.constants)",
  "change_description": "string",
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Read the current module source; identify all mypy and ruff violations.
2. Map every function, class, and constant to its declared and inferred type.
3. For each change: confirm it does not introduce a new `Any` annotation without justification.
4. Apply `from __future__ import annotations` if any forward references exist.
5. Use `@dataclass(frozen=True)` for value objects; use `@dataclass` only for mutable state.
6. Replace bare `dict`, `list`, `tuple` with generic forms (`dict[str, int]` etc.).
7. Prefer explicit `tuple[str, ...]` over `Sequence[str]` for fixed-length ordered data.
8. Remove all `type: ignore` comments unless the underlying mypy limitation is documented inline.
9. Run `python -m ruff check . --select ALL` and fix every reported violation.
10. Run `python -m mypy engine/src --strict` and fix every error.

## Gate Checklist

| Gate | Condition |
|---|---|
| ruff clean | zero violations from `ruff check . --select E,F,B,RUF,ARG` |
| mypy strict | zero errors from `mypy engine/src --strict` |
| no new `Any` | grep for `Any` shows no new occurrences vs baseline |
| frozen dataclasses | all value objects use `frozen=True` |
| no mutable defaults | no `field(default_factory=list)` on frozen dataclasses |

## Decision Tree

```
Change request received
  ↓
Does target module have existing mypy/ruff violations?
  YES → Fix pre-existing violations first (scope this in diff summary)
  NO  → Proceed to new change
        ↓
        Does new code introduce `Any` or `type: ignore`?
          YES → Document the reason or refactor to avoid it
          NO  → Proceed
                ↓
                All gate checks pass? → PROCEED
                Any gate fails?       → FIX_AND_RETRY (max 3 iterations)
                Still fails?          → REJECT (include diagnostics in WorkOrderResult)
```

## Failure Modes

| Mode | Action |
|---|---|
| ruff AUTO_FIX cannot resolve all issues | Apply manual fix; document in diff summary |
| mypy strict detects library stub gap | Add `py.typed` marker or `# type: ignore[import]` with inline comment |
| Frozen dataclass needs mutable field | Extract mutable field to separate mutable wrapper class |
| Forward reference cycle | Use `TYPE_CHECKING` guard and string annotation |
