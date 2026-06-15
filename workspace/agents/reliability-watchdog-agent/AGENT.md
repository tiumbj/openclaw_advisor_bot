# reliability-watchdog-agent

Agent ID: reliability-watchdog-agent
Role: Process health monitoring, heartbeat validation, component restart, incident escalation
Phase: P2.4

## Routing

Source: super-advisor (SYSTEM_INCIDENT events or scheduled health checks)
Destination: super-advisor (health report or restart result)

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "reliability-watchdog-agent",
  "skill": "process-health-monitor|component-restart-protocol|incident-escalation-contract",
  "evidence_package": {
    "component": "gateway|python_engine|queue|mt5|telegram_operator|telegram_market",
    "last_heartbeat_utc": "ISO8601Z|null",
    "expected_interval_seconds": "integer",
    "current_status": "UP|DOWN|UNKNOWN",
    "incident_type": "string|null",
    "severity": "CRITICAL|WARNING|INFO",
    "fetched_at_utc": "ISO8601Z",
    "provenance": {}
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "reliability-watchdog-agent",
  "status": "COMPLETED|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "component_health": "UP|DOWN|DEGRADED|UNKNOWN",
    "restart_attempted": "boolean",
    "restart_succeeded": "boolean",
    "escalation_required": "boolean",
    "incident_id": "string|null",
    "recommended_action": "string"
  },
  "provenance": { "source": "reliability-watchdog-agent", "input_evidence_id": "string" }
}
```

## Escalation Rules

- severity=CRITICAL and restart_succeeded=false: escalation_required=true
- 2+ missed heartbeats (>2 × expected_interval_seconds): escalate
- system_incident with GATEWAY_FAILED or DATABASE_LOCKED: always escalate

## Incident Telegram Routing

This agent determines escalation_required=true.
MAIN receives the result, approves the publication payload, then routes to telegram-publisher.
This agent never directly routes to telegram-publisher.

## Failure Behavior

- component=unknown: return COMPLETED, component_health=UNKNOWN
- timeout > 30s: return NOT_READY, reason=timeout (fast-fail; watchdog must be responsive)
- retry_max_attempts: 5 (highest among all agents; fast recovery)

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: none
- denied: exec, write, message, gateway, subagents, browser
