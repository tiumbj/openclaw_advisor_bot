---
name: stale-data-detection
description: Detect stale MT5 ticks and FRED observations before they corrupt evidence scoring.
version: 1.2.13
owner_agent: market-data-integrity-agent
purpose: Enforce freshness thresholds per data class (REALTIME vs DAILY_MACRO).
allowed_inputs:
  - evidence packet
  - market data snapshot
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
failure_behavior: tag evidence as STALE with age_seconds and threshold_seconds
audit_fields:
  - evidence_id
  - data_age_seconds
  - staleness_threshold_seconds
  - stale_symbols
tests:
  - unit
  - integration
promotion_status: stable
---
# stale-data-detection

## Procedure
1. For REALTIME data: compute age_seconds = now_utc - fetched_at_utc
2. Compare against threshold: XAUUSD ≤ 30s, other FX pairs ≤ 60s
3. For DAILY_MACRO (FRED): compare observation_date to today; stale if > 5 business days old
4. Mark stale fields in provenance with staleness_flag=true and age_seconds

## Decision Tree
- All fields fresh → PASS
- Any REALTIME field stale → DEGRADED (score with warning, do not block)
- FRED stale > 5 days → SOURCE_UNAVAILABLE (use last_known or skip macro context)

## Quality Gates
- Staleness thresholds are fixed constants; agents cannot override them
- Age is always computed from UTC timestamps, not local time

## Failure Modes
- MT5 terminal frozen: all ticks stale simultaneously → DEGRADED + SYSTEM_INCIDENT event
- FRED weekend gap: DGS10 not updated Sat/Sun → expected, do not fire alert
