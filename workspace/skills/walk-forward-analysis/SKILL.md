---
name: walk-forward-analysis
description: Validate strategy performance using time-ordered out-of-sample walk-forward windows.
version: 1.2.15
owner_agent: statistical-backtest-agent
purpose: Detect in-sample overfitting by testing performance on unseen future windows.
allowed_inputs:
  - outcome ledger records
  - strategy parameters
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
failure_behavior: return WFA_INSUFFICIENT_DATA if fewer than 2 windows possible
audit_fields:
  - evidence_id
  - window_count
  - in_sample_performance
  - out_of_sample_performance
  - efficiency_ratio
tests:
  - unit
  - integration
promotion_status: stable
---
# walk-forward-analysis

## Procedure
1. Split Outcome Ledger records into anchored train/test windows (default: 70/30 split)
2. For each window: compute win_rate, avg_rr, sharpe from in-sample records
3. Apply same parameters to out-of-sample window; compute same metrics
4. efficiency_ratio = out_of_sample_sharpe / in_sample_sharpe
5. Return per-window and aggregate metrics

## Decision Tree
- efficiency_ratio >= 0.6 → ROBUST (strategy generalises)
- efficiency_ratio 0.4-0.6 → MARGINAL (monitor closely)
- efficiency_ratio < 0.4 → OVERFIT (block promotion, trigger overfitting-detection)
- Fewer than 2 windows possible → WFA_INSUFFICIENT_DATA

## Quality Gates
- All outcome data from immutable Outcome Ledger (hash-verified)
- Parameters must be fixed before WFA begins — no in-loop tuning

## Failure Modes
- Train window too small: artificially high in-sample → MARGINAL flag even if ratio OK
- Non-stationary market: regime shift between windows → flag regime change in report
