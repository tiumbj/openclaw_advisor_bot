---
name: data-provenance-contract
description: Enforce that all evidence numerics carry complete provenance metadata (source, timestamp, realtime_class).
version: 1.2.14
owner_agent: market-data-integrity-agent
purpose: Prevent agent-fabricated numerics from entering the immutable evidence archive.
allowed_inputs:
  - evidence packet
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
failure_behavior: reject evidence packet with provenance violation details
audit_fields:
  - evidence_id
  - provenance
  - realtime_class
  - source_system
tests:
  - unit
  - integration
promotion_status: stable
---
# data-provenance-contract

## Procedure
1. For every numeric field in the evidence packet, check provenance dict contains: source, fetched_at_utc, realtime_class
2. Verify realtime_class is one of: REALTIME, DELAYED_15MIN, DAILY_MACRO, COMPUTED
3. For COMPUTED values verify formula_version field is present
4. Hash-verify evidence packet against archive record if archive_id present

## Decision Tree
- All fields have complete provenance → PASS
- Any numeric field missing provenance → REJECT (do not archive)
- COMPUTED field missing formula_version → REJECT

## Quality Gates
- realtime_class must match actual data source (MT5 tick → REALTIME, FRED daily → DAILY_MACRO)
- No agent may set its own provenance for externally sourced data

## Failure Modes
- Agent returns hardcoded value without fetching → provenance.source missing → REJECT
- Clock skew causes fetched_at_utc mismatch → flag for review but do not reject
