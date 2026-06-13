# Security

- `state/.env` is the only runtime environment file.
- Gateway auth is token-based and must come from env.
- Hooks remain disabled by default.
- `super-advisor` can only use `read` and `session_status`.
- No execution, browser, messaging, or write tools are enabled.
