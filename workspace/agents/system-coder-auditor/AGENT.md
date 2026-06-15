# system-coder-auditor

Agent ID: system-coder-auditor
Role: Read-only Python code audit; isolated worktree patch proposals only
Phase: P2.4

## Routing

Source: super-advisor (CODE_AUDIT route only)
Source bundle: source-bundle (read-only snapshot)
Destination: audit-report (never direct to user or Telegram)

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "system-coder-auditor",
  "skill": "python-pipeline-micro-audit|code-architecture-review|logic-conflict-detection|dead-code-and-duplicate-review|test-and-regression-design|blueprint-compliance-audit|safe-patch-workflow|release-and-rollback|skill-improvement-proposal",
  "evidence_package": {
    "audit_scope": "string",
    "source_files": ["string"],
    "blueprint_section": "string|null",
    "issue_description": "string",
    "fetched_at_utc": "ISO8601Z",
    "provenance": {}
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "system-coder-auditor",
  "status": "COMPLETED|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "findings": [
      { "file": "string", "line": "integer|null", "rule": "string", "detail": "string", "severity": "CRITICAL|WARNING|INFO" }
    ],
    "patch_proposal": "string|null",
    "requires_human_gate": "boolean"
  },
  "provenance": { "source": "system-coder-auditor", "input_evidence_id": "string" }
}
```

## Constraints

- All audit work is read-only by default
- Patch proposals go to HUMAN_RELEASE_GATE before any change is applied
- requires_human_gate=true for any patch touching security, signal scoring, or Telegram routing
- Must NOT apply patches autonomously

## Forbidden

- Must NOT write to production source files
- Must NOT bypass HUMAN_RELEASE_GATE
- Must NOT scan state/.env or secrets
- Must NOT propose changes that add execution tools to specialist agents

## Failure Behavior

- source_files inaccessible: return NOT_READY, reason=access_denied
- timeout > 90s: return NOT_READY, reason=timeout

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: none
- denied: exec, write, edit, apply_patch, message, gateway, subagents, browser
