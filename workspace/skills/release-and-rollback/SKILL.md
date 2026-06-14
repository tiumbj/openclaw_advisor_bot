---
name: release-and-rollback
description: Release and rollback skill.
version: 1.2.8
owner_agent: system-coder-auditor
purpose: Define release gates and rollback evidence.
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
# release-and-rollback

This skill supports release and rollback evidence only.
