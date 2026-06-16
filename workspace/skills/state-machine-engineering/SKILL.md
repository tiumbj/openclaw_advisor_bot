---
name: state-machine-engineering
description: Design typed finite-state machines with transition guards and invariant tests.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Enforce legal state transitions for signal lifecycle, task state, and CodeWorkOrder lifecycle.
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

# Skill: state-machine-engineering

Owner: blueprint-coder
Phase: P2.4

## Purpose

Design finite-state machines (FSMs) for signal lifecycle, agent task state, and
CodeWorkOrder lifecycle.  Every FSM must have explicit states, typed transitions,
guard conditions, and invariants that are enforced by property-based tests.
State machines must not permit illegal transitions silently — they must raise a
typed exception or return an error FeatureResult.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "fsm_name": "string",
  "states": ["string"],
  "initial_state": "string",
  "terminal_states": ["string"],
  "transitions": [{"from": "string", "event": "string", "to": "string", "guard": "string"}],
  "invariants": ["string"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Define the state enum using `enum.Enum`; terminal states should be clearly marked
   (e.g., `CONFIRMED`, `REJECTED`, `EXPIRED`).
2. Implement the transition table as a `dict[tuple[State, Event], State]` for O(1) lookup.
3. Add guard functions: a transition that fails its guard raises `InvalidTransitionError`
   with `from_state`, `event`, and `reason` fields.
4. Define invariants as functions that return `bool`; call them after every transition.
5. Write unit tests: (a) valid transitions succeed, (b) invalid transitions raise, (c) all
   invariants hold after 100 random valid transition sequences (Hypothesis).
6. Confirm terminal states have no outgoing transitions.
7. Document the FSM as an ASCII state diagram in the module docstring.

## Gate Checklist

| Gate | Condition |
|---|---|
| State enum | All states declared in `enum.Enum` |
| Transition table | Every valid (from, event) pair has exactly one target state |
| Invalid transition | Illegal (from, event) pair raises `InvalidTransitionError` |
| Terminal states | No outgoing transitions from terminal states |
| Invariant tests | Hypothesis test confirms invariants hold over 100 random sequences |

## Decision Tree

```
New FSM required
  ↓
Is there an existing FSM for this lifecycle?
  YES → Extend with new states/transitions; confirm existing tests still pass
  NO  → Implement fresh; start with initial and terminal states, then transitions
        ↓
        Does any transition require external I/O?
          YES → Extract I/O to a callback; keep FSM pure
          NO  → Proceed; run all gates
```

## Failure Modes

| Mode | Action |
|---|---|
| Unreachable state detected | Remove or document; never leave dead states in the enum |
| Invariant fails after valid transition | Fix the invariant (not the test); the state machine is wrong |
| Guard blocks all paths to terminal state | Audit guard logic; ensure at least one path to CONFIRMED and REJECTED |
