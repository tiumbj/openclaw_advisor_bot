---
name: overfitting-detection
description: Detect parameter overfitting in strategy backtests using robustness metrics.
version: 1.2.14
owner_agent: statistical-backtest-agent
purpose: Block strategies that rely on data-mined parameters from reaching the experiment promotion gate.
allowed_inputs:
  - backtest results
  - parameter sensitivity matrix
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
failure_behavior: return OVERFITTING_DETECTED with sensitivity report
audit_fields:
  - evidence_id
  - parameter_count
  - sensitivity_score
  - robustness_flag
  - overfitting_indicators
tests:
  - unit
  - integration
promotion_status: stable
---
# overfitting-detection

## Procedure
1. Receive parameter sensitivity matrix: performance vs ±10% parameter perturbation
2. Compute sensitivity_score: average performance degradation on perturbation
3. Count number of free parameters relative to sample size (complexity ratio)
4. Check for equity curve smoothness: high smoothness + low OOS performance → overfitting signal
5. Return robustness assessment: ROBUST, MARGINAL, or OVERFIT

## Decision Tree
- sensitivity_score < 15% degradation AND complexity_ratio < 0.1 → ROBUST
- sensitivity_score 15-30% degradation → MARGINAL (note in experiment record)
- sensitivity_score > 30% degradation OR complexity_ratio > 0.2 → OVERFIT → block

## Quality Gates
- Sensitivity matrix must include at least ±10% perturbation for each free parameter
- Cannot suppress overfitting flag without human override in experiment record

## Failure Modes
- Only 1-2 free parameters: sensitivity test trivially passes → require additional sample check
- Single-regime backtest: OOS looks good only because regime repeated → flag regime concentration
