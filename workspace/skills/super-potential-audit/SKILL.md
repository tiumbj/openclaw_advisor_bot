---
name: super-potential-audit
description: Super potential audit skill.
version: 1.2.13
owner_agent: xau-strategy-auditor
purpose: Audit super potential evidence for XAUUSD.
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
# super-potential-audit

Second-level audit for SUPER_POTENTIAL_CONFIRMED events.
Runs after xauusd-market-analysis; validates that all gates are met before MAIN approves publication.

## Procedure

1. Receive signal_event envelope, threshold_version, and evidence_ids from MAIN.
2. Verify threshold_version=signal-thresholds-p2.4-v1; reject if mismatched.
3. Verify signal_event structure is a valid event envelope (schema_version, integrity_hash, etc.).
4. Verify data_quality=VALID gate.
5. Verify score >= confirmed_threshold (80.0) gate.
6. Verify headroom_atr >= minimum_headroom_atr (1.0) gate.
7. Verify timeframe_agreement >= minimum_timeframe_alignment (2) gate.
8. Verify evidence_ids count >= minimum_evidence_count (3) gate.
9. Verify provenance.source_system=python gate.
10. Verify event is not expired (expires_at_utc in future) gate.
11. Verify dedup_key not seen within dedup window.
12. Return audit_passed=true and publication_recommended=true only when ALL gates pass and event_type=CONFIRMED.

## Gate Checklist (all must pass for CONFIRMED)

- [ ] data_quality = VALID
- [ ] score >= threshold_version.confirmed_threshold (default 80.0)
- [ ] headroom_atr >= minimum_headroom_atr (default 1.0)
- [ ] timeframe_agreement >= minimum_timeframe_alignment (default 2)
- [ ] evidence_ids count >= minimum_evidence_count (default 3)
- [ ] provenance.source_system = python
- [ ] event not expired (expires_at_utc in future)
- [ ] dedup_key not seen in dedup window

## Required Input Fields

- `signal_event`: the SUPER_POTENTIAL_CONFIRMED event envelope (full dict)
- `threshold_version`: string (must be signal-thresholds-p2.4-v1)
- `evidence_ids`: list (must match signal_event.payload.evidence_ids)

## Output Fields

- `audit_passed`: boolean
- `gates_passed`: list of passed gate names
- `gates_failed`: list of failed gate names
- `publication_recommended`: boolean (true only when audit_passed=true and event_type=CONFIRMED)
- `reason`: string

## Decision Tree

- Any gate fails: audit_passed=false, publication_recommended=false
- event_type=CANDIDATE_INTERNAL: publication_recommended=false (always hold internal)
- All gates pass and event_type=CONFIRMED: audit_passed=true, publication_recommended=true

## Failure Modes

- Signal event missing or malformed: REJECT, reason=invalid_signal_event
- threshold_version mismatch: REJECT, reason=threshold_version_mismatch
- Timeout: REJECT, reason=timeout
