---
name: process-health-monitor
description: Monitor Python engine, OpenClaw Gateway, and queue worker process health via probes.
version: 1.2.12
owner_agent: reliability-watchdog-agent
purpose: Detect process crashes and degradation before they cause evidence pipeline gaps.
allowed_inputs:
  - watchdog report
  - component probe results
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
failure_behavior: return HEALTH_DEGRADED or HEALTH_FAILED with component list
audit_fields:
  - check_id
  - components_healthy
  - components_degraded
  - components_failed
  - consecutive_failures
tests:
  - unit
  - integration
promotion_status: stable
---
# process-health-monitor

## Procedure
1. Receive WatchdogReport from runtime/watchdog.py ComponentProbe results
2. Classify overall system health: HEALTHY (all OK), DEGRADED (any DEGRADED), FAILED (any FAILED)
3. For each DEGRADED/FAILED component track consecutive_failures counter
4. At consecutive_failures >= 3 → escalate to incident
5. Return health_report: component_statuses, overall_status, escalation_required

## Decision Tree
- All components OK → HEALTHY
- Any component DEGRADED (1-2 failures) → DEGRADED (alert but continue)
- Any component FAILED (3+ failures) → FAILED → trigger component-restart-protocol
- Multiple components FAILED simultaneously → SYSTEM_OFFLINE_DETECTED event

## Quality Gates
- Health check uses ComponentProbe callable, not agent inference
- consecutive_failures tracked in Python WatchdogReport, not agent memory

## Failure Modes
- Watchdog itself crashes: missed heartbeat detected by external endpoint → SYSTEM_OFFLINE_DETECTED
- Probe returns false positive on temporary blip → DEGRADED after 1 failure, escalate only after 3
