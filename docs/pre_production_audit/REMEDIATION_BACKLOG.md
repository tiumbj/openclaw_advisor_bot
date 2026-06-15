# Remediation Backlog

- Baseline commit: `d44da0983b38408575ceedfccb00b909862ff9f0`
- Generated UTC: `2026-06-15T00:57:20.800653Z`
- Evidence hash SHA256: `abcf755071b6b4f02f51be1b56954fcf81e4090271da3bf93a3615ba04c02be5`

- `PPA-0001` `HIGH` P2.4 status reports: Update reports from generated evidence after the final status commit, then re-run CI/security.
- `PPA-0002` `HIGH` OpenClaw runtime configuration: Migrate gateway token to SecretRef or OpenClaw secret store and verify with deep security audit.
- `PPA-0003` `HIGH` MAIN agent manager: Implement and test the MAIN runtime manager before release-gate consideration.
- `PPA-0004` `HIGH` Market data schemas: Add realtime_class/provenance to schemas and enforce it in ingestion, storage, and event validation.
- `PPA-0005` `MEDIUM` Pytest command reproducibility: Make the command create its parent temp directory or document and automate the setup in CI/audit scripts.
- `PPA-0006` `MEDIUM` Required pytest subsets: Separate coverage-gated full suite from subset functional gates or combine coverage across subsets.
- `PPA-0007` `MEDIUM` OpenClaw advisor CLI validators: Require OPENCLAW_ADVISOR_ROOT or reinstall package from the checkout before validators run.
- `PPA-0008` `MEDIUM` OpenClaw doctor and agent tool policy: Resolve doctor warnings or explicitly accept them with risk owner and compensating controls.
- `PPA-0009` `MEDIUM` FRED and browser live evidence: Provide live FRED credential in secure runtime and rerun browser plugin E2E in an environment where the plugin can start.
