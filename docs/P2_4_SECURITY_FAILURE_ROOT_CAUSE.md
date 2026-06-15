# P2.4 Security Failure Root Cause

## Scope

- Work package: `WP-P2_4-GPT55-PRE-AUDIT-REMEDIATION`
- Phase: `P2.4`
- Baseline commit: `a996540297e43cd0cb540379575ab636f0986b5e`
- GitHub workflow: `security`
- Failed run: `27503144729`
- Failed job: `audit`
- Failed step: `Secret, source, AST, constant, graph, and tracking scan`
- Failed command: `openclaw-advisor security-scan --include-history --strict | Tee-Object -FilePath security-scan.json`
- Exit code: `1`

## Root Cause

The strict security scan failed because generated reports and artifact bundles containing historical quoted findings were classified as `ACTIVE_SOURCE`. These files contained documented references to forbidden trading execution symbols, but they were evidence/report material, not executable runtime source.

The scanner therefore reported thousands of active-source violations even though the offending matches came from report artifacts and documentation quotes.

Local reproduction before remediation:

```powershell
openclaw-advisor security-scan --include-history --strict
```

Observed local failure shape before remediation:

- `summary.pass=false`
- `active_source_violations` greater than zero
- Matches included generated JSON report artifacts and `docs` evidence files.

## Security Boundary Decision

The fix does not weaken strict mode and does not remove forbidden symbols from the active-source rule set. The scanner still fails if forbidden execution symbols appear in source files.

The fix changes path classification so generated report artifacts and documentation are not treated as executable active source:

- `docs` stays `DOCUMENTATION`.
- `artifacts` is classified as `DOCUMENTATION`.
- generated `security-scan.json` is classified as `DOCUMENTATION`.
- local pytest temp directories and Python cache directories are ignored.

## Dependency Audit Finding

Local `pip-audit` initially found vulnerabilities in the installed environment:

- `pip 25.0.1`
- `pyarrow 19.0.1`

`pyproject.toml` already required `pyarrow>=23.0.1,<24`, so the local environment was stale. The environment was aligned to project requirements with:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

After alignment:

- `pip` version: `26.1.2`
- `pyarrow` version: `23.0.1`
- `openclaw-advisor-foundation` version: `1.2.10`
- `python -m pip_audit`: PASS, no known vulnerabilities found

## Local Verification After Remediation

| Gate | Command | Result |
| --- | --- | --- |
| Strict source/security scan | `openclaw-advisor security-scan --include-history --strict` | PASS, `active_source_violations=0` |
| Dependency audit | `python -m pip_audit` | PASS, no known vulnerabilities found |
| Dependency integrity | `python -m pip check` | PASS |
| Config validation | `openclaw-advisor render-config --validate --strict` | PASS |
| Skill validation | `openclaw-advisor validate-skills --strict` | PASS |
| Control UI E2E | `.\scripts\Test-OpenClawUI.ps1` | PASS |

## Current Truth

Replacement GitHub security passed on HEAD `286224ec29e0a6881ed3a7003db5b63ec3ba233e` in run `27516318322`.
