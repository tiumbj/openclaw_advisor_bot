---
name: privilege-boundary-audit
description: Verify each agent's tool allow/deny lists match the Blueprint isolation contract.
version: 1.2.15
owner_agent: security-compliance-agent
purpose: Ensure no agent has been granted tools beyond its defined privilege boundary.
allowed_inputs:
  - agent contract record
  - constants tool manifest
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
failure_behavior: return PRIVILEGE_VIOLATION with over-privileged tools list
audit_fields:
  - agent_id
  - expected_allowed_tools
  - actual_allowed_tools
  - over_privileged_tools
  - under_privileged_tools
tests:
  - unit
  - integration
promotion_status: stable
---
# privilege-boundary-audit

## Procedure
1. Load AGENT_ALLOWED_TOOLS and AGENT_DENIED_TOOLS from constants.py for each agent
2. Load agent contract from agent_topology.py (AgentContract.allowed_tools, denied_tools)
3. Cross-reference: any tool in allowed that is not in Blueprint definition → PRIVILEGE_VIOLATION
4. Check _STANDARD_DENY appears in every agent's denied_tools
5. Return audit per agent: COMPLIANT or PRIVILEGE_VIOLATION

## Decision Tree
- All agents have tool lists matching Blueprint exactly → COMPLIANT
- Any agent missing a _STANDARD_DENY item → PRIVILEGE_VIOLATION
- Any agent with execute/write tool in allowed → CRITICAL_PRIVILEGE_VIOLATION

## Quality Gates
- Tool manifests are compared at schema level, not text search
- _STANDARD_DENY 21 entries must appear in every agent's denied_tools

## Failure Modes
- New tool added to platform but not to deny list → caught by this audit
- Agent alias (super-advisor = main-agent) creates duplicate contract → flag duplicate identity
