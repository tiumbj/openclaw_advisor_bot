---
name: xauusd-market-analysis
description: XAUUSD market analysis skill.
version: 1.2.8
owner_agent: xau-strategy-auditor
purpose: Audit XAUUSD structure and setup quality.
allowed_inputs:
  - market evidence
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
# xauusd-market-analysis

This skill audits XAUUSD evidence only.
