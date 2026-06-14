---
name: alert-failure-analysis
description: Analyse failed or low-quality alerts in the Outcome Ledger to identify systematic failure patterns.
version: 1.2.10
owner_agent: failure-root-cause-agent
purpose: Drive continuous improvement by surfacing recurring alert failure root causes.
allowed_inputs:
  - outcome ledger records
  - evidence archive records
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
failure_behavior: return ANALYSIS_UNAVAILABLE if outcome ledger empty or inaccessible
audit_fields:
  - evidence_id
  - failure_category
  - frequency
  - affected_evidence_ids
  - contributing_conditions
tests:
  - unit
  - integration
promotion_status: stable
---
# alert-failure-analysis

## Procedure
1. Query Outcome Ledger for alerts marked failed, missed, or low-quality in the review window
2. Group by failure_category: data_gap, false_signal, stale_data, macro_divergence, technical_failure
3. Compute frequency per category and time-cluster patterns
4. Cross-reference with evidence archive for contributing conditions at alert time
5. Return failure_report: top 3 categories, frequency, representative evidence_ids

## Decision Tree
- >3 same-category failures in 7 days → systematic pattern → trigger corrective-hypothesis-design
- Isolated single failure → log and continue
- All failures in one session → likely infrastructure failure → trigger SYSTEM_INCIDENT

## Quality Gates
- Only use Outcome Ledger records for failure identification (no agent assumption)
- Cannot label failure without evidence_id cross-reference

## Failure Modes
- Outcome Ledger empty (new system): no failures to analyse → return ANALYSIS_UNAVAILABLE
- LLM agent mis-labels outcome as failure: contradicted by Python score → use Python score
