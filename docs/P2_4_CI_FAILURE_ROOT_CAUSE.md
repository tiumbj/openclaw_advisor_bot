# P2.4 CI Failure Root Cause

## Scope

- Work package: `WP-P2_4-GPT55-PRE-AUDIT-REMEDIATION`
- Phase: `P2.4`
- Baseline commit: `a996540297e43cd0cb540379575ab636f0986b5e`
- GitHub workflow: `ci`
- Failed run: `27503144728`
- Failed job: `validate`
- Failed step: `Ruff`
- Failed command: `python -m ruff check .`
- Exit code: `1`

## Root Cause

The CI run failed before tests because the repository did not satisfy the strict Ruff gate in a clean GitHub Windows runner. The failure was not a GitHub runner outage and was not a transient dependency issue.

Observed failure categories from `gh run view 27503144728 --log-failed`:

- Import ordering issues in production and test modules.
- Unused imports and unused variables.
- Line-length violations in `agent_topology.py`, `fred_adapter.py`, `runtime/watchdog.py`, and tests.
- Ruff-specific lint violations such as ambiguous Unicode text in test documentation.

Local reproduction initially matched the workflow failure mode with:

```powershell
python -m ruff check .
```

## Secondary CI Workflow Issues

The CI workflow also had avoidable gate ambiguity:

- `pytest` already generated coverage through `pyproject.toml`, but the workflow reran pytest in a separate `Coverage` step.
- The workflow uploaded `docs/P2_COVERAGE.json` but did not explicitly assert that the file existed before artifact upload.
- The workflow did not run all required P2.4 validation gates: `pip check`, agent validation, routing validation, and package build.

## Remediation

- Fixed Ruff violations with import sorting, unused import removal, line wrapping, and ASCII-only test documentation.
- Added `engine/.tmp_pytest` to Ruff excludes so a local temp pytest sandbox cannot break lint discovery.
- Kept coverage threshold unchanged at `85`.
- Removed the duplicate pytest coverage rerun from CI.
- Added explicit CI gates:
  - `python -m pip check`
  - `python -m ruff check .`
  - `python -m mypy engine\src`
  - `python -m pytest -m "not live"`
  - `openclaw-advisor validate-skills --strict`
  - `openclaw-advisor validate-agents --strict`
  - `openclaw-advisor validate-routing --strict`
  - `openclaw-advisor render-config --validate --strict`
  - coverage artifact existence check for `docs\P2_COVERAGE.json`
  - `python -m pip wheel . --no-deps --wheel-dir dist`

## Local Verification After Remediation

The following local gates passed before pushing:

| Gate | Command | Result |
| --- | --- | --- |
| Dependency integrity | `python -m pip check` | PASS |
| Lint | `python -m ruff check .` | PASS |
| Type check | `python -m mypy engine\src` | PASS |
| Non-live tests and coverage | `python -m pytest -m "not live"` | PASS, `197 passed, 1 deselected`, total coverage `87.04%` |
| Skill validation | `openclaw-advisor validate-skills --strict` | PASS, 56 skills |
| Agent validation | `openclaw-advisor validate-agents --strict` | PASS, 12 agents |
| Routing validation | `openclaw-advisor validate-routing --strict` | PASS |
| Config validation | `openclaw-advisor render-config --validate --strict` | PASS |
| Package build | `python -m pip wheel . --no-deps --wheel-dir dist` | PASS |
| Control UI E2E | `.\scripts\Test-OpenClawUI.ps1` | PASS |

## Current Truth

Replacement GitHub CI passed on HEAD `286224ec29e0a6881ed3a7003db5b63ec3ba233e` in run `27516318293`.
