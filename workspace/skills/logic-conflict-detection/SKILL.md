---
name: logic-conflict-detection
description: Logic conflict detection skill.
version: 1.2.7
owner_agent: system-coder-auditor
purpose: Detect logic conflicts and policy clashes.
allowed_inputs:
  - code bundle
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
failure_behavior: return structured audit failure
audit_fields:
  - evidence_id
  - correlation_id
  - provenance
tests:
  - unit
  - integration
promotion_status: stable
---
# logic-conflict-detection

This skill detects conflicting control flow and contracts.
