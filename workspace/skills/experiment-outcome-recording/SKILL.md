---
name: experiment-outcome-recording
description: Record experiment outcomes into the Outcome Ledger with hash-chained immutable entries.
version: 1.2.14
owner_agent: knowledge-skill-manager
purpose: Ensure every experiment transition produces a verifiable, hash-linked outcome record.
allowed_inputs:
  - experiment transition record
  - outcome metrics
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
failure_behavior: return OUTCOME_RECORDING_FAILED if hash chain broken
audit_fields:
  - experiment_id
  - outcome_id
  - terminal_state
  - outcome_metrics
  - ledger_hash
tests:
  - unit
  - integration
promotion_status: stable
---
# experiment-outcome-recording

## Procedure
1. Receive experiment terminal state (RELEASED or ROLLED_BACK) and outcome_metrics
2. Verify experiment_id exists in ExperimentStore with matching state
3. Compute outcome record: experiment_id, terminal_state, outcome_metrics, reviewed_by, transitioned_at
4. Write to OutcomeLedger (hash-chained): compute hash = SHA256(prev_hash + outcome_record)
5. Return outcome_id and ledger_hash; trigger research-knowledge-lifecycle

## Decision Tree
- Experiment in RELEASED or ROLLED_BACK state → record outcome
- Experiment in non-terminal state → OUTCOME_RECORDING_FAILED (premature)
- Hash chain broken (prev_hash mismatch) → OUTCOME_RECORDING_FAILED (integrity error)

## Quality Gates
- Only terminal states produce outcome records (REJECTED also valid terminal state)
- outcome_metrics must include at least: win_rate_delta, alert_quality_delta (or reason for absence)
- Self-approval check enforced: reviewer != proposer_agent

## Failure Modes
- OutcomeLedger file corrupted → hash verification fails → halt recording, escalate to MAIN
- Experiment with no measurable outcome (config change only) → record with metrics=null and reason
