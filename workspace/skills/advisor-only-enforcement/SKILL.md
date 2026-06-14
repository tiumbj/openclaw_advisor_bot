---
name: advisor-only-enforcement
description: Audit all agent outputs and tool calls for advisor-only compliance (no trade execution, no OrderSend).
version: 1.2.8
owner_agent: security-compliance-agent
purpose: Prevent any code path from reaching MT5 write operations or broker execution APIs.
allowed_inputs:
  - agent output record
  - tool call log
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
failure_behavior: return ADVISOR_VIOLATION with violation details and halt flag
audit_fields:
  - evidence_id
  - violation_type
  - offending_agent
  - offending_call
  - halt_required
tests:
  - unit
  - integration
promotion_status: stable
---
# advisor-only-enforcement

## Procedure
1. Scan all tool calls in agent session for: OrderSend, order_send, place_order, execute_trade, broker_write
2. Verify ALLOW_ORDER_SEND env var is false; EXECUTION_ALLOWED is false; ADVISOR_ONLY is true
3. Check no agent has write access to MT5 via gateway (gateway tool denied for all agents)
4. Verify no agent output contains executable trading instruction directed at broker
5. Return compliance audit: COMPLIANT or ADVISOR_VIOLATION

## Decision Tree
- No execution tool calls and env constraints confirmed → COMPLIANT
- Any OrderSend or broker write found → ADVISOR_VIOLATION + halt_required=true
- Ambiguous output (text describing a trade but no tool call) → flag for human review

## Quality Gates
- All agents must have gateway in denied_tools
- ALLOW_ORDER_SEND=false is a hard invariant — cannot be overridden at runtime
- Any ADVISOR_VIOLATION triggers SECURITY_ALERT Telegram event

## Failure Modes
- Agent uses indirect code path to reach MT5 → caught by MT5 adapter read-only enforcement
- Test code accidentally enables order send → catch in CI before commit
