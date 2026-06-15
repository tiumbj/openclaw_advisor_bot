# Independent Pre-production Audit Findings

- Baseline commit: `d44da0983b38408575ceedfccb00b909862ff9f0`
- Generated UTC: `2026-06-15T00:57:20.800653Z`
- Evidence hash SHA256: `aca02714e36b4584245ad16644426b6d8ce9d0eb034620c02743af7fe8a77952`

## PPA-0001 HIGH - report-truth

- Component: `P2.4 status reports`
- Expected: Committed reports must identify the actual audited HEAD and final GitHub run IDs.
- Actual: PROJECT_STATUS.json still records observed_remote_head, implementation_commit, and github_gates for 286224e while actual HEAD is d44da09.
- Impact: A next auditor cannot rely on Git reports alone to reconstruct final provenance.
- Remediation: Update reports from generated evidence after the final status commit, then re-run CI/security.
- Status: `OPEN`


## PPA-0002 HIGH - runtime-security

- Component: `OpenClaw runtime configuration`
- Expected: Runtime config must keep secret-bearing fields out of plaintext-readable config.
- Actual: openclaw doctor warns that state/openclaw.json contains plaintext secret-bearing gateway.auth.token.
- Impact: Agents or tools with config read access may expose runtime auth material.
- Remediation: Migrate gateway token to SecretRef or OpenClaw secret store and verify with deep security audit.
- Status: `OPEN`


## PPA-0003 HIGH - architecture-runtime

- Component: `MAIN agent manager`
- Expected: MAIN must be a runtime orchestrator with capability-based routing, validation, conflict resolution, max hops, pause/stop/resume, and recovery idempotency.
- Actual: Production source exposes only simple MainPlanner and AgentRouter helpers; no executable MAIN runtime loop, result validator, conflict resolver, recovery resume, or idempotent dispatch path was found.
- Impact: Blueprint requirements for MAIN runtime behavior are not proven by production code.
- Remediation: Implement and test the MAIN runtime manager before release-gate consideration.
- Status: `OPEN`


## PPA-0004 HIGH - data-provenance

- Component: `Market data schemas`
- Expected: All market numerics must carry provenance including realtime_class.
- Actual: TickRecord and BarRecord contain data_quality but no realtime_class field.
- Impact: Agents and downstream logic cannot reliably distinguish realtime, stale, unknown, and daily macro data.
- Remediation: Add realtime_class/provenance to schemas and enforce it in ingestion, storage, and event validation.
- Status: `OPEN`


## PPA-0005 MEDIUM - clean-validation

- Component: `Pytest command reproducibility`
- Expected: Required audit command must run from clean checkout exactly as specified.
- Actual: python -m pytest -m "not live" -q --basetemp .\_tmp\audit-pytest fails when .\_tmp does not already exist.
- Impact: Required validation is not directly reproducible without an undocumented setup step.
- Remediation: Make the command create its parent temp directory or document and automate the setup in CI/audit scripts.
- Status: `OPEN`


## PPA-0006 MEDIUM - test-configuration

- Component: `Required pytest subsets`
- Expected: Required unit, integration, and security subset commands should be runnable audit gates.
- Actual: Running each subset alone fails the global coverage fail-under gate even when tests pass.
- Impact: The required validation list cannot be interpreted unambiguously as independent gates.
- Remediation: Separate coverage-gated full suite from subset functional gates or combine coverage across subsets.
- Status: `OPEN`


## PPA-0007 MEDIUM - audit-isolation

- Component: `OpenClaw advisor CLI validators`
- Expected: Clean clone validation must operate on the checkout under audit.
- Actual: Advisor validator outputs resolved paths to C:\Data\OpenClawSuperAdvisor instead of the isolated clone path, indicating editable-install/root resolution contamination.
- Impact: A clean-checkout audit can silently validate the wrong working tree or state directory.
- Remediation: Require OPENCLAW_ADVISOR_ROOT or reinstall package from the checkout before validators run.
- Status: `OPEN`


## PPA-0008 MEDIUM - runtime-health

- Component: `OpenClaw doctor and agent tool policy`
- Expected: Runtime health checks should have no unresolved warnings before pre-production approval.
- Actual: openclaw doctor reports missing command owner, message tool unavailable for telegram route, stale/missing session transcript state, and minimal profile policy warnings.
- Impact: Operational ownership, Telegram behavior, and forensic session integrity are not release-ready.
- Remediation: Resolve doctor warnings or explicitly accept them with risk owner and compensating controls.
- Status: `OPEN`


## PPA-0009 MEDIUM - required-live-evidence

- Component: `FRED and browser live evidence`
- Expected: Pre-production PASS requires live FRED validation and browser E2E evidence.
- Actual: No FRED_API_KEY/live FRED result was available in audit evidence; Browser plugin bootstrap failed with sandbox ACL before in-app browser E2E could run.
- Impact: Live data and browser readiness cannot be approved.
- Remediation: Provide live FRED credential in secure runtime and rerun browser plugin E2E in an environment where the plugin can start.
- Status: `OPEN`


## PPA-0010 LOW - build-cleanliness

- Component: `Package build`
- Expected: Audit/build commands should not leave untracked generated artifacts unless ignored or cleaned.
- Actual: python -m build generated dist/ and egg-info artifacts in the audit clone.
- Impact: Repeated audit runs can accumulate local noise and obscure source changes.
- Remediation: Update ignore/cleanup policy for generated build and coverage outputs.
- Status: `OPEN`
