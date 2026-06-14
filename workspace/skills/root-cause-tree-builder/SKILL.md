---
name: root-cause-tree-builder
description: Build structured 5-Why root cause trees for evidence pipeline failures and alert misses.
version: 1.2.10
owner_agent: failure-root-cause-agent
purpose: Produce machine-readable root cause trees that drive corrective experiment hypotheses.
allowed_inputs:
  - failure analysis report
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
failure_behavior: return ROOT_CAUSE_INSUFFICIENT_EVIDENCE if <3 data points available
audit_fields:
  - failure_id
  - root_cause_tree
  - depth_reached
  - confidence
  - contributing_systems
tests:
  - unit
  - integration
promotion_status: stable
---
# root-cause-tree-builder

## Procedure
1. Receive failure_report from alert-failure-analysis
2. Build 5-Why tree: start from symptom, drill down through causal chain
3. At each level verify cause is supported by evidence archive data (not assumption)
4. Identify leaf-level root cause: the earliest unsupported system condition
5. Return root_cause_tree: structured dict with why_chain, contributing_systems, confidence

## Decision Tree
- Evidence supports full 5-why chain → ROOT_CAUSE_IDENTIFIED (HIGH confidence)
- Evidence supports 3-4 whys → ROOT_CAUSE_PROBABLE (MEDIUM confidence)
- Evidence supports <3 whys → ROOT_CAUSE_INSUFFICIENT_EVIDENCE

## Quality Gates
- Each why-level must cite evidence_id or system log reference
- Agent cannot fabricate why-levels without evidence reference

## Failure Modes
- Evidence archive inaccessible → cannot build tree → return ROOT_CAUSE_INSUFFICIENT_EVIDENCE
- Circular causation detected: flag as SYSTEM_DESIGN_ISSUE, escalate to MAIN
