---
name: evidence-audit
description: Evidence audit and provenance skill.
version: 1.2.14
owner_agent: super-advisor
purpose: Audit evidence integrity and provenance.
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
# evidence-audit

MAIN uses this skill to validate every agent result before accepting it.
Any result that fails evidence-audit is rejected and must be retried with valid evidence.

## Procedure

1. Receive agent result payload from MAIN.
2. Verify `evidence_reference` is present and non-empty.
3. Verify `provenance` is a non-empty dict.
4. Verify `provenance.source` is NOT "agent", "llm", or "specialist".
5. For each numeric field in `payload`, check `provenance.numeric_fields.<field>.source_system = python`.
6. Verify `status` is in the allowed set (COMPLETED|WATCH|LOW_SCORE|NOT_READY|CONFLICT).
7. Verify `task_id` and `agent_id` match the dispatched values.
8. Return structured `audit_passed` result with all `rejection_reasons`.

## Validation Rules

1. `evidence_reference` must be non-empty
2. `provenance` must be non-empty dict
3. `provenance.source` must NOT be "agent", "llm", or "specialist"
4. Numeric fields in `payload` require `provenance.numeric_fields.<field>.source_system = python`
5. `status` must be COMPLETED|WATCH|LOW_SCORE|NOT_READY|CONFLICT
6. `task_id` must match the dispatched task
7. `agent_id` must match the dispatched agent

## Decision Tree

- evidence_reference missing → REJECT, reason=missing_evidence_reference
- provenance missing → REJECT, reason=missing_provenance
- provenance.source is agent/llm/specialist → REJECT, reason=agent_numeric_source_forbidden
- fabricated_numeric_evidence=true → REJECT, reason=fabricated_evidence
- task_id mismatch → REJECT, reason=task_id_mismatch
- agent_id mismatch → REJECT, reason=agent_id_mismatch
- status not in allowed set → REJECT, reason=invalid_status
- All checks pass → audit_passed=true

## Rejection Triggers

- Missing evidence_reference: REJECT, reason=missing_evidence_reference
- Missing provenance: REJECT, reason=missing_provenance
- Numeric value from agent/LLM: REJECT, reason=agent_numeric_source_forbidden
- fabricated_numeric_evidence=true in payload: REJECT, reason=fabricated_evidence
- task_id mismatch: REJECT, reason=task_id_mismatch
- agent_id mismatch: REJECT, reason=agent_id_mismatch
- status not in allowed set: REJECT, reason=invalid_status

## Output Fields

- `evidence_reference`: echoed
- `audit_passed`: boolean
- `rejection_reasons`: list (empty when audit_passed=true)

## Failure Modes

- Empty result payload: REJECT, reason=empty_result
- Schema error: REJECT, reason=schema_error
