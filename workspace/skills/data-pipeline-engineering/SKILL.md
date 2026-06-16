---
name: data-pipeline-engineering
description: Implement MT5/FRED ingestion with quality scoring, timezone normalisation, and provenance.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Ensure all market data carries realtime_class, quality_status, and source_system before scoring.
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

# Skill: data-pipeline-engineering

Owner: blueprint-coder
Phase: P2.4

## Purpose

Implement and maintain the MT5/FRED data ingestion pipeline: bar retrieval,
tick collection, missing-bar detection, timezone normalisation, and quality
classification.  All pipeline outputs must carry `realtime_class`, `source_system`,
`fetched_at_utc`, and `quality_status`.  The Python pipeline is the sole authority
for numeric evidence — never accept numeric data from agent-sourced events.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "pipeline_stage": "string (collection | provenance | scoring | publication)",
  "symbols": ["string"],
  "timeframes": ["string (M1 | M5 | M15 | H1 | H4 | D1)"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Confirm the provider adapter returns data with `symbol`, `timeframe`, `bars`,
   `fetched_at_utc`, `realtime_class`, and `source_system` fields.
2. Apply missing-bar detection: count expected bars in the window; flag STALE if
   actual < 80% of expected.
3. Apply timezone normalisation: all timestamps must be UTC; raise `DataProvenanceError`
   if a naive datetime is detected.
4. Compute `data_quality` score: each of freshness, completeness, bar count, and tick
   spread contributes 0.25; total must exceed 0.7 for PROCEED.
5. Assign `realtime_class`:
   - MT5 XAUUSD: `REALTIME`
   - MT5 delayed feeds: `DELAYED_15MIN`
   - FRED macro series: `DAILY_MACRO`
   - Computed features: `COMPUTED`
6. Reject any data where `source_system == "agent"` and `realtime_class` is numeric.
7. Write tests: missing bars classified as STALE, naive datetime raises, data_quality
   below 0.7 returns NO_SETUP, agent-sourced numeric data rejected.

## Gate Checklist

| Gate | Condition |
|---|---|
| Provenance complete | Every bar/tick has fetched_at_utc, realtime_class, source_system |
| Missing-bar detection | Gaps > 20% of expected bars → STALE classification |
| UTC-only | No naive datetimes allowed anywhere in the pipeline |
| Agent-numeric guard | source_system="agent" for numeric data → REJECT |
| data_quality threshold | Below 0.7 → NO_SETUP; never proceed with partial data |

## Decision Tree

```
New data source or field required
  ↓
Is source_system "python"?
  YES → Proceed; apply all 5 provenance fields
  NO  → Is source_system "agent"?
          YES → REJECT if data is numeric; HOLD if data is advisory text only
          NO  → REJECT: unknown source_system must be classified first
```

## Failure Modes

| Mode | Action |
|---|---|
| MT5 returns 0 bars | Mark data_quality=0.0, realtime_class=STALE; return NO_SETUP |
| FRED API unavailable | Use last known value with realtime_class=STALE; flag in provenance |
| Naive datetime in input | Raise DataProvenanceError; do not silently convert |
| data_quality exactly 0.7 | HOLD: borderline quality requires human review |
