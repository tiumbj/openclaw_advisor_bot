---
name: agent-orchestration-contract
description: MAIN safe routing and orchestration constraints for all 11 specialist agents.
version: 1.2.12
owner_agent: super-advisor
purpose: Define safe agent routing, task dispatch, and conflict detection rules for MAIN.
allowed_inputs:
  - routing specification
  - task dispatch request
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
failure_behavior: return structured routing rejection
audit_fields:
  - task_id
  - source_agent
  - target_agent
  - route_allowed
tests:
  - unit
  - integration
promotion_status: stable
---
# agent-orchestration-contract

MAIN uses this skill to validate all agent routing and task dispatch before execution.

## Procedure

1. Receive routing request with source_agent, target_agent, event_type, and task_id.
2. Verify source_agent and target_agent are in the 11-agent topology.
3. Look up (source_agent, target_agent) pair in REALTIME_ROUTE_ALLOWLIST.
4. If not in allowlist, return route_allowed=false, reason=route_not_in_allowlist.
5. Verify task_id is non-empty UUID4.
6. Check for concurrent task on target_agent; if busy, set queued=true.
7. Check deduplication window for duplicate dedup_key.
8. Return route_allowed=true or structured rejection.

## Decision Tree

- source_agent not in topology → REJECT, reason=unknown_source_agent
- target_agent not in topology → REJECT, reason=unknown_target_agent
- (source, target) not in REALTIME_ROUTE_ALLOWLIST → REJECT, reason=route_not_in_allowlist
- task_id missing → REJECT, reason=missing_task_id
- target_agent busy with other task → route_allowed=true, queued=true (hold for retry)
- dedup_key seen within dedup window → DROP, reason=duplicate_event
- All checks pass → route_allowed=true, queued=false

## REALTIME_ROUTE_ALLOWLIST

Only these exact directed routes are permitted in realtime:

| Source | Destination | Allowed Events |
|---|---|---|
| evidence-archive | super-advisor | NEW_EVIDENCE |
| super-advisor | xau-strategy-auditor | ANALYSIS_REQUEST |
| xau-strategy-auditor | super-advisor | ANALYSIS_RESULT |
| super-advisor | telegram-publisher | APPROVED_PUBLICATION |
| telegram-publisher | outcome-ledger | DELIVERY_RECEIPT |

All other source→destination pairs: DENY, reason=route_not_in_allowlist

## Task Dispatch Rules

- MAIN must dispatch one task at a time per agent (no concurrent tasks to same agent_id)
- task_id must be globally unique (UUID4)
- skill must be in the target agent's AGENT.md allowed skills list
- Dispatch payload must include: task_id, agent_id, skill, evidence_package, correlation_id

## Conflict Detection

- If agent A is already executing task T1 and MAIN tries to dispatch T2 to A: QUEUE (do not drop)
- If two evidence packets with same dedup_key arrive within deduplication_window_seconds: DROP the second
- If MAIN receives results from an agent_id it did not dispatch: REJECT, reason=undispatchd_agent_result

## Required Input Fields

- `source_agent`: string (must be an agent_id in the 11-agent topology)
- `target_agent`: string (must be an agent_id in the 11-agent topology)
- `event_type`: string
- `task_id`: UUID4 string

## Output Fields

- `route_allowed`: boolean
- `reason`: string (populated when route_allowed=false)
- `queued`: boolean (true when task was deferred due to concurrent execution)

## Failure Modes

- source_agent not in topology: REJECT, reason=unknown_source_agent
- target_agent not in topology: REJECT, reason=unknown_target_agent
- Route not in allowlist: REJECT, reason=route_not_in_allowlist
- task_id missing: REJECT, reason=missing_task_id
