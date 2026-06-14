---
name: sample-adequacy-review
description: Verify statistical sample size before any backtest or performance metric is computed.
version: 1.2.10
owner_agent: statistical-backtest-agent
purpose: Block under-powered analysis that produces false confidence in strategy performance.
allowed_inputs:
  - backtest specification
  - historical evidence records
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
failure_behavior: return SAMPLE_INADEQUATE with minimum_required and actual_count
audit_fields:
  - evidence_id
  - sample_count
  - minimum_required
  - date_range
  - market_regimes_covered
tests:
  - unit
  - integration
promotion_status: stable
---
# sample-adequacy-review

## Procedure
1. Count evidence records in backtest scope: sample_count
2. Compare to minimum_required = max(30, win_rate_target_precision_factor)
3. Verify date_range spans at least 3 distinct market regimes (trending, ranging, volatile)
4. Check no single regime dominates > 70% of sample
5. Return adequacy report: ADEQUATE, MARGINAL (20-29 samples), or INADEQUATE (<20)

## Decision Tree
- sample_count >= 30 and regimes >= 3 → ADEQUATE
- sample_count 20-29 → MARGINAL (proceed with reduced confidence flag)
- sample_count < 20 or regimes < 2 → INADEQUATE (block promotion)

## Quality Gates
- Sample count from Outcome Ledger records only (immutable archive)
- Cannot backfill samples with synthetic or agent-generated data

## Failure Modes
- Short strategy history (<3 months): likely MARGINAL — report as MARGINAL not INADEQUATE
- Cherry-picked date range (only one regime): flag regime concentration
