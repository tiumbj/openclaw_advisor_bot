---
name: us10y-context-review
description: Interpret US 10-Year Treasury yield (DGS10 from FRED) for gold macro context.
version: 1.2.8
owner_agent: intermarket-macro-agent
purpose: Classify yield regime (rising/falling/flat) for real-rate pressure on XAUUSD.
allowed_inputs:
  - FRED evidence packet (DGS10)
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
failure_behavior: return US10Y_CONTEXT_UNAVAILABLE if FRED data absent or stale
audit_fields:
  - evidence_id
  - dgs10_value
  - dgs10_observation_date
  - yield_regime
  - age_days
tests:
  - unit
  - integration
promotion_status: stable
---
# us10y-context-review

## Procedure
1. Receive FRED DGS10 evidence packet (FredSeriesResult from fred_adapter)
2. Verify status != SOURCE_UNAVAILABLE; if so → US10Y_CONTEXT_UNAVAILABLE
3. Compute age_days = today - observation_date
4. If age_days > 5 → mark as STALE (use last_known but flag)
5. Compare current value to 20-day rolling average (if history available):
   - value > avg + 0.10 → YIELD_RISING (bearish gold)
   - value < avg - 0.10 → YIELD_FALLING (bullish gold)
   - else → YIELD_FLAT
6. Return yield_regime with supporting numerics

## Decision Tree
- FRED status SOURCE_UNAVAILABLE → US10Y_CONTEXT_UNAVAILABLE
- STALE but value present → use with staleness warning
- value valid and fresh → classify regime

## Quality Gates
- All yield values come from FRED adapter Python module; agent does not estimate yields
- is_proxy=False for DGS10 (direct US Treasury data)

## Failure Modes
- FRED API key expired → SOURCE_UNAVAILABLE → use free-tier fallback if enabled
- Federal holiday: DGS10 not published → expected gap, use last_known
