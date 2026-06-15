---
name: realtime-evidence-review
description: Realtime evidence review skill.
version: 1.2.12
owner_agent: xau-strategy-auditor
purpose: Review live evidence snapshots without mutation.
allowed_inputs:
  - market evidence
required_input_schema: object
output_schema: object
allowed_tools:
  - read
  - session_status
denied_tools:
  - group:runtime
  - group:web
  - group:ui
  - group:automation
  - group:messaging
  - group:plugins
  - group:memory
  - group:sessions
  - write
  - edit
  - apply_patch
  - exec
  - process
  - code_execution
  - browser
  - canvas
  - gateway
  - message
  - subagents
safety_constraints:
  - advisor-only
  - no secret access
  - no execution
failure_behavior: return structured audit failure
audit_fields:
  - evidence_id
  - correlation_id
  - provenance
tests:
  - unit
  - integration
promotion_status: stable
---
# realtime-evidence-review

Reviews live Python evidence snapshots for completeness, freshness, and provenance integrity.
Read-only; must not mutate evidence.

## Procedure

1. Receive evidence snapshot from xau-strategy-auditor.
2. Verify all required input fields are present; return REJECT if any missing.
3. Recompute SHA-256 of canonical JSON of evidence payload; compare to integrity_hash.
4. Verify provenance.source starts with "python_"; reject non-python sources.
5. Verify provenance.formula_version=features-p2.4-v1.
6. Check fetched_at_utc age; if > 3 minutes, set freshness_status=stale.
7. Verify data_quality is not STALE; if stale, return HOLD.
8. If all checks pass, return snapshot_valid=true, recommendation=PROCEED.

## Required Input Fields

- `evidence_id`: non-empty string
- `symbol`: XAUUSD
- `timeframe`: M1|M5|M15|H1|H4|D1
- `fetched_at_utc`: ISO8601Z
- `data_quality`: VALID|DEGRADED|STALE|INSUFFICIENT_DATA
- `features`: dict of Python-computed values
- `provenance.source`: must be a python_* source
- `provenance.formula_version`: features-p2.4-v1
- `integrity_hash`: SHA-256 hex digest

## Output Fields

- `evidence_id`, `snapshot_valid` (bool), `freshness_status` (fresh|stale|unknown)
- `missing_fields`, `provenance_issues` (lists)
- `integrity_verified` (bool), `recommendation` (PROCEED|HOLD|REJECT)

## Decision Tree

1. integrity_hash mismatch: snapshot_valid=false, recommendation=REJECT
2. provenance.source not python_*: REJECT, reason=non_python_source
3. data_quality=STALE: recommendation=HOLD, freshness_status=stale
4. Any required field missing: REJECT
5. All pass: PROCEED

## Failure Modes

- Empty evidence: REJECTED, reason=empty_evidence
- integrity_hash absent: REJECTED, reason=missing_integrity_hash
- fetched_at_utc older than 3 minutes: freshness_status=stale
- Timeout: return REJECTED, reason=timeout
