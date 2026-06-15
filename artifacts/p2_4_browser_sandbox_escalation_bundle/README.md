# P2.4 Browser Sandbox Escalation Bundle

This bundle captures the latest verified browser sandbox helper findings for P2.4.

Classification:

- `BROWSER_SANDBOX_BLOCKED_UPSTREAM`
- `UPSTREAM_CODEX_RUNTIME_DEFECT`
- `HELPER_ERROR_PROPAGATION_BUG`

What is included:

- Baseline and final Git SHAs
- Package version and phase
- `node_repl.exe` path, hash, and manifest details
- `codex.exe` version and hash
- Process parent chain and observed integrity levels
- MCP stdio protocol observations
- Exact sandbox failure text
- Proof that failure occurred before user JavaScript
- Native Windows ACL comparison results
- Tested path classes
- SID and ACE semantics
- Privilege observations
- Error propagation limitation
- Ownership matrix
- Recommended upstream reproduction procedure
- Verified topology counts: 13 agents and 74 skills
- Non-self-referential SHA semantics for the reconciliation baseline and capture head

Redaction policy:

- No tokens, secrets, chat IDs, or provider keys are included
- Personal paths are included only where required to identify the helper/runtime boundary
- Current commit SHA is intentionally resolved externally rather than embedded in the bundle
