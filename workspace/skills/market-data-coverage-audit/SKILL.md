---
name: market-data-coverage-audit
description: Verify all 8 required MT5 symbols are present and non-null in every evidence packet.
version: 1.2.8
owner_agent: market-data-integrity-agent
purpose: Detect missing or stale symbol data before it enters the evidence pipeline.
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
  - read-only market data
failure_behavior: return structured coverage failure with missing symbol list
audit_fields:
  - symbols_present
  - symbols_missing
  - evidence_id
  - provenance
tests:
  - unit
  - integration
promotion_status: stable
---
# market-data-coverage-audit

## Procedure
1. Extract symbol list from incoming evidence packet provenance
2. Compare against required 8 symbols: XAUUSD, EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD
3. For each present symbol verify value is non-null and bid/ask spread is non-zero
4. Return coverage report: symbols_present, symbols_missing, coverage_pct

## Decision Tree
- ALL 8 present and non-null → status=PASS
- ≥6 present → status=DEGRADED (can proceed with warning)
- <6 present → status=FAIL (block downstream evidence scoring)

## Quality Gates
- Evidence packet must declare symbol provenance explicitly
- Stale data (age > MT5_STALE_THRESHOLD_SECONDS) counts as missing

## Failure Modes
- MT5 connection dropped mid-session: symbol data returns null → DEGRADED
- Wrong symbol alias configured in env: value present but wrong instrument → log mismatch
