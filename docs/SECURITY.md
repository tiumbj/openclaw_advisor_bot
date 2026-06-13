# Security

Version: `1.1.1`  
Phase: `P1.1`

- `state\.env` and `state\openclaw.json` are local runtime artifacts and must not be tracked.
- The config template enforces a read-only sandbox with only `read` and `session_status`.
- Security audit includes source-text scan, AST scan, resolved-constant scan, runtime import-graph reachability, and secret scanning for working tree, staged files, and git history.
- Hooks stay disabled by default, and no execution, messaging, or broker-write tool is permitted.
