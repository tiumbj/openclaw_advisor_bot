---
name: algorithm-and-logic-design
description: Design and verify pure deterministic algorithms for market feature computation.
version: 1.2.13
owner_agent: blueprint-coder
purpose: Guarantee correctness, determinism, and formula_version traceability for all feature functions.
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

# Skill: algorithm-and-logic-design

Owner: blueprint-coder
Phase: P2.4

## Purpose

Design, verify, and implement algorithms for market feature computation, signal
scoring, deduplication, and event validation.  Every algorithm must be pure
(no side effects), deterministic given the same inputs, and covered by at least
one property-based test that validates its invariants.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "algorithm_name": "string",
  "inputs_description": "string",
  "outputs_description": "string",
  "invariants": ["string"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Write the algorithm specification as a docstring with inputs, outputs, and complexity.
2. List all edge cases: empty inputs, single element, all-equal values, NaN, infinity.
3. Implement the algorithm; return `FeatureResult` with `quality_status="INSUFFICIENT_DATA"`
   for inputs below minimum length rather than raising exceptions.
4. Write at least one unit test per edge case identified in step 2.
5. Write at least one property-based test (Hypothesis) that asserts each invariant from
   the `invariants` field.
6. Verify the algorithm produces the same output for the same input across 100 random seeds.
7. Check that no `float` operation produces `nan` or `inf` in normal operating range
   (XAUUSD 1000–3500 USD, RSI 0–100, ATR 0.1–50.0).
8. Confirm `formula_version` matches the module-level `FORMULA_VERSION` constant.

## Gate Checklist

| Gate | Condition |
|---|---|
| Pure function | No global mutation, no I/O, no datetime.now() calls |
| Deterministic | 100 identical-input runs produce identical output |
| Edge-case coverage | Unit tests cover empty, single, NaN-equivalent, below-minimum |
| Invariant tests | At least one Hypothesis test per listed invariant |
| formula_version | All FeatureResult objects carry the correct formula_version |

## Decision Tree

```
Algorithm design requested
  ↓
Does input have a minimum length requirement?
  YES → Add explicit guard; return INSUFFICIENT_DATA FeatureResult if not met
  NO  → Proceed
        ↓
        Does algorithm involve division?
          YES → Add zero-denominator guard; return INVALID/ZERO_VARIANCE FeatureResult
          NO  → Proceed
                ↓
                Does algorithm use zip()?
                  YES → Add strict=False or strict=True with comment explaining why
                  ↓
                All gates pass? → PROCEED
```

## Failure Modes

| Mode | Action |
|---|---|
| Algorithm produces NaN | Add guard; return INVALID FeatureResult with quality_status="INVALID" |
| Two algorithms produce conflicting scores for the same input | Log the conflict; use the formula_version tie-break rule (newer wins) |
| Property test finds a counterexample | Fix the invariant violation before committing |
