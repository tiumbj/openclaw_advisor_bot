---
name: performance-and-reliability-engineering
description: Profile, fix bottlenecks, add retry with backoff, and cap unbounded data structures.
version: 1.2.13
owner_agent: blueprint-coder
purpose: Ensure the pipeline meets latency targets and handles transient failures gracefully.
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

# Skill: performance-and-reliability-engineering

Owner: blueprint-coder
Phase: P2.4

## Purpose

Identify and fix performance bottlenecks and reliability gaps in the OpenClaw
pipeline: slow feature computation, unbounded data structures, missing retry
logic, and unhandled network failures.  All changes must be measured (before/after
timing) and must not reduce test coverage.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "bottleneck_description": "string",
  "profiling_evidence": "string (e.g. output of cProfile or pytest-benchmark)",
  "reliability_gap": "string",
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Reproduce the performance issue with a benchmark: `python -m pytest --benchmark-only -k <target>`.
2. Run cProfile on the hot path: confirm the bottleneck is in `engine/src/`, not in
   a library function.
3. Apply the optimisation: prefer algorithmic improvement over micro-optimisation.
   - Replace O(n^2) with O(n log n) where n > 200 data points
   - Cache expensive pure computations with `functools.lru_cache` where inputs are hashable
   - Avoid re-reading the same file in a hot loop; read once, pass as argument
4. For reliability: add retry with exponential backoff for all network calls
   (`FRED_UNAVAILABLE`, `MT5_DISCONNECTED` scenarios); confirm the retry count and
   backoff are configurable via settings.
5. Add `MarketAlertDedupStore` TTL eviction if the store grows > 10,000 entries per day.
6. Measure after: confirm the benchmark shows >= 20% improvement for the hot path.
7. Confirm all existing tests still pass (performance optimisation must not change behaviour).

## Gate Checklist

| Gate | Condition |
|---|---|
| Profiling evidence | cProfile or benchmark output included in WorkOrderResult |
| Algorithmic improvement | No micro-optimisation without profiling evidence |
| Retry configurable | Retry count and backoff read from settings, not hardcoded |
| Dedup TTL | MarketAlertDedupStore eviction confirmed for high-volume scenarios |
| Behaviour unchanged | All pre-existing tests pass after the change |

## Decision Tree

```
Performance report received
  ↓
Is the bottleneck in a Python pure function?
  YES → Use lru_cache if inputs are hashable; otherwise optimise the algorithm
  NO  → Is it an I/O bottleneck (MT5, FRED, disk)?
          YES → Add async where supported; add retry with backoff
          NO  → Is it a data structure growing unboundedly?
                  YES → Add TTL eviction or size cap
```

## Failure Modes

| Mode | Action |
|---|---|
| lru_cache on unhashable input | Use a frozenset key or a custom cache keyed on a hashable representation |
| Retry hides a real error | Confirm the retry is only for transient failures (network, timeout) not for validation errors |
| Optimisation breaks a test | Revert; the test captures the expected behaviour; find an optimisation that preserves it |
