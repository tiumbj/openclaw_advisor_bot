---
name: candlestick-microstructure
description: Candlestick microstructure review skill.
version: 1.2.14
owner_agent: xau-strategy-auditor
purpose: Review candle microstructure evidence.
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
# candlestick-microstructure

This skill audits candles without modifying numbers.

## Procedure
1. Validate input against required_input_schema; reject malformed payloads without partial processing.
2. Execute the primary analysis sequence for this skill using Python deterministic rules only.
3. Record all computed values with evidence IDs and provenance metadata before returning.
4. Return structured output to the requesting agent; do not fabricate missing values.

## Decision Tree
- Input VALID and all required fields present → proceed with full analysis.
- Input STALE → annotate stale=True in output; proceed with caveat.
- Input SOURCE_UNAVAILABLE → return INSUFFICIENT_DATA; do not substitute fabricated values.
- Required evidence missing or schema mismatch → return REJECTED with ailure_reason.

## Failure Mode
- **Source unavailable**: Return SOURCE_UNAVAILABLE status; never fill with fabricated data.
- **Schema violation**: Reject payload; log structured error; do not partially process.
- **Timeout / retry exhaustion**: Return TIMEOUT status; let job_queue requeue.
- **Agent unreachable**: Record incident via watchdog callback; escalate after threshold.