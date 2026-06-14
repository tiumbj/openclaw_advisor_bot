---
name: microstructure-trigger-audit
description: Audit price-action trigger conditions (order blocks, FVG, BOS) before alert publication.
version: 1.2.9
owner_agent: price-action-microstructure-agent
purpose: Validate that trigger criteria are met by Python-computed evidence, not agent assumption.
allowed_inputs:
  - evidence packet
  - trigger specification
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
failure_behavior: return TRIGGER_NOT_MET with unmet conditions list
audit_fields:
  - evidence_id
  - trigger_conditions
  - met_conditions
  - unmet_conditions
tests:
  - unit
  - integration
promotion_status: stable
---
# microstructure-trigger-audit

## Procedure
1. Extract trigger specification from evidence packet (e.g., price_in_OB=true, BOS_confirmed=true)
2. For each condition, verify corresponding Python-computed field exists in provenance
3. Cross-check condition value against numeric evidence (price vs OB range)
4. Return audit: met_conditions, unmet_conditions, overall_trigger_status

## Decision Tree
- All conditions met with Python evidence → TRIGGER_CONFIRMED
- Any condition missing Python evidence → TRIGGER_UNVERIFIED (cannot publish alert)
- Any condition explicitly false → TRIGGER_NOT_MET

## Quality Gates
- Agent cannot assert trigger without Python provenance
- OB range must come from Python OHLC calculation, not agent text

## Failure Modes
- Agent fabricates "price_in_OB=true" without numeric evidence → caught by provenance check
- OB calculated on wrong timeframe → timeframe mismatch in provenance
