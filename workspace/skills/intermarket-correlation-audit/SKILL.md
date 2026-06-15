---
name: intermarket-correlation-audit
description: Audit directional alignment between XAUUSD, DXY proxy, US10Y, and FX basket before alert publication.
version: 1.2.11
owner_agent: intermarket-macro-agent
purpose: Flag macro divergence that weakens alert confidence before it reaches MAIN.
allowed_inputs:
  - intermarket evidence packet
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
failure_behavior: return CORRELATION_UNAVAILABLE if any macro feed missing
audit_fields:
  - evidence_id
  - xauusd_direction
  - usd_direction
  - yield_regime
  - alignment_score
  - divergence_flags
tests:
  - unit
  - integration
promotion_status: stable
---
# intermarket-correlation-audit

## Procedure
1. Receive consolidated intermarket evidence: XAUUSD bias, usd_direction, yield_regime
2. Check expected correlations:
   - USD_STRENGTHENING + YIELD_RISING → expect bearish XAUUSD pressure
   - USD_WEAKENING + YIELD_FALLING → expect bullish XAUUSD pressure
3. Compute alignment_score: 0 (full divergence) to 3 (full alignment)
4. Flag divergence pairs that contradict XAUUSD bias
5. Return audit: alignment_score, divergence_flags, macro_context_label

## Decision Tree
- alignment_score >= 2 → MACRO_ALIGNED (high confidence)
- alignment_score == 1 → MACRO_PARTIAL (reduced confidence, note in alert)
- alignment_score == 0 → MACRO_DIVERGENT (suppress alert or add strong caveat)

## Quality Gates
- All three inputs must have Python provenance (not inferred by agent)
- Divergence does not block alert but must be disclosed in evidence

## Failure Modes
- US10Y_CONTEXT_UNAVAILABLE and USD_CONTEXT_UNAVAILABLE simultaneously → CORRELATION_UNAVAILABLE
- Correlation inversion during defensive market regimes: valid but rare; do not suppress
