# Environment Variables

Version: `1.2.1`  
Phase: `P2.2`

- Canonical publication-safe template: `.env.example`
- Runtime-only local file: `state\.env`
- `state\.env` must never be tracked by Git.
- Validation statuses are `PRESENT`, `MISSING`, `BLANK`, or `INVALID_FORMAT`.
- Safety flags must remain `ADVISOR_ONLY=true`, `EXECUTION_ALLOWED=false`, and `ALLOW_ORDER_SEND=false`.
