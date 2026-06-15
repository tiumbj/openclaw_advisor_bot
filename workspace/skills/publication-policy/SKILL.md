---
name: publication-policy
description: Gate MAIN approved Telegram publication payloads; reject forbidden event types and dedup violations.
version: 1.2.12
owner_agent: super-advisor
purpose: Final MAIN gate before sending APPROVED_PUBLICATION to telegram-publisher.
allowed_inputs:
  - publication payload
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
failure_behavior: return structured rejection; never silently drop
audit_fields:
  - event_id
  - event_type
  - publication_decision
  - reason
tests:
  - unit
  - integration
promotion_status: stable
---
# publication-policy

MAIN runs this skill as the final gate before sending APPROVED_PUBLICATION to telegram-publisher.
A payload that passes publication-policy becomes an `ApprovedPublicationPayload` and is routed to telegram-publisher only.

## Procedure

1. Receive event envelope and audit_result from MAIN.
2. Verify event_type is in ALLOWED_MARKET_PUBLISH (not FORBIDDEN).
3. For CONFIRMED events, verify audit_result.audit_passed=true.
4. Verify event expires_at_utc is in the future.
5. Verify dedup_key is not in MarketAlertDedupStore within cooldown_seconds.
6. Verify evidence_reference is present and non-empty.
7. Verify integrity_hash matches canonical JSON of event payload.
8. If all gates pass, return publication_approved=true and ApprovedPublicationPayload.
9. If any gate fails, return publication_approved=false with reason; fail closed.

## Allowed Event Types (Telegram Market Bot only)

| event_type | Publish? | Notes |
|---|---|---|
| SUPER_POTENTIAL_CONFIRMED | YES | Score >= 80.0, all gates passed |
| SUPER_POTENTIAL_INVALIDATED | YES | Publish once; includes reason |
| DATA_QUALITY_WARNING | YES | Only when data_quality=STALE/INSUFFICIENT_DATA |
| SYSTEM_INCIDENT | YES | MAIN-escalated only |

## Forbidden Event Types (never publish to Telegram)

- SUPER_POTENTIAL_CANDIDATE_INTERNAL (must never leave MAIN)
- SYSTEM_HEALTH (internal watchdog events only)
- Any event_type not in the allowed list above

## Gate Checklist (all must pass before APPROVED_PUBLICATION is issued)

1. event_type in ALLOWED_MARKET_PUBLISH
2. super-potential-audit returned audit_passed=true (for CONFIRMED events)
3. event not expired (expires_at_utc > now_utc)
4. dedup_key not in MarketAlertDedupStore (within cooldown_seconds=3600)
5. evidence_reference present and non-empty
6. integrity_hash present and matches event payload canonical JSON

## Required Input Fields

- `event`: full event envelope dict
- `audit_result`: super-potential-audit output (required for CONFIRMED events)
- `dedup_store_state`: current dedup key set

## Output Fields

- `publication_approved`: boolean
- `reason`: string (populated when publication_approved=false)
- `approved_payload`: ApprovedPublicationPayload (populated when publication_approved=true)
  - `event_id`, `event_type`, `dedup_key`, `approved_at_utc`, `thai_template_key`

## Decision Tree

- event_type=CANDIDATE_INTERNAL: REJECT, reason=forbidden_event_type_candidate_internal
- event_type not in allowlist: REJECT, reason=forbidden_event_type
- audit_result.audit_passed=false (for CONFIRMED): REJECT, reason=audit_failed
- event expired: REJECT, reason=event_expired
- dedup_key in dedup window: REJECT, reason=duplicate_event
- integrity_hash mismatch: REJECT, reason=integrity_violation
- All gates pass: publication_approved=true

## Failure Modes

- Missing audit_result for CONFIRMED events: REJECT, reason=missing_audit_result
- Malformed event envelope: REJECT, reason=schema_error
- dedup_store_state unavailable: REJECT, reason=dedup_store_unavailable (fail closed)
