---
name: m1-m5-pattern-review
description: Review M1 and M5 XAUUSD patterns for entry timing context within HTF structure.
version: 1.2.11
owner_agent: price-action-microstructure-agent
purpose: Synthesize M1/M5 signals for entry confirmation in the alert evidence packet.
allowed_inputs:
  - OHLC evidence packet (M1 and M5)
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
  - read-only market data
failure_behavior: return INSUFFICIENT_DATA if M1/M5 unavailable
audit_fields:
  - evidence_id
  - m1_pattern
  - m5_pattern
  - htf_alignment
  - entry_timing_score
tests:
  - unit
  - integration
promotion_status: stable
---
# m1-m5-pattern-review

## Procedure
1. Receive last 20 M1 candles and last 20 M5 candles from evidence packet
2. Classify M5 structure: impulse, retracement, consolidation, or UNCLASSIFIED
3. Classify M1 pattern within M5 context: entry_confirmed, counter-structure, or neutral
4. Compute HTF alignment: check M5 direction matches H1/H4 bias from intermarket context
5. Return entry_timing_score: HIGH (aligned), MEDIUM (partial), LOW (divergent), or SKIP

## Decision Tree
- M5 impulse + M1 confirmation + HTF aligned → entry_timing_score=HIGH
- M5 impulse but M1 counter-structure → entry_timing_score=LOW
- M5 consolidation → WAIT (no entry timing signal)
- <10 candles on either TF → INSUFFICIENT_DATA

## Quality Gates
- All OHLC data must be from Python MT5 adapter, not reconstructed by agent
- HTF bias must be provided by intermarket-macro-agent evidence, not assumed

## Failure Modes
- MT5 history gap in M1 data → INSUFFICIENT_DATA, do not interpolate
- Timezone mismatch between TFs → flag and use UTC-normalized timestamps only
