---
name: component-restart-protocol
description: Bounded automatic restart procedure for failed system components with rollback guard.
version: 1.2.15
owner_agent: reliability-watchdog-agent
purpose: Recover failed components without human intervention up to max_restart_attempts.
allowed_inputs:
  - incident report
  - watchdog report
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
failure_behavior: return RESTART_EXHAUSTED after max_restart_attempts with human escalation
audit_fields:
  - incident_id
  - component
  - restart_attempt
  - max_restart_attempts
  - restart_outcome
tests:
  - unit
  - integration
promotion_status: stable
---
# component-restart-protocol

## Procedure
1. Receive FAILED component from process-health-monitor
2. Check restart_attempts[component] against max_restart_attempts (default: 3)
3. If attempts remaining: signal restart via shutdown.trigger_shutdown + Start-AdvisorStack
4. After restart: probe component health; if OK → increment recovery counter
5. If max_restart_attempts reached → RESTART_EXHAUSTED → send HUMAN_INTERVENTION_REQUIRED

## Decision Tree
- restart_attempts < max_restart_attempts → attempt restart
- restart_attempts == max_restart_attempts → RESTART_EXHAUSTED + human escalation
- Component recovers after restart → SYSTEM_RECOVERED event
- Restart causes new component failure → cascade → SYSTEM_OFFLINE_DETECTED

## Quality Gates
- Restart attempts tracked in Python Watchdog class, not agent memory
- Only Python engine and Gateway components are auto-restartable
- Database and evidence archive components: escalate immediately (no auto-restart)

## Failure Modes
- Rapid restart loop (component crashes immediately each time) → circuit breaker after 3 attempts
- Restart script not found → RESTART_EXHAUSTED immediately, log missing script
