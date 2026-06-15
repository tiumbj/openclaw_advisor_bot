---
name: migration-and-backward-compatibility
description: Implement backward-compatible migrations for schemas, constants, and config.
version: 1.2.14
owner_agent: blueprint-coder
purpose: Prevent breaking changes from disrupting callers; maintain aliases for at least 3 commits.
allowed_inputs:
  - CodeWorkOrder
required_input_schema: object
output_schema: object
allowed_tools:
  - read
  - session_status
  - write
  - edit
  - apply_patch
denied_tools:
  - group:runtime
  - group:web
  - group:ui
  - group:automation
  - group:messaging
  - group:plugins
  - group:memory
  - group:sessions
  - process
  - code_execution
  - browser
  - canvas
  - gateway
  - message
  - subagents
  - memory_search
  - memory_get
  - sessions_list
  - sessions_history
  - sessions_send
  - sessions_spawn
  - sessions_yield
safety_constraints:
  - isolated-worktree-only
  - no secret access
  - no push/merge/deploy
  - no self-approval
  - human-release-gate-closed
failure_behavior: return WorkOrderResult with acceptance_criteria_unmet populated
audit_fields:
  - task_id
  - baseline_commit
  - changed_files
tests:
  - unit
  - integration
promotion_status: p2.4-hardening
---

# Skill: migration-and-backward-compatibility

Owner: blueprint-coder
Phase: P2.4

## Purpose

Design and implement backward-compatible migrations for schemas, constants, APIs,
and configuration files.  Never break an existing test or remove a public constant
without a deprecation period.  All schema version changes must carry the old and
new `formula_version` values in the WorkOrderResult diff summary.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "migration_target": "string (schema name, constant, or module)",
  "old_version": "string",
  "new_version": "string",
  "breaking_changes": ["string"],
  "backward_compatible_period_commits": 3,
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. For formula_version bumps: add the new version string constant; keep the old constant
   as a `_LEGACY_` alias for at least 3 commits before removing it.
2. For constant renames: add the new name; alias the old name with a comment
   `# backward-compat alias: remove after <task_id>`.
3. For config schema changes: confirm the `render_config` + `validate_rendered_config`
   pipeline accepts the new schema; add a migration test that reads an old-format config
   and confirms it is rejected with a clear error message (not silently accepted with wrong values).
4. For database/NDJSON schema changes in `EvidenceArchive` or `OutcomeLedger`: add a
   reader that handles both old and new record formats; never silently discard old records.
5. Write a migration test: confirm the old version is handled correctly (either migrated
   or rejected with a clear error), and the new version is accepted.
6. Update `FORMULA_VERSION` in the relevant module; update `ThresholdConfig` version string.

## Gate Checklist

| Gate | Condition |
|---|---|
| Old version alias present | Legacy constant/version aliased for >= 3 commits |
| Migration test | Test confirms old-format config is handled (migrated or clear error) |
| formula_version updated | Module FORMULA_VERSION constant reflects new version string |
| No silent discard | Old records are migrated or rejected with a log; never silently dropped |
| validate_rendered_config | Passes for new schema; fails for old schema with clear message |

## Decision Tree

```
Schema or version migration required
  ↓
Is this a breaking change (old callers will fail)?
  YES → Add backward-compat alias; schedule removal in a future commit
  NO  → Apply the change directly; confirm old callers still work
        ↓
        Does the change affect EvidenceArchive or OutcomeLedger records on disk?
          YES → Add a dual-format reader; write a migration test with a synthetic old record
          NO  → Update constants and validate; run the test suite
```

## Failure Modes

| Mode | Action |
|---|---|
| Old config silently accepted with wrong values | Fix validate_rendered_config to reject old format; never silently accept wrong version |
| OutcomeLedger reader cannot parse old record | Add explicit version field to new records; default to "v1" for records without version |
| formula_version mismatch in EvidenceArchive | Log a warning; do not reject; tag the record with `version_mismatch=True` |
