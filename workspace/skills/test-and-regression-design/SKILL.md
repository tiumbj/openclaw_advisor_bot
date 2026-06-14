---
name: test-and-regression-design
description: Test and regression design skill.
version: 1.2.8
owner_agent: system-coder-auditor
purpose: Design tests and regression checks.
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
# test-and-regression-design

This skill designs regression checks and fixtures.
