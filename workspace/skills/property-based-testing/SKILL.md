---
name: property-based-testing
description: Write Hypothesis property-based tests for mathematical invariants of pure functions.
version: 1.2.14
owner_agent: blueprint-coder
purpose: Assert invariants hold over the full input space, not just hand-picked examples.
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

# Skill: property-based-testing

Owner: blueprint-coder
Phase: P2.4

## Purpose

Write property-based tests using the Hypothesis library to assert mathematical
invariants of pure functions: commutativity, idempotency, monotonicity, range
bounds, and round-trip encoding/decoding.  Property-based tests complement
example-based tests — they do not replace them.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "target_function": "string (module:function name)",
  "properties": [{"name": "string", "description": "string"}],
  "value_ranges": {"param_name": {"min": "number", "max": "number"}},
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Import `hypothesis` and `hypothesis.strategies` at the top of the test module.
2. For each property in `properties`: write a `@given`-decorated test that asserts
   the property holds for all valid inputs in `value_ranges`.
3. Use `@settings(max_examples=200, deadline=None)` for computation-heavy functions.
4. For market data: use value ranges appropriate to XAUUSD reality:
   - closes: `st.floats(min_value=1000.0, max_value=3500.0, allow_nan=False, allow_infinity=False)`
   - RSI: result must be in `[0.0, 100.0]`
   - ATR: result must be non-negative
5. For provenance/hash functions: assert round-trip property (encode then decode
   recovers the original).
6. For scoring functions: assert monotonicity (higher quality input → higher or equal score).
7. Confirm all property tests pass with `python -m pytest -k property` and that
   Hypothesis does not find a counterexample in 200 examples.

## Gate Checklist

| Gate | Condition |
|---|---|
| @given decorator | All property tests use @given with typed strategies |
| Realistic value ranges | Strategies use market-realistic bounds |
| 200 examples | @settings(max_examples=200) for computation-heavy tests |
| No counterexample | Hypothesis exhausts max_examples without finding a failure |
| Complements unit tests | Property tests are in addition to, not instead of, unit tests |

## Decision Tree

```
Property test required
  ↓
Is the property mathematical (invariant, monotonicity, round-trip)?
  YES → Use @given with appropriate strategies
  NO  → Is the property a boundary condition?
          YES → Express as a parametrized unit test (not property-based)
          NO  → Is the property a stateful sequence?
                  YES → Use hypothesis.stateful.RuleBasedStateMachine
```

## Failure Modes

| Mode | Action |
|---|---|
| Hypothesis finds a counterexample | The invariant is wrong or the function has a bug; fix the function |
| Strategy generates invalid market data (NaN, inf) | Add `allow_nan=False, allow_infinity=False` to st.floats |
| Test is too slow (deadline exceeded) | Add `@settings(deadline=None)` and reduce max_examples to 100 |
| Property test is vacuously true | Strengthen with an `assume()` filter or a concrete countercheck |
