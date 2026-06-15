---
name: corrective-hypothesis-design
description: Design structured hypotheses for corrective experiments based on root cause analysis.
version: 1.2.14
owner_agent: failure-root-cause-agent
purpose: Translate root cause findings into testable experiment specifications for the 16-state lifecycle.
allowed_inputs:
  - root cause tree
  - failure analysis report
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
failure_behavior: return HYPOTHESIS_BLOCKED if root cause confidence is LOW
audit_fields:
  - hypothesis_id
  - root_cause_ref
  - proposed_change
  - success_criteria
  - rollback_trigger
tests:
  - unit
  - integration
promotion_status: stable
---
# corrective-hypothesis-design

## Procedure
1. Receive root_cause_tree with identified root cause
2. Formulate hypothesis: "If we change [X], then [Y] failure will decrease by [Z%]"
3. Define success_criteria: measurable metric improvement within experiment window
4. Define rollback_trigger: specific regression threshold that auto-reverts change
5. Create experiment specification compatible with 16-state lifecycle (initial state: OBSERVATION)

## Decision Tree
- ROOT_CAUSE_IDENTIFIED (HIGH) → full hypothesis + success criteria
- ROOT_CAUSE_PROBABLE (MEDIUM) → hypothesis with wider confidence bounds
- ROOT_CAUSE_INSUFFICIENT_EVIDENCE → HYPOTHESIS_BLOCKED (require more failure data first)

## Quality Gates
- success_criteria must be Python-measurable (Outcome Ledger metrics)
- rollback_trigger must be defined before experiment can advance past OBSERVATION
- Self-approval forbidden: proposer_agent cannot approve own experiment

## Failure Modes
- Overly broad hypothesis (changes multiple systems at once) → split into focused hypotheses
- No rollback defined → experiment blocked at PEER_REVIEW gate
