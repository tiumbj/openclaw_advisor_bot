---
name: skill-candidate-lifecycle
description: Manage new skill proposals from candidate to validated SKILL.md through the skill validator gate.
version: 1.2.8
owner_agent: knowledge-skill-manager
purpose: Ensure new skills meet frontmatter completeness and semantic depth before entering production workspace.
allowed_inputs:
  - skill candidate specification
  - knowledge finding
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
failure_behavior: return SKILL_CANDIDATE_REJECTED with validation failures
audit_fields:
  - skill_name
  - validation_result
  - failed_checks
  - promoted_at
tests:
  - unit
  - integration
promotion_status: stable
---
# skill-candidate-lifecycle

## Procedure
1. Receive skill candidate specification (frontmatter + body draft)
2. Run skill validator: frontmatter required fields, version format, owner_agent exists in 12-agent topology
3. Run semantic depth check: body must contain Procedure, Decision Tree, Quality Gates, Failure Modes sections
4. If validation passes: write SKILL.md to workspace/skills/<name>/ via safe-patch-workflow
5. If validation fails: return SKILL_CANDIDATE_REJECTED with specific failed checks

## Decision Tree
- All frontmatter fields present AND semantic sections complete → SKILL_PROMOTED
- Missing frontmatter field → SKILL_CANDIDATE_REJECTED (list missing fields)
- Missing semantic section → SKILL_CANDIDATE_REJECTED (list missing sections)
- owner_agent not in 12-agent topology → SKILL_CANDIDATE_REJECTED

## Quality Gates
- version must match current system version (1.2.8)
- Skill name must be kebab-case, unique across workspace/skills/
- safe-patch-workflow must be used for writing (no direct file write by agent)

## Failure Modes
- Skill file already exists: propose update not new file
- Duplicate skill purpose (same function different name): flag for merge
