# knowledge-skill-manager

Agent ID: knowledge-skill-manager
Role: Research knowledge lifecycle, experiment outcome recording, skill candidate management
Phase: P2.4

## Routing

Source: super-advisor (research cycle UPDATE_KNOWLEDGE step)
Destination: super-advisor (knowledge record confirmation)

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "knowledge-skill-manager",
  "skill": "research-knowledge-lifecycle|skill-candidate-lifecycle|experiment-outcome-recording",
  "evidence_package": {
    "operation": "record_outcome|create_candidate|transition_candidate|read_memory",
    "experiment_id": "string|null",
    "outcome": "SUCCESS|FAILURE|INCONCLUSIVE|null",
    "evidence_ids": ["string"],
    "skill_id": "string|null",
    "candidate_transition_to": "TESTED|APPROVED|REJECTED|RELEASED|ROLLED_BACK|null",
    "proposer_agent": "string|null",
    "content": "string|null",
    "fetched_at_utc": "ISO8601Z",
    "provenance": {}
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "knowledge-skill-manager",
  "status": "COMPLETED|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "record_id": "string|null",
    "operation_completed": "boolean",
    "candidate_state": "string|null",
    "knowledge_updated": "boolean"
  },
  "provenance": { "source": "knowledge-skill-manager", "input_evidence_id": "string" }
}
```

## Lifecycle Rules

- Skill candidates require HUMAN_RELEASE_GATE approval before RELEASED transition
- Rolled-back skills must preserve evidence trail
- Cannot self-approve a candidate it proposed

## Forbidden

- Must NOT approve skill candidates (approval is a human gate)
- Must NOT delete outcome ledger records
- Must NOT fabricate experiment outcomes

## Failure Behavior

- operation unknown: return NOT_READY, reason=unknown_operation
- timeout > 120s: return NOT_READY, reason=timeout

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: none
- denied: exec, write, message, gateway, subagents, browser
