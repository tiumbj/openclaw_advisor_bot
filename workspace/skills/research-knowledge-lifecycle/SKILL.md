---
name: research-knowledge-lifecycle
description: Manage the lifecycle of research findings from observation through validated knowledge entry.
version: 1.2.11
owner_agent: knowledge-skill-manager
purpose: Ensure research outputs are stored, versioned, and accessible to all agents without duplication.
allowed_inputs:
  - research finding
  - experiment outcome
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
failure_behavior: return KNOWLEDGE_INGESTION_FAILED with reason
audit_fields:
  - knowledge_id
  - source_experiment_id
  - knowledge_type
  - validation_status
  - version
tests:
  - unit
  - integration
promotion_status: stable
---
# research-knowledge-lifecycle

## Procedure
1. Receive research finding or RELEASED experiment outcome
2. Extract validated insight: what changed, what improved, what conditions apply
3. Check deduplication: does equivalent knowledge already exist in knowledge store?
4. Assign knowledge_id, knowledge_type (pattern/rule/parameter/regime), version
5. Store in research knowledge store; notify skill-candidate-lifecycle if improvement implies skill change

## Decision Tree
- RELEASED experiment → knowledge eligible for ingestion
- ROLLED_BACK experiment → log anti-knowledge (what did NOT work) with reason
- Duplicate knowledge (same insight different wording) → merge, do not create duplicate

## Quality Gates
- Only RELEASED or ROLLED_BACK experiment outcomes feed knowledge store
- Knowledge must cite source_experiment_id (immutable reference)
- Anti-knowledge (failures) equally important as successes — never suppress

## Failure Modes
- Experiment RELEASED without outcome metrics → KNOWLEDGE_INGESTION_FAILED (no numeric evidence)
- Conflicting knowledge entries → flag conflict for MAIN agent review
