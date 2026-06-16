---
name: event-driven-system-design
description: Design event schemas, integrity hashes, provenance chains, and dedup guards.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Guarantee every pipeline event is idempotent, tamper-evident, and carries complete provenance.
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

# Skill: event-driven-system-design

Owner: blueprint-coder
Phase: P2.4

## Purpose

Design and implement event schemas, provenance chains, integrity hashes, and
idempotency guarantees for the OpenClaw event pipeline.  Every event must carry
a deterministic `integrity_hash` (SHA-256), a `formula_version`, and a complete
`provenance` block.  Duplicate events identified by `event_id` must be rejected
by `MarketAlertDedupStore`.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "event_type": "string (MARKET_ALERT | CANDIDATE | HOLD | INVALIDATED | SYSTEM_*)",
  "schema_fields": {"field_name": "type_string"},
  "provenance_requirements": ["string"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Define the event envelope fields: `event_id`, `event_type`, `timestamp_utc`,
   `numeric_fields`, `provenance`, `integrity_hash`.
2. Implement `build_event_envelope` so that `integrity_hash` is the SHA-256 of the
   canonical JSON (sorted keys, no whitespace).
3. Implement `validate_event_envelope` to reject events where:
   - `integrity_hash` does not match recomputed hash
   - `provenance.source_system` is `"agent"` and `event_type` is numeric
   - `timestamp_utc` is more than `EVENT_FRESHNESS_SECONDS` in the past
   - `event_id` is already present in `MarketAlertDedupStore`
4. Add the event type to the publication policy's allowed types list if required.
5. Write tests: hash tampering rejected, duplicate event_id rejected, stale event rejected,
   agent-sourced numeric event rejected.
6. Confirm `EvidenceArchive` accepts the new event and `OutcomeLedger` records it.

## Gate Checklist

| Gate | Condition |
|---|---|
| integrity_hash | SHA-256 of canonical JSON (sorted keys, no whitespace) |
| dedup enforced | Duplicate event_id returns REJECT from MarketAlertDedupStore |
| stale check | Event older than EVENT_FRESHNESS_SECONDS returns HOLD |
| agent-numeric guard | source_system="agent" + numeric type → REJECT |
| provenance complete | All provenance fields present: source, formula_version, evidence_ids |

## Decision Tree

```
New event type required
  ↓
Is it market-facing (alert, candidate, hold, invalidated)?
  YES → Add to ALLOWED_EVENT_TYPES in publication policy; write 4 rejection tests
  NO  → Is it system-facing (SYSTEM_STARTED, DISK_LOW, etc.)?
          YES → Add to TELEGRAM_SYSTEM_EVENTS in constants.py; no numeric guard needed
          NO  → REJECT: event type must be classified before implementation
```

## Failure Modes

| Mode | Action |
|---|---|
| integrity_hash mismatch | Recompute from canonical JSON; check for encoding differences (UTF-8 BOM) |
| Dedup store grows unbounded | Confirm TTL is set; default 86400 seconds for market alerts |
| Provenance missing formula_version | Update the feature function to include FORMULA_VERSION |
