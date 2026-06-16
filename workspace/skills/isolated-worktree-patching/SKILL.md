---
name: isolated-worktree-patching
description: Manage the Git worktree lifecycle for patch application, testing, result capture, and clean-up.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Guarantee patches are applied and tested in complete isolation from the main working tree.
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

# Skill: isolated-worktree-patching

Owner: blueprint-coder
Phase: P2.4

## Purpose

Manage the full lifecycle of an isolated Git worktree for blueprint-coder:
creation, branch checkout, patch application, test execution, result capture,
and clean-up.  The worktree must never overlap with the main working tree, must
be cleaned up after the work order completes (pass or fail), and must not leave
uncommitted changes in the main repo.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "worktree_path": "string (absolute path, must differ from main repo root)",
  "branch_name": "string (blueprint/<task_id>)",
  "patch_files": ["string (relative path to patch file or inline diff)"],
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. Verify `worktree_path` does not overlap with the main working tree root:
   `worktree_path != main_root and not worktree_path.startswith(main_root)`.
2. Create the worktree: `git worktree add <worktree_path> <baseline_commit>`.
3. Checkout the feature branch: `git checkout -b blueprint/<task_id>` inside the worktree.
4. Apply each patch in `patch_files` using `git apply --check` first; if the check fails,
   abort and report the conflict in WorkOrderResult.acceptance_criteria_unmet.
5. After applying patches: run `python -m ruff check .`, `python -m mypy engine/src --strict`,
   and `python -m pytest` inside the worktree.
6. Capture the test results and diff (`git diff baseline_commit..HEAD`).
7. Produce the WorkOrderResult with all outcomes.
8. Clean up: `git worktree remove <worktree_path>` regardless of outcome.
9. Do NOT merge, push, or tag the worktree branch.

## Gate Checklist

| Gate | Condition |
|---|---|
| No overlap | worktree_path is outside main repo root |
| Branch isolated | Branch name is `blueprint/<task_id>`; does not exist in main repo |
| patch --check passes | `git apply --check` succeeds before `git apply` |
| Clean-up guaranteed | Worktree removed after work order (even on failure) |
| Main repo clean | `git status` in main repo shows no changes after worktree removal |

## Decision Tree

```
Work order received with worktree_path
  ↓
Does worktree_path overlap with main repo root?
  YES → REJECT work order; report overlap in WorkOrderResult
  NO  → Create worktree; checkout branch
        ↓
        Does git apply --check fail?
          YES → REJECT with patch conflict report; skip test execution
          NO  → Apply patch; run tests
                ↓
                Tests pass? → Produce PASS WorkOrderResult
                Tests fail? → Produce FAIL WorkOrderResult with failure details
                              ↓
                              Clean up worktree in both cases
```

## Failure Modes

| Mode | Action |
|---|---|
| git worktree add fails (branch already exists) | Use `git worktree add -B` to force; or delete the stale worktree first |
| patch --check fails due to context mismatch | Regenerate the patch from the exact baseline_commit; do not adjust context |
| Worktree clean-up fails (locked by process) | Log the error; attempt `git worktree prune`; report in WorkOrderResult |
| Main repo shows uncommitted changes after removal | Run `git worktree prune && git clean -fd` inside main repo; report to human if unclear |
