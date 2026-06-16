---
name: test-and-regression-engineering
description: Write pytest unit and integration tests with mocked I/O and coverage >= 85%.
version: 1.2.15
owner_agent: blueprint-coder
purpose: Produce tests that are deterministic, isolated, and express intended behaviour, not implementation.
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

# Skill: test-and-regression-engineering

Owner: blueprint-coder
Phase: P2.4

## Purpose

Write unit, integration, and regression tests that are deterministic, isolated,
and express the intended behaviour rather than the implementation.  Every test
added by blueprint-coder must follow the pytest fixture model, must not use
live Telegram or real secrets, and must contribute to coverage >= 85% for the
changed module.

## Input Schema

```json
{
  "task_id": "string",
  "baseline_commit": "string (SHA-1)",
  "target_module": "string (dotted path)",
  "test_scenarios": [{"name": "string", "input": "object", "expected": "object"}],
  "coverage_requirement": 85,
  "acceptance_criteria": ["string"]
}
```

## Procedure

1. For each scenario in `test_scenarios`: write a function named
   `test_<scenario_name>` with a single assert per behaviour.
2. Do NOT use `unittest.TestCase`; use plain pytest functions and fixtures.
3. Mock all external I/O (MT5, FRED, Telegram) using `pytest.monkeypatch` or
   the `http_post` parameter injection pattern established in conftest.py.
4. Never read `state/.env` or any secret in a test; use the `env_path=paths.canonical_env_example_path`
   pattern from existing tests.
5. Parametrize tests that share the same structure with `@pytest.mark.parametrize`.
6. For regression tests: include a comment stating the bug it guards against and
   the commit where it was fixed.
7. Run `python -m pytest --cov=openclaw_super_advisor.<target_module> --cov-report=term-missing`;
   confirm coverage >= 85%.

## Gate Checklist

| Gate | Condition |
|---|---|
| No live external calls | All I/O mocked; no network, no MT5, no Telegram API |
| No secrets in tests | .env not read; env_path=canonical_env_example_path used |
| Single assert per behaviour | Each test function has one logical assertion per behaviour |
| Coverage >= 85% | Module branch coverage reported >= 85% |
| Regression comment | Each regression test has a comment citing the bug |

## Decision Tree

```
New test scenario required
  ↓
Is the scenario testing external I/O?
  YES → Mock the I/O; use the http_post injection pattern for Telegram
  NO  → Is the scenario testing a pure function?
          YES → Call the function directly; no fixtures needed
          NO  → Use conftest fixtures (sample_project, build_paths)
                ↓
                Does the test require file system access?
                  YES → Use tmp_path fixture; never use C:\Temp or Windows global temp
```

## Failure Modes

| Mode | Action |
|---|---|
| Test uses live Telegram | Reject; rewrite with mock http_post transport |
| Coverage below 85% | Add parametrized tests for the uncovered branches |
| Flaky test (sometimes passes, sometimes fails) | Identify the non-deterministic dependency; fix or mock it |
| Test passes but asserts nothing meaningful | Strengthen the assertion; `assert True` is not a test |
